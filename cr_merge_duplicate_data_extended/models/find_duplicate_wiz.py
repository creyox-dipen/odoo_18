# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api


class DuplicateWiz(models.TransientModel):
    _name = "duplicate.wiz"
    _description = "Duplicate Data Wizard"

    is_selected_records = fields.Boolean(string='Selected Records Only')
    field_ids = fields.Many2many(
        comodel_name='ir.model.fields',
        string='Field(s)',
        domain=lambda self: self.get_fields(),
        required=True
    )
    actions = fields.Selection([
        ('none', 'None'),
        ('delete', 'Delete'),
        ('archive', 'Archive')
    ], string="Action on Duplicate Records", default='none')

    duplicate_lines = fields.One2many(
        'duplicate.wiz.line', 'wizard_id',
        string='Duplicate Records'
    )

    def get_fields(self):
        model_id = self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1)
        return [('model_id', '=', model_id.id)]

    def action_find_duplicates(self):
        """
        Finds the duplicate value from the records
        """
        field_names = self.field_ids.mapped('name')

        return {
            'name': 'Grouped Records',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'list',
            'target': 'current',
            'domain': [('id', 'in', self._context.get('active_ids'))],
            'context': {
                'group_by': field_names,
            }
        }

    @api.model
    def default_get(self, fields_list):
        """Fill wizard lines dynamically with active_ids"""
        print(self.env.context.get("active_ids", []))
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        records = self.env["res.partner"].browse(active_ids)

        line_vals = []
        for rec in records:
            line_vals.append((0, 0, {
                "record_id": rec.id,
                "display_name": rec.complete_name,
                "is_original": False,
            }))
        res["duplicate_lines"] = line_vals
        return res


    def merge_data(self):
        if self.actions == 'delete':
            self.duplicate_lines.mapped('partner_id').unlink()
        elif self.actions == 'archive':
            self.duplicate_lines.mapped('partner_id').write({'active': False})
        # Add merge logic here if needed
        return {'type': 'ir.actions.act_window_close'}



class DuplicateWizLine(models.TransientModel):
    _name = "duplicate.wiz.line"
    _description = "Duplicate Wizard Line"

    wizard_id = fields.Many2one("duplicate.wiz", ondelete="cascade")
    is_original = fields.Boolean("Original Record")
    record_id = fields.Integer("Record ID")
    display_name = fields.Char("Display Name")