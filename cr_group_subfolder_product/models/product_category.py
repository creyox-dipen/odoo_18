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
        Override write to detect changes in folder structure and propagate
        them to all products in this category.

        - Deletions: If a folder line is removed, we safely delete its
          matching folders on all products (folder must be empty).
        - Additions/Updates: Any addition or renaming in the structure
          is synced to all products.
        """
        # 1. Collect lines being deleted to find folders before lines are gone
        deleted_line_ids = []
        if 'folder_structure_ids' in vals:
            for cmd in vals['folder_structure_ids']:
                # Command.DELETE (2) or Command.UNLINK (3)
                if cmd[0] in (2, 3) and cmd[1]:
                    deleted_line_ids.append(cmd[1])

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
        for folder in folders_to_delete:
            if folder.exists():
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
