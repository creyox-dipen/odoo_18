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
        required=True,
    )
    actions = fields.Selection([
        ('none', 'None'),
        ('delete', 'Delete'),
        ('archive', 'Archive')
    ], string="Action on Duplicate Records", default='none')

    duplicate_lines = fields.One2many(
        'duplicate.wiz.line', 'wizard_id',
        string='Duplicate Records',
        store=True
    )

    def get_fields(self):
        model_id = self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1)
        return [('model_id', '=', model_id.id)]

    def action_find_duplicates(self):
        """
        Finds the duplicate value from the records
        """
        active_ids = []
        if not self.is_selected_records:
            active_ids = self.env[self._context.get('active_model')].search([('id', 'not in', self._context.get('active_ids'))]).ids
        else :
            active_ids = self._context.get('active_ids')
        field_names = self.field_ids.mapped('name')
        return {
            'name': 'Grouped Records',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'list',
            'target': 'current',
            'domain': [('id', 'in', active_ids)],
            'context': {
                'group_by': field_names,
            }
        }

    @api.model
    def default_get(self, fields_list):
        """
        Fill wizard lines dynamically with active_ids
        """
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        records = self.env["res.partner"].browse(active_ids)

        line_vals = []
        for rec in records:
            line_vals.append((0, 0, {
                "record_id": rec.id,
                "display_name": rec.display_name,
                "is_original": False,
            }))
        res["duplicate_lines"] = line_vals
        return res

    def merge_data(self):
        lines = self.duplicate_lines
        if lines:
            action_records = lines.filtered(lambda line: not line.is_original).mapped('record_id')
            records = self.env['res.partner'].browse(action_records)
            if self.actions == 'delete':
                records.mapped(lambda rec: rec.unlink())
            elif self.actions == 'archive':
                records.write({'active': False})

    def create(self, vals):
        if vals.get("duplicate_lines"):
            active_ids = self.env.context.get("active_ids", [])
            records = self.env["res.partner"].browse(active_ids)
            record_map = {rec.id: rec.display_name for rec in records}

            new_lines = []
            for command in vals["duplicate_lines"]:
                if command[0] == 0:
                    line_data = command[2]

                    if not line_data.get("record_id") and active_ids:
                        rec_id = active_ids.pop(0)  # consume sequentially
                        line_data["record_id"] = rec_id
                        line_data["display_name"] = record_map.get(rec_id)

                    new_lines.append((0, 0, line_data))
                else:
                    new_lines.append(command)

            vals["duplicate_lines"] = new_lines

        return super().create(vals)


class DuplicateWizLine(models.TransientModel):
    _name = "duplicate.wiz.line"
    _description = "Duplicate Wizard Line"

    wizard_id = fields.Many2one("duplicate.wiz", store=True)
    is_original = fields.Boolean("Original Record", store=True)
    record_id = fields.Integer("Record ID", store=True)
    display_name = fields.Char("Display Name", store=True)
