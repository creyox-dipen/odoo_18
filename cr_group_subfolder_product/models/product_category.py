# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, _
from odoo.exceptions import UserError


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
        Override write to detect deleted folder lines and apply safe-delete logic
        on documents.document folders for all products in this category.

        When a Command.DELETE or Command.UNLINK is detected in folder_structure_ids,
        we collect the affected folder lines, then for each product that uses this
        category we delete only the folders (and their sub-folders) that contain
        no documents. Folders with documents are left untouched.
        """
        # Collect lines being deleted before the write
        deleted_line_ids = []
        if 'folder_structure_ids' in vals:
            for cmd in vals['folder_structure_ids']:
                # Command.DELETE (2) or Command.UNLINK (3)
                if cmd[0] in (2, 3) and cmd[1]:
                    deleted_line_ids.append(cmd[1])

        # Fetch line data before it is deleted
        deleted_lines = self.env['cr.category.folder.line'].browse(deleted_line_ids)
        # Map: (category_id, line_sequence_name) for matching folders
        lines_info = {
            line.id: (line.category_id.id, line.name, line.sequence)
            for line in deleted_lines
        }

        result = super().write(vals)

        # Safe-delete folders for affected products
        if lines_info:
            for category in self:
                products = self.env['product.template'].search([
                    ('categ_id', '=', category.id),
                ])
                for product in products:
                    for line_id, (cat_id, fname, fseq) in lines_info.items():
                        if cat_id != category.id:
                            continue
                        # Find root folder of this product that matches the line
                        existing_folder = self.env['documents.document'].search([
                            ('type', '=', 'folder'),
                            ('res_model', '=', 'product.template'),
                            ('res_id', '=', product.id),
                            ('name', '=', fname),
                        ], limit=1)
                        if existing_folder:
                            existing_folder._cr_safe_delete_folder()

        return result
