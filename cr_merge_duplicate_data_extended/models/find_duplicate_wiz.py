# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class DuplicateWiz(models.TransientModel):
    _name = "duplicate.wiz"
    _description = "duplicate data wizard"

    # action = fields.Selection([('none', 'None'), ('delete', 'Delete'), ('archived', 'Archived')], string="Action on Duplicate Record")
    is_selected_records = fields.Boolean(string='Selected Records Only')
    field_ids = fields.Many2many(comodel_name='ir.model.fields', string='Fields(s)', domain=lambda self: self.get_fields(), required=True)
    actions = fields.Selection([('none', 'None'), ('delete', 'Delete'), ('archive', 'Archive')], string="Action on Duplicate Records",  default='none')

    def get_fields(self):
        model_id = self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1)
        return [('model_id', '=', model_id.id)]

    def action_find_duplicates(self):
        """
        This method finds the duplicate value from the records
        """
        field_names = self.field_ids.mapped('name')
        return {
            'name': 'Grouped Records',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'list',
            'target': 'current',
            'context': {
                'group_by': field_names,
            }
        }
