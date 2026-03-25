# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, Command, _
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
        """Count all document folders linked to this product (all levels)."""
        for product in self:
            product.folder_count = self.env['documents.document'].search_count([
                ('type', '=', 'folder'),
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
            ])

    def action_view_product_folders(self):
        """Return an action to view all document folders linked to this product."""
        self.ensure_one()
        return {
            'name': _('Product Folders'),
            'type': 'ir.actions.act_window',
            'res_model': 'documents.document',
            'view_mode': 'list,form',
            'domain': [
                ('type', '=', 'folder'),
                ('res_model', '=', 'product.template'),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_type': 'folder',
                'default_res_model': 'product.template',
                'default_res_id': self.id,
                'search_default_folder_id': False,  # Show all, not just top-level
            },
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
        Override write to detect category changes and trigger folder sync.

        When categ_id changes:
          - Check if any existing folders for this product have documents
          - If YES: open warning wizard, do not change yet
          - If NO: delete old folders, create new structure

        :param dict vals: fields being written
        :return: result of super().write()
        """
        old_categories = {}
        if 'categ_id' in vals:
            for product in self:
                old_categories[product.id] = product.categ_id

        result = super().write(vals)

        if 'categ_id' in vals:
            for product in self:
                old_categ = old_categories.get(product.id)
                new_categ = product.categ_id
                if old_categ and old_categ != new_categ:
                    product._cr_handle_category_change(old_categ, new_categ)

        return result

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
        Create the folder hierarchy (documents.document records with type='folder')
        for this product based on the given category's folder_structure_ids.

        Hierarchy is determined by the sequence field using dot-notation:
          - 1.0  => top-level
          - 1.1  => parent is 1.0
          - 1.1.1 => parent is 1.1
        
        Lines are sorted by sequence to ensure parents are created before children.

        :param product.category categ: the category with folder_structure_ids
        """
        self.ensure_one()
        Document = self.env['documents.document']
        # Sort naturally to ensure parents are processed first (1.1 before 1.1.1)
        lines = categ.folder_structure_ids.sorted(key=lambda l: l.sequence)

        # Map: normalized sequence tuple → created documents.document id
        seq_to_doc = {}

        for line in lines:
            normalized_seq = line._get_normalized_sequence()
            parent_doc = self._cr_find_parent_document(line, seq_to_doc)
            vals = {
                'name': line.name,
                'type': 'folder',
                'res_model': 'product.template',
                'res_id': self.id,
                'folder_id': parent_doc.id if parent_doc else False,
                'cr_category_folder_line_id': line.id,
                'access_internal': 'edit',
                'access_via_link': 'none',
                'owner_id': self.env.user.id,
            }
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
