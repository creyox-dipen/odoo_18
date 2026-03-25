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
            'Changing the category will delete all existing folders (without documents) '
            'and create a new folder structure. '
            'Folders with documents will be preserved. '
            'Do you want to continue?'
        ),
        readonly=True,
    )

    def action_confirm(self):
        """
        Confirm the category change. Safely delete old folders (those without
        documents) and create the new folder structure based on the new category.

        Folders that contain documents are preserved even after confirmation.

        :return: dict — window close action
        """
        self.ensure_one()
        product = self.product_id
        new_categ = self.new_categ_id

        # Safe-delete old top-level folders for this product
        old_folders = self.env['documents.document'].search([
            ('type', '=', 'folder'),
            ('res_model', '=', 'product.template'),
            ('res_id', '=', product.id),
            ('folder_id', '=', False),  # top-level only (children handled recursively)
        ])
        for folder in old_folders:
            folder._cr_safe_delete_folder()

        # Create new structure
        if new_categ.folder_structure_ids:
            product._cr_create_folder_structure(new_categ)

        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        """
        Cancel the category change dialog. No changes are made.

        :return: dict — window close action
        """
        return {'type': 'ir.actions.act_window_close'}
