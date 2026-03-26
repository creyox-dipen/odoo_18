# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, Command, _
from odoo.exceptions import UserError, RedirectWarning
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    """
    Extends product.template to automatically manage documents.document folder
    hierarchies based on the product category's folder_structure_ids.

    When a product is assigned (or changes) a category, the folder hierarchy
    defined in the category is auto-created in documents.document as
    type='folder' records linked to this product via res_model/res_id.

    Category change logic:
      - If old folders have documents → show a warning wizard (user must confirm)
      - If old folders have no documents → silently replace with new structure
    """

    _inherit = 'product.template'

    cr_document_folder_ids = fields.One2many(
        'documents.document',
        compute='_compute_cr_document_folder_ids',
        string='Product Folders',
        help='Folder hierarchy in Documents for this product.',
    )
    folder_count = fields.Integer(
        string='Folder Count',
        compute='_compute_folder_count',
    )

    def _compute_folder_count(self):
        """Count all documents (folders and files) linked to this product."""
        for product in self:
            product.folder_count = self.env['documents.document'].search_count([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
            ])

    def action_view_product_folders(self):
        """Return an action to view all documents/folders linked to this product."""
        self.ensure_one()
        return {
            'name': _('Folders'),
            'type': 'ir.actions.act_window',
            'res_model': 'documents.document',
            'view_mode': 'kanban,list',
            'domain': [
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_res_model': 'product.template',
                'default_res_id': self.id,
                'search_default_res_model': 'product.template',
                'search_default_res_id': self.id,
                'search_default_folder_id': False,
            },
            'help': _("""<p class="o_view_nocontent_smiling_face">
                Upload documents to this product.
            </p>"""),
            'target': 'current',
        }

    def _compute_cr_document_folder_ids(self):
        """Compute the top-level document folders linked to this product."""
        DocumentDocument = self.env['documents.document']
        for product in self:
            product.cr_document_folder_ids = DocumentDocument.search([
                ('type', '=', 'folder'),
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
                ('folder_id', '=', False),  # top-level only
            ])

    def write(self, vals):
        """
        Override write to enforce folder structure replacement rules.

        - If no documents exist in old folders: silent replacement.
        - If documents exist:
            - If confirmed via wizard (cr_skip_folder_check): continue.
            - Otherwise: raise error (fallback if onchange was bypassed).
        """
        if 'categ_id' in vals:
            for product in self:
                if product.categ_id.id == vals['categ_id']:
                    continue

                if product._cr_has_any_documents():
                    if not self.env.context.get('cr_skip_folder_check'):
                        # Provide a button to open the warning wizard
                        action = self.env.ref('cr_group_subfolder_product.action_cr_folder_change_warning')
                        raise RedirectWarning(
                            _("The current folders for product '%s' contain documents. "
                              "Changing the category will cause folder replacement.") % product.name,
                            action.id,
                            _("Continue by replacing older structure"),
                            additional_context={
                                'default_product_id': product.id,
                                'default_new_categ_id': vals['categ_id'],
                            }
                        )

        # Proceed with save
        result = super().write(vals)

        if 'categ_id' in vals:
            for product in self:
                # If we reached here, either it was safe or it was confirmed.
                # Silent replacement for safe ones (no documents)
                if not product._cr_has_any_documents():
                    # Delete all managed folders for this product
                    old_folders = self.env['documents.document'].search([
                        ('type', '=', 'folder'),
                        ('res_model', '=', 'product.template'),
                        ('res_id', '=', product.id),
                    ])
                    # We can't easily know the exact "old" category structure here
                    # as it's already updated, so we delete based on line association
                    # or product association.
                    for folder in old_folders:
                        if folder.exists():
                            folder._cr_safe_delete_folder()
                    if product.categ_id.folder_structure_ids:
                        product._cr_create_folder_structure(product.categ_id)

        return result

    @api.onchange('categ_id')
    def _onchange_categ_id_warning(self):
        """
        Trigger the confirmation wizard if the user changes the category
        of a product that has existing documents in its folders.
        """
        if not self.categ_id or not self._origin.id:
            return

        # Use _origin to check current state in DB
        if self.categ_id != self._origin.categ_id:
            if self._origin._cr_has_any_documents():
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'cr.folder.change.warning',
                    'view_mode': 'form',
                    'target': 'new',
                    'name': _('Warning: Folder Structure Change'),
                    'context': {
                        'default_product_id': self._origin.id,
                        'default_new_categ_id': self.categ_id.id,
                    }
                }

    def _cr_has_any_documents(self):
        """Helper to check if any managed folder for this product has documents."""
        self.ensure_one()
        folders = self.env['documents.document'].search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
        ])
        return any(f._cr_has_documents() for f in folders)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to auto-create folder structure when a product is
        created with a category that has folder_structure_ids configured.

        :param list[dict] vals_list: list of field value dicts for new products
        :return: newly created product.template records
        """
        records = super().create(vals_list)
        for product in records:
            if product.categ_id and product.categ_id.folder_structure_ids:
                product._cr_create_folder_structure(product.categ_id)
        return records

    def _cr_handle_category_change(self, old_categ, new_categ):
        """
        Handle the logic when a product's category is changed.

        Checks if old folders have any documents. If yes, opens a warning
        wizard for the user to confirm. If no, silently replaces folders.

        :param product.category old_categ: the previous category
        :param product.category new_categ: the new category
        """
        self.ensure_one()
        old_folders = self.env['documents.document'].search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
        ])
        has_docs = any(f._cr_has_documents() for f in old_folders if f.type == 'folder')

        if has_docs:
            # Return action to open the warning wizard — the caller in JS
            # context will catch this via _cr_category_change_warning flag
            # We store intent on the product for the wizard to act upon
            self.with_context(
                cr_pending_categ_id=new_categ.id,
                cr_old_categ_id=old_categ.id,
            )
            # Create wizard record and return action
            wizard = self.env['cr.folder.change.warning'].create({
                'product_id': self.id,
                'new_categ_id': new_categ.id,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cr.folder.change.warning',
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
                'name': _('Warning: Folder Structure Change'),
            }
        else:
            # No documents — safe to replace directly
            old_folders._cr_safe_delete_folder()
            if new_categ.folder_structure_ids:
                self._cr_create_folder_structure(new_categ)

    def _cr_create_folder_structure(self, categ):
        """
        Create or update the folder hierarchy for this product based on the
        category's folder_structure_ids.

        This method is idempotent: it checks for existing folders linked to
        the same category line and updates them (name/parent) if necessary.

        :param product.category categ: the category with folder_structure_ids
        """
        self.ensure_one()
        Document = self.env['documents.document']
        # Sort naturally to ensure parents are processed first
        lines = categ.folder_structure_ids.sorted(key=lambda l: l.sequence)

        # Map: normalized sequence tuple → documents.document (existing or new)
        seq_to_doc = {}

        for line in lines:
            normalized_seq = line._get_normalized_sequence()
            # Find existing folder for this specific line and product
            existing_doc = Document.sudo().search([
                ('type', '=', 'folder'),
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.id),
                ('cr_category_folder_line_id', '=', line.id),
            ], limit=1)

            parent_doc = self._cr_find_parent_document(line, seq_to_doc)
            vals = {
                'name': line.name,
                'folder_id': parent_doc.id if parent_doc else False,
                'cr_category_folder_line_id': line.id,
            }

            if existing_doc:
                # Update existing folder if info changed
                update_vals = {}
                if existing_doc.name != vals['name']:
                    update_vals['name'] = vals['name']
                if existing_doc.folder_id != vals['folder_id']:
                    update_vals['folder_id'] = vals['folder_id']

                if update_vals:
                    existing_doc.sudo().write(update_vals)
                doc = existing_doc
            else:
                # Create new folder
                vals.update({
                    'type': 'folder',
                    'res_model': 'product.template',
                    'res_id': self.id,
                    'access_internal': 'edit',
                    'access_via_link': 'none',
                    'owner_id': self.env.user.id,
                })
                doc = Document.sudo().create(vals)

            seq_to_doc[normalized_seq] = doc

    def _cr_find_parent_document(self, line, seq_to_doc):
        """
        Determine the parent documents.document folder based on the dot-notation.

        Example:
          - sequence '1.1.1' -> parent sequence '1.1'
          - sequence '1.1'   -> parent sequence '1.0' (or whatever was configured)

        :param cr.category.folder.line line: the folder line
        :param dict seq_to_doc: mapping of normalized sequence tuple → documents.document
        :return: documents.document or None
        """
        parent_seq = line._get_parent_sequence()
        if parent_seq:
            return seq_to_doc.get(parent_seq)
        return None
