# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api

class DuplicateWiz(models.TransientModel):
    _name = "duplicate.wiz"
    _description = "duplicate data wizard"

    # action = fields.Selection([('none', 'None'), ('delete', 'Delete'), ('archived', 'Archived')], string="Action on Duplicate Record")
    is_selected_records = fields.Boolean(string='Selected Records Only')
    field_ids = fields.Many2many(comodel_name='ir.model.fields', string='Fields(s)', domain=lambda self: self.get_fields(), required=True)

    def get_fields(self):
        model_id = self.env['ir.model'].search([('model', '=', 'sale.order')], limit=1)
        return [('model_id', '=', model_id.id)]

    def action_find_duplicates(self):
        print(self.is_selected_records)
        print(self._context.get('active_ids'))
        print(self._context.get('active_model'))
        print(self)
        if self.is_selected_records:

