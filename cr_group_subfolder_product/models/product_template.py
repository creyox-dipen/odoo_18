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
        """Count only the folder records linked to this product."""
        for product in self:
            product.folder_count = self.env['documents.document'].search_count([
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
                ('type', '=', 'folder'),
            ])
    

    def action_view_product_folders(self):
        self.ensure_one()

        root_folder = self.env['documents.document'].sudo().search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
            ('cr_is_product_root', '=', True),
        ], limit=1)
    
        action = self.env.ref('documents.document_action').sudo().read()[0]
        action.update({
            'name': _('Documents – %s') % self.name,
            'target': 'current',
            'context': {
                'searchpanel_default_folder_id': root_folder.id if root_folder else False,
                'default_res_model': 'product.template',
                'default_res_id': self.id,
            },
        })
        return action

    # def action_view_product_folders(self):
    #     """
    #     Open the native Documents module UI pre-navigated to this product's root folder.

    #     Uses the main ``documents.document_action`` action (which includes the proper
    #     kanban/list views with the search-panel sidebar) and sets
    #     ``searchpanel_default_folder_id`` so the sidebar automatically navigates
    #     into the product's root folder.  This allows users to browse sub-folders
    #     and open individual files the same way as the native Documents app.

    #     If no root folder exists yet (e.g. category has no structure), the action
    #     still opens the Documents app without pre-selecting a folder.

    #     :return: ir.actions.act_window dict
    #     """
    #     self.ensure_one()

    #     # Find the product's root (top-level) folder – the one without a parent folder
    #     # that is linked to this product.
    #     root_folder = self.env['documents.document'].search([
    #         ('type', '=', 'folder'),
    #         ('res_model', '=', 'product.template'),
    #         ('res_id', '=', self.id),
    #         ('folder_id', '=', False),
    #     ], limit=1)

    #     # Load the main Documents action and override its context so the search
    #     # panel sidebar pre-selects the product's root folder.
    #     action = self.env.ref('documents.document_action').sudo().read()[0]
    #     action.update({
    #         'name': _('Documents – %s') % self.name,
    #         'target': 'current',
    #         'context': {
    #             'searchpanel_default_folder_id': root_folder.id if root_folder else False,
    #             'default_res_model': 'product.template',
    #             'default_res_id': self.id,
    #         },
    #     })
    #     return action

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
        self.ensure_one()
        Document = self.env['documents.document']
    
        # Find or create the single product root folder
        root_folder = Document.sudo().search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', self.id),
            ('cr_is_product_root', '=', True),
        ], limit=1)
    
        if not root_folder:
            root_folder = Document.sudo().create({
                'name': self.name,
                'type': 'folder',
                'res_model': 'product.template',
                'res_id': self.id,
                'folder_id': False,
                'cr_is_product_root': True,
                'access_internal': 'edit',
                'access_via_link': 'none',
                'owner_id': self.env.user.id,
            })
    
        lines = categ.folder_structure_ids.sorted(key=lambda l: l.sequence)
        seq_to_doc = {}
    
        for line in lines:
            normalized_seq = line._get_normalized_sequence()
            existing_doc = Document.sudo().search([
                ('type', '=', 'folder'),
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.id),
                ('cr_category_folder_line_id', '=', line.id),
            ], limit=1)
    
            parent_doc = self._cr_find_parent_document(line, seq_to_doc)
            # Top-level lines (no parent) go under root_folder instead of False
            parent_folder_id = parent_doc.id if parent_doc else root_folder.id
    
            vals = {
                'name': line.name,
                'folder_id': parent_folder_id,
                'cr_category_folder_line_id': line.id,
            }
    
            if existing_doc:
                update_vals = {}
                if existing_doc.name != vals['name']:
                    update_vals['name'] = vals['name']
                if existing_doc.folder_id.id != parent_folder_id:
                    update_vals['folder_id'] = parent_folder_id
                if update_vals:
                    existing_doc.sudo().write(update_vals)
                doc = existing_doc
            else:
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
