# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)


class CrFolderChangeWarning(models.TransientModel):
    """
    Warning wizard displayed when a user changes a product's category
    and the existing folder structure for that product contains documents.

    The user must confirm to proceed with the category change and folder
    replacement, or cancel to keep the current structure.
    """

    _name = 'cr.folder.change.warning'
    _description = 'Folder Change Warning'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    new_categ_id = fields.Many2one(
        'product.category',
        string='New Category',
        required=True,
    )
    message = fields.Char(
        string='Warning Message',
        default=lambda self: _(
            'The current folder structure for this product contains documents. '
            'Changing the category will delete ALL existing folders (including those with files) '
            'and create a new folder structure. '
            'FILES IN THESE FOLDERS MAY BE LOST. '
            'Do you want to continue?'
        ),
        readonly=True,
    )

    def action_confirm(self):
        """
        Confirm the category change. 
        - Updates the product category in the database.
        - Deletes the OLD folder structure (even if it contains files).
        - Creates the NEW folder structure.
        """
        self.ensure_one()
        product = self.product_id
        new_categ = self.new_categ_id

        # 1. Update the product category (bypass safe check in write via context)
        product.with_context(cr_skip_folder_check=True).write({
            'categ_id': new_categ.id
        })

        # 2. Force delete old folders for this product
        # (We delete all top-level folders linked to this product)
        old_folders = self.env['documents.document'].sudo().search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', product.id),
        ])
        # We use unlink() directly to ensure everything is gone as confirmed
        old_folders.sudo().unlink()

        # 3. Create new structure
        if new_categ.folder_structure_ids:
            product._cr_create_folder_structure(new_categ)

        # Return action to reload the product page
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_cancel(self):
        """
        Cancel the category change dialog. 
        Returns a reload action to ensure the UI reverts the unsaved category change.
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
