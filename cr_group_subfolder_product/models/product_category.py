# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, _
from odoo.exceptions import UserError, RedirectWarning


class ProductCategory(models.Model):
    """
    Extends product.category to support a configurable folder structure.

    The folder_structure_ids One2many holds template lines (cr.category.folder.line)
    that define a folder hierarchy (using dot-sequence notation). When a product is
    assigned this category, documents.document folders are auto-created per product.

    On deletion of a folder line, safe-delete logic is applied to all related products:
    folders with no documents are deleted, folders with documents are preserved.
    """

    _inherit = 'product.category'

    folder_structure_ids = fields.One2many(
        'cr.category.folder.line',
        'category_id',
        string='Folder Structure',
        help=(
            'Define a folder hierarchy for products in this category. '
            'Sequence uses dot notation: 1.0 = top-level, 1.1 = child of 1.0, etc.'
        ),
    )

    def write(self, vals):
        """
        Override write to detect changes in folder structure and propagate
        them to all products in this category.

        - Deletions: If a folder line is removed, we safely delete its
          matching folders on all products (folder must be empty).
        - Additions/Updates: Any addition or renaming in the structure
          is synced to all products.
        """
        # 1. Identify deleted lines and handle cascading deletions
        deleted_line_ids = []
        if 'folder_structure_ids' in vals:
            for cmd in vals['folder_structure_ids']:
                # Command.DELETE (2) or Command.UNLINK (3)
                if cmd[0] in (2, 3) and cmd[1]:
                    deleted_line_ids.append(cmd[1])

            if deleted_line_ids:
                lines = self.env['cr.category.folder.line'].browse(deleted_line_ids)
                all_to_delete = lines
                for line in lines:
                    all_to_delete |= line._get_descendant_lines()

                # Check if any folder (including subfolders) has documents
                if any(l._cr_has_any_documents() for l in all_to_delete):
                    if not self.env.context.get('cr_force_delete_lines'):
                        action = self.env.ref('cr_group_subfolder_product.action_cr_folder_delete_warning')
                        raise RedirectWarning(
                            _("Some subfolders contain files. Do you want to continue or cancel?"),
                            action.id,
                            _("Continue with Deletion"),
                            additional_context={
                                'default_line_ids': [fields.Command.set(all_to_delete.ids)],
                                'default_category_id': self.id,
                            }
                        )

                # Ensure all descendant lines are also marked for deletion in vals
                # so the One2many is cleaned up logically
                final_deleted_ids = all_to_delete.ids
                existing_cmds_ids = [c[1] for c in vals['folder_structure_ids'] if c[0] in (2, 3)]
                for line_id in final_deleted_ids:
                    if line_id not in existing_cmds_ids:
                        vals['folder_structure_ids'].append((2, line_id, 0))

                deleted_line_ids = final_deleted_ids  # For step 2

        # 2. Identify all managed folders linked to these specific lines (all products)
        folders_to_delete = self.env['documents.document']
        if deleted_line_ids:
            folders_to_delete = self.env['documents.document'].sudo().search([
                ('type', '=', 'folder'),
                ('cr_category_folder_line_id', 'in', deleted_line_ids),
            ])

        # 3. Perform the write to the database
        result = super().write(vals)

        # 4. Handle Deletions: Safe-delete folders that lost their configuration line
        # If cr_force_delete_lines is in context, we skip safety checks
        force_delete = self.env.context.get('cr_force_delete_lines')
        for folder in folders_to_delete:
            if folder.exists():
                if force_delete:
                    folder.sudo().unlink()
                else:
                    folder._cr_safe_delete_folder()

        # 5. Handle Additions/Updates: Sync structure for all related products
        if 'folder_structure_ids' in vals:
            for category in self:
                products = self.env['product.template'].search([
                    ('categ_id', '=', category.id),
                ])
                for product in products:
                    product._cr_create_folder_structure(category)

        return result

    def action_delete_checked_lines(self):
        """
        Action to delete folder lines that are marked as 'is_selected',
        skipping any folders that contain files or are parents of folders with files.
        """
        self.ensure_one()
        selected_lines = self.folder_structure_ids.filtered('is_selected')
        if not selected_lines:
            raise UserError(_("Please select at least one line to delete."))

        # 1. Expand selection to include all descendants (candidates for deletion)
        candidates = selected_lines
        for line in selected_lines:
            candidates |= line._get_descendant_lines()

        # 2. Identify untouchable lines (those with files or parents of those with files)
        all_lines = self.folder_structure_ids
        lines_with_files = all_lines.filtered(lambda l: l._cr_has_any_documents())
        untouchable = lines_with_files
        for line in lines_with_files:
            untouchable |= line._cr_get_all_parent_lines()

        # 3. Calculate safe set for deletion
        final_to_delete = candidates - untouchable

        # 4. Handle skips and redirection
        if candidates & untouchable:
            folders_with_files = candidates.filtered(lambda l: l._cr_has_direct_documents())
            skipped_parents = (candidates & untouchable) - folders_with_files
            
            msg_parts = []
            if folders_with_files:
                names_files = ", ".join([f"{l.name} ({l.sequence})" for l in folders_with_files])
                msg_parts.append(_("The following folders specifically contain files: %s.") % names_files)
            
            if skipped_parents:
                names_parents = ", ".join([f"{l.name} ({l.sequence})" for l in skipped_parents])
                msg_parts.append(_("Additionally, the following folders will be skipped to preserve the hierarchy: %s.") % names_parents)
            
            message = "\n".join(msg_parts)

            if not final_to_delete:
                # If everything selected was untouchable, just show info and stop
                return {
                    'name': _("Deletion Information"),
                    'type': 'ir.actions.act_window',
                    'res_model': 'cr.folder.delete.warning',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_category_id': self.id,
                        'default_message': message + _("\nNo other folder lines are available for deletion."),
                        'default_line_ids': [],
                    }
                }

            # Show warning wizard to confirm deletion of safe folders
            return {
                'name': _("Deletion Warning"),
                'type': 'ir.actions.act_window',
                'res_model': 'cr.folder.delete.warning',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_category_id': self.id,
                    'default_line_ids': [fields.Command.set(final_to_delete.ids)],
                    'default_message': message + _("\nDo you want to proceed with deleting the empty folders?"),
                }
            }

        # No untouchable folders in selection, delete everything selected
        if final_to_delete:
            self.write({
                'folder_structure_ids': [fields.Command.unlink(line.id) for line in final_to_delete]
            })
        return {'type': 'ir.actions.client', 'tag': 'reload'}
