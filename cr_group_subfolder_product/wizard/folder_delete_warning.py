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
    message = fields.Char(
        string='Warning Message',
        default=lambda self: _(
            'Some subfolders contain files. Do you want to continue or cancel?'
        ),
        readonly=True,
    )

    def action_confirm(self):
        """
        Perform the force deletion of the folder lines and their related folders.
        """
        self.ensure_one()
        category = self.category_id
        # Prepare deletion commands for the category
        commands = [(2, line.id, 0) for line in self.line_ids]
        
        # Perform write on category with force context
        # This will trigger the ProductCategory.write logic which handles
        # the documents.document deletion safely (or forcefully since we skip the check)
        category.with_context(cr_force_delete_lines=True).write({
            'folder_structure_ids': commands
        })

        # Return action to reload the category page
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_cancel(self):
        """Do nothing and close."""
        return {'type': 'ir.actions.act_window_close'}
