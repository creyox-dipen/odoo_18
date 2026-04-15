# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, _

class CrFolderDeleteWarning(models.TransientModel):
    """
    Wizard shown when a user tries to delete a folder structure line
    that has existing documents in its related folders on products.
    """
    _name = 'cr.folder.delete.warning'
    _description = 'Folder Line Delete Warning'

    category_id = fields.Many2one('product.category', string='Category', required=True)
    line_ids = fields.Many2many('cr.category.folder.line', string='Lines to Delete')
    message = fields.Text(
        string='Warning Message',
        readonly=True,
    )

    def action_confirm(self):
        """
        Perform selective deletion:
        - Delete empty folders from individual products.
        - Preserve folders that contain documents.
        - Only delete the template line if ALL its folders were deleted across all products.
        """
        self.ensure_one()
        if not self.line_ids or self.message and "skipped" in self.message:
            return {'type': 'ir.actions.act_window_close'}
            
        category = self.category_id
        lines_skipped = []
        
        # We process lines to check contents across all products
        # Sorting by sequence length (depth) descending ensures children are handled before parents
        sorted_lines = self.line_ids.sorted(key=lambda l: len(l.sequence.split('.')), reverse=True)
        
        Document = self.env['documents.document'].sudo()
        
        for line in sorted_lines:
            # Find all product folders linked to this template line
            folders = Document.search([
                ('cr_category_folder_line_id', '=', line.id),
            ])
            
            for folder in folders:
                if not folder._cr_has_documents():
                    # Folder is empty, safe to delete for this product
                    folder.unlink()
            
            # After processing all products, check if the line can be removed from template
            remaining_count = Document.search_count([
                ('cr_category_folder_line_id', '=', line.id),
            ])
            
            if remaining_count == 0:
                # No product is using this folder anymore, delete from category structure
                line.unlink()
            else:
                # Some products still have files here
                lines_skipped.append(f"{line.name} ({line.sequence})")

        if lines_skipped:
            # Update message and clear line_ids to show 'Close' button only
            self.write({
                'message': _("There are items inside of the %s folder(s) in some products so it will be skipped.") % ", ".join(lines_skipped),
                'line_ids': [fields.Command.clear()],
            })
            return {
                'name': _("Deletion Information"),
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_cancel(self):
        """Do nothing and close."""
        return {'type': 'ir.actions.act_window_close'}
