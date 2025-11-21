# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, fields, models

class MrpBOM(models.Model):
    _inherit = 'mrp.bom'

    material_costing_ids = fields.One2many('material.costing', 'bom_id')
    labour_costing_ids = fields.One2many('labour.costing', 'bom_id')
    overhead_costing_ids = fields.One2many('overhead.costing', 'bom_id')

    mat_total_cost = fields.Float("Total Material Cost", compute="_find_mat_total_cost")
    lab_total_cost = fields.Float("Total Labour Cost", compute="_find_lab_total_cost")
    ove_total_cost = fields.Float("Total Overhead Cost", compute="_find_ove_total_cost")

    total_cost = fields.Float("Total Cost",compute="_find_total_cost")

    @api.depends('material_costing_ids.mat_total_product_cost')
    def _find_mat_total_cost(self):
        for bom in self:
            total_cost = 0
            for costing in bom.material_costing_ids:
                total_cost += costing.mat_total_product_cost
            bom.mat_total_cost = total_cost

    @api.depends('labour_costing_ids.lab_total_operation_cost')
    def _find_lab_total_cost(self):
        for bom in self:
            total_cost = 0
            for costing in bom.labour_costing_ids:
                total_cost += costing.lab_total_operation_cost
            bom.lab_total_cost = total_cost

    @api.depends('overhead_costing_ids.ove_total_operation_cost')
    def _find_ove_total_cost(self):
        for bom in self:
            total_cost = 0
            for costing in bom.overhead_costing_ids:
                total_cost += costing.ove_total_operation_cost
            bom.ove_total_cost = total_cost

    @api.depends('mat_total_cost','lab_total_cost','ove_total_cost')
    def _find_total_cost(self):
        self.total_cost = self.mat_total_cost + self.lab_total_cost + self.ove_total_cost

    """ TO AUTO POPULATE THE PRODUCTS FROM COMPONENTS TO DIRECT MATERIAL COST """
    @api.onchange('bom_line_ids')
    def auto_populate_products_in_material_cost(self):
        commands = [(5, 0, 0)]  # Clear existing material costing lines
        for line in self.bom_line_ids:
            if line.product_id:
                product_tmpl = line.product_id.product_tmpl_id
                vals = {
                    'mat_product_id': product_tmpl.id,
                    'mat_planned_qty': line.product_qty,
                }
                commands.append((0, 0, vals))
        return {'value': {'material_costing_ids': commands}}

    """ TO AUTO CALCULATE LABOUR COST BASED ON WORK CENTER """
    @api.onchange('labour_costing_ids')
    def auto_calc_labour_costing_from_work_center(self):
        config = self.env['ir.config_parameter'].sudo()
        method = config.get_param('cr_mrp_process_costing.costing_method_selection')

        if method == 'work_center':
            for line in self.labour_costing_ids:
                if line.lab_operation_id:
                    line.lab_cost_per_hour = self.labour_costing_ids.lab_operation_id.workcenter_id.labour_cost_per_hour


    """ TO AUTO CALCULATE OVERHEAD COST BASED ON WORK CENTER """
    @api.onchange('overhead_costing_ids')
    def auto_calc_overhead_costing_from_work_center(self):
        config = self.env['ir.config_parameter'].sudo()
        method = config.get_param('cr_mrp_process_costing.costing_method_selection')

        if method == 'work_center':
            for line in self.overhead_costing_ids:
                if line.ove_operation_id:
                    line.ove_cost_per_hour = self.overhead_costing_ids.ove_operation_id.workcenter_id.overhead_cost_per_hour