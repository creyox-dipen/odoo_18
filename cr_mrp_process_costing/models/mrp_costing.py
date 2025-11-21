# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class MaterialCosting(models.Model):
    _name = 'material.costing'

    bom_id = fields.Many2one("mrp.bom")
    production_id = fields.Many2one("mrp.production")

    mat_operation_id = fields.Many2one('mrp.routing.workcenter', string="Operation")
    mat_product_id = fields.Many2one('product.template', string="Product")
    mat_planned_qty = fields.Integer("Planned Qty")
    mat_actual_qty = fields.Integer("Actual Qty",copy=False)
    mat_uom = fields.Char("UOM", default='Units')
    mat_cost_per_unit = fields.Float("Cost/Unit")
    mat_total_product_cost = fields.Float("Total Cost", compute="_find_mat_total_product_cost",readonly=1)
    mat_total_actual_product_cost = fields.Float("Total Actual Material Cost",readonly=1)

    @api.onchange("mat_planned_qty","mat_cost_per_unit")
    def _find_mat_total_product_cost(self):
        for record in self:
            record.mat_total_product_cost = record.mat_planned_qty * record.mat_cost_per_unit

class LabourCosting(models.Model):
    _name = 'labour.costing'

    bom_id = fields.Many2one("mrp.bom")
    production_id = fields.Many2one("mrp.production")

    lab_operation_id = fields.Many2one('mrp.routing.workcenter', string="Operation")
    lab_planned_hour = fields.Float("Planned Hour")
    lab_actual_hour = fields.Float("Actual Hour",copy=False)
    lab_cost_per_hour = fields.Float("Cost/Hour")
    lab_total_operation_cost = fields.Float("Total Cost", compute="_find_lab_total_operation_cost",readonly=1)
    lab_total_actual_operation_cost = fields.Float("Total Actual Cost",readonly=1)

    is_costing_by_work_center = fields.Boolean(default=False, compute="_find_is_costing_by_work_center")

    def _find_is_costing_by_work_center(self):
        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.costing_method_selection')
        for rec in self:
            if temp == 'work_center':
                rec.is_costing_by_work_center = True
            else:
                rec.is_costing_by_work_center = False

    @api.onchange("lab_planned_hour", "lab_cost_per_hour")
    def _find_lab_total_operation_cost(self):
        for record in self:
            record.lab_total_operation_cost = record.lab_planned_hour * record.lab_cost_per_hour

class OverheadCosting(models.Model):
    _name = 'overhead.costing'

    bom_id = fields.Many2one("mrp.bom")
    production_id = fields.Many2one("mrp.production")

    ove_operation_id = fields.Many2one('mrp.routing.workcenter', string="Operation")
    ove_planned_hour = fields.Float("Planned Hour")
    ove_actual_hour = fields.Float("Actual Hour",copy=False)
    ove_cost_per_hour = fields.Float("Cost/Hour")
    ove_total_operation_cost = fields.Float("Total Cost", compute="_find_ove_total_operation_cost",readonly=1)
    ove_total_actual_operation_cost = fields.Float("Total Actual Cost",readonly=1)

    is_costing_by_work_center = fields.Boolean(default=False, compute="_find_is_costing_by_work_center")

    def _find_is_costing_by_work_center(self):
        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.costing_method_selection')
        for rec in self:
            if temp == 'work_center':
                rec.is_costing_by_work_center = True
            else:
                rec.is_costing_by_work_center = False

    @api.onchange("ove_planned_hour", "ove_cost_per_hour")
    def _find_ove_total_operation_cost(self):
        for record in self:
            record.ove_total_operation_cost = record.ove_planned_hour * record.ove_cost_per_hour
