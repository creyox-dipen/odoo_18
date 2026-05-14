# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class CrFolderDeleteWarning(models.TransientModel):
    _name = 'cr.folder.delete.warning'
    _description = 'Safe Folder Delete Warning'

    message = fields.Text(string='Warning Message', readonly=True)
    line_ids = fields.Many2many('project.folder.structure', string='Lines to Delete')

    def action_confirm(self):
        """Proceed with deleting empty folder instances project-by-project."""
        self.ensure_one()
        candidates = self.line_ids
        
        # 1. Find every physical folder instance across all projects
        all_folders = self.env['documents.document'].sudo().search([
            ('cr_project_folder_line_id', 'in', candidates.ids)
        ])
        
        # 2. Try to delete each physical folder instance individually.
        for folder in all_folders:
            if folder.exists():
                folder._cr_safe_delete_folder()
            
        # 3. After the individual project cleanup, check if any project still has
        # these folders (because they had files).
        remaining_folders = self.env['documents.document'].sudo().search([
            ('cr_project_folder_line_id', 'in', candidates.ids)
        ])
        lines_still_in_use = remaining_folders.mapped('cr_project_folder_line_id')
        
        # 4. Remove the lines from the Global Template ONLY if they are now 
        # completely gone from every project in the system.
        safe_to_unlink_from_template = candidates - lines_still_in_use
        if safe_to_unlink_from_template:
            safe_to_unlink_from_template.unlink()
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_cancel(self):
        """Simply close the wizard."""
        return {'type': 'ir.actions.act_window_close'}
