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
        Perform the deletion of the folder lines that were identified as empty.
        """
        self.ensure_one()
        if not self.line_ids:
            return {'type': 'ir.actions.act_window_close'}
            
        category = self.category_id
        # Prepare deletion commands for the category
        commands = [fields.Command.unlink(line.id) for line in self.line_ids]
        
        # Perform write on category with force context
        # We use cr_force_delete_lines=True because we already identified these as safe 
        # to delete or we intend to delete them regardless of sub-logic.
        category.with_context(cr_force_delete_lines=True).write({
            'folder_structure_ids': commands
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_cancel(self):
        """Do nothing and close."""
        return {'type': 'ir.actions.act_window_close'}
