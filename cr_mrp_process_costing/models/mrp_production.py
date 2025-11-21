# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, fields, models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    material_costing_ids = fields.One2many('material.costing', 'production_id', copy=True)
    labour_costing_ids = fields.One2many('labour.costing', 'production_id', copy=True)
    overhead_costing_ids = fields.One2many('overhead.costing', 'production_id', copy=True)

    mat_total_cost = fields.Float("Estimated Material Cost")
    lab_total_cost = fields.Float("Estimated Labour Cost")
    ove_total_cost = fields.Float("Estimated Overhead Cost")

    mat_total_actual_cost = fields.Float("Actual Material Cost", compute="_find_mat_total_actual_cost")
    lab_total_actual_cost = fields.Float("Actual Labour Cost", compute="_find_lab_total_actual_cost")
    ove_total_actual_cost = fields.Float("Actual Overhead Cost", compute="_find_ove_total_actual_cost")

    total_cost = fields.Float("Estimated Total Cost")
    actual_total_cost = fields.Float("Actual Total Cost", compute="_find_actual_total_cost")
    product_unit_cost = fields.Float(string="Product Unit Cost")

    is_costing_by_work_center = fields.Boolean(default=False, compute="_find_is_costing_by_work_center")
    is_journal_entry = fields.Boolean(compute="_find_is_journal_entry")

    material_cost_debit_account_id = fields.Many2one('account.account', compute="_find_material_cost_debit_account_id")
    labour_cost_debit_account_id= fields.Many2one('account.account', compute="_find_labour_cost_debit_account_id")
    overhead_cost_debit_account_id = fields.Many2one('account.account', compute="_find_overhead_cost_debit_account_id")
    total_cost_debit_account_id = fields.Many2one('account.account', compute="_find_total_cost_debit_account_id")

    material_cost_credit_account_id = fields.Many2one('account.account',
                                                      compute="_find_material_cost_credit_account_id")
    labour_cost_credit_account_id = fields.Many2one('account.account', compute="_find_labour_cost_credit_account_id")
    overhead_cost_credit_account_id = fields.Many2one('account.account',
                                                      compute="_find_overhead_cost_credit_account_id")
    total_cost_credit_account_id = fields.Many2one('account.account', compute="_find_total_cost_credit_account_id")

    #Functions to find the Accounts from settings
    def _find_material_cost_debit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.material_costing_debit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.material_cost_debit_account_id = temp_account

    def _find_labour_cost_debit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.labour_costing_debit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.labour_cost_debit_account_id = temp_account

    def _find_overhead_cost_debit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.overhead_costing_debit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.overhead_cost_debit_account_id = temp_account

    def _find_total_cost_debit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.total_costing_debit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.total_cost_debit_account_id = temp_account

    def _find_material_cost_credit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.material_costing_credit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.material_cost_credit_account_id = temp_account

    def _find_labour_cost_credit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.labour_costing_credit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.labour_cost_credit_account_id = temp_account

    def _find_overhead_cost_credit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.overhead_costing_credit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.overhead_cost_credit_account_id = temp_account

    def _find_total_cost_credit_account_id(self):
        temp_id = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.total_costing_credit_account_id')
        temp_account = self.env['account.account'].browse(int(temp_id))
        for rec in self:
            if temp_account:
                rec.total_cost_credit_account_id = temp_account

    #function to check the is_journal_entry is true or not
    def _find_is_journal_entry(self):
        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.is_journal_entry')
        for rec in self:
            if temp:
                rec.is_journal_entry = True
            else:
                rec.is_journal_entry = False

    #function to check the is_costing_by_work_center is true or not
    def _find_is_costing_by_work_center(self):
        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.costing_method_selection')
        for rec in self:
            if temp == 'work_center':
                rec.is_costing_by_work_center = True
            else:
                rec.is_costing_by_work_center = False

    #function to set the data in MO according to BOM
    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        if self.bom_id:
            self.material_costing_ids = [(5, 0, 0)]
            self.labour_costing_ids = [(5, 0, 0)]
            self.overhead_costing_ids = [(5, 0, 0)]
            self.move_raw_ids = [(5, 0, 0)]

            bom = self.bom_id

            bom_line_data = [
                (0, 0, {
                    'product_id': bom_line.product_id.id,
                    'product_uom_qty': bom_line.product_qty,
                }) for bom_line in bom.bom_line_ids
            ]
            self.move_raw_ids = bom_line_data

            material_costing_data = [
                (0, 0, {
                    'mat_operation_id': material.mat_operation_id.id,
                    'mat_product_id': material.mat_product_id.id,
                    'mat_planned_qty': material.mat_planned_qty,
                    'mat_actual_qty': material.mat_actual_qty,
                    'mat_uom': material.mat_uom,
                    'mat_cost_per_unit': material.mat_cost_per_unit,
                    'mat_total_actual_product_cost': material.mat_total_actual_product_cost,
                }) for material in bom.material_costing_ids
            ]
            self.material_costing_ids = material_costing_data

            labour_costing_data = []
            lab_total_cost = 0
            for labour in bom.labour_costing_ids:
                lab_cost_per_hour = labour.lab_cost_per_hour
                if self.is_costing_by_work_center:
                    lab_cost_per_hour = labour.lab_operation_id.workcenter_id.labour_cost_per_hour or 0

                total_operation_cost = labour.lab_planned_hour * lab_cost_per_hour
                lab_total_cost += total_operation_cost

                labour_costing_data.append((0, 0, {
                    'lab_operation_id': labour.lab_operation_id.id,
                    'lab_planned_hour': labour.lab_planned_hour,
                    'lab_actual_hour': labour.lab_actual_hour,
                    'lab_cost_per_hour': lab_cost_per_hour,
                    'lab_total_actual_operation_cost': labour.lab_total_actual_operation_cost,
                }))
            self.labour_costing_ids = labour_costing_data

            overhead_costing_data = []
            ove_total_cost = 0
            for overhead in bom.overhead_costing_ids:
                ove_cost_per_hour = overhead.ove_cost_per_hour
                if self.is_costing_by_work_center:
                    ove_cost_per_hour = overhead.ove_operation_id.workcenter_id.overhead_cost_per_hour or 0

                total_operation_cost = overhead.ove_planned_hour * ove_cost_per_hour
                ove_total_cost += total_operation_cost

                overhead_costing_data.append((0, 0, {
                    'ove_operation_id': overhead.ove_operation_id.id,
                    'ove_planned_hour': overhead.ove_planned_hour,
                    'ove_actual_hour': overhead.ove_actual_hour,
                    'ove_cost_per_hour': ove_cost_per_hour,
                    'ove_total_actual_operation_cost': overhead.ove_total_actual_operation_cost,
                }))
            self.overhead_costing_ids = overhead_costing_data

            self.mat_total_cost = bom.mat_total_cost
            self.lab_total_cost = lab_total_cost if self.is_costing_by_work_center else bom.lab_total_cost
            self.ove_total_cost = ove_total_cost if self.is_costing_by_work_center else bom.ove_total_cost

            self.total_cost = self.mat_total_cost + self.lab_total_cost + self.ove_total_cost

    #functions to find the Actual Total costs
    @api.depends("material_costing_ids.mat_cost_per_unit", 'material_costing_ids.mat_actual_qty')
    def _find_mat_total_actual_cost(self):
        total_cost = 0
        for record in self.material_costing_ids:
            record.mat_total_actual_product_cost = record.mat_actual_qty * record.mat_cost_per_unit
            total_cost += record.mat_total_actual_product_cost
        self.mat_total_actual_cost = total_cost

    @api.depends("labour_costing_ids.lab_actual_hour", "labour_costing_ids.lab_cost_per_hour")
    def _find_lab_total_actual_cost(self):
        total_cost = 0
        for record in self.labour_costing_ids:
            record.lab_total_actual_operation_cost = record.lab_actual_hour * record.lab_cost_per_hour
            total_cost += record.lab_total_actual_operation_cost
        self.lab_total_actual_cost = total_cost

    @api.depends("overhead_costing_ids.ove_actual_hour", "overhead_costing_ids.ove_cost_per_hour")
    def _find_ove_total_actual_cost(self):
        total_cost = 0
        for record in self.overhead_costing_ids:
            record.ove_total_actual_operation_cost = record.ove_actual_hour * record.ove_cost_per_hour
            total_cost += record.ove_total_actual_operation_cost
        self.ove_total_actual_cost = total_cost

    @api.depends('mat_total_actual_cost', 'lab_total_actual_cost', 'ove_total_actual_cost')
    def _find_actual_total_cost(self):
        for record in self:
            record.actual_total_cost = (
                    record.mat_total_actual_cost +
                    record.lab_total_actual_cost +
                    record.ove_total_actual_cost
            )

    @api.onchange('material_costing_ids')
    def _find_product_unit_cost(self):
        self.product_unit_cost = 0
        for line in self.material_costing_ids:
            if line.mat_product_id:
                self.product_unit_cost += line.mat_product_id.standard_price

    #function of Produce All Button
    def button_mark_done(self):
        super(MrpProduction, self).button_mark_done()
        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.costing_method_selection')
        if temp == 'work_center':
            for labour_cost in self.labour_costing_ids:
                for rec in self.workorder_ids:
                    if rec.name == labour_cost.lab_operation_id.name:
                        labour_cost.lab_actual_hour = rec.duration / 60

            for overhead_cost in self.overhead_costing_ids:
                for rec in self.workorder_ids:
                    if rec.name == overhead_cost.ove_operation_id.name:
                        overhead_cost.ove_actual_hour = rec.duration / 60

        if self.is_journal_entry:
            inventory_journal = self.env['account.journal'].search(
                [('type', '=', 'general'), ('name', '=', 'Inventory Valuation')], limit=1
            )

            total_cost_values = {
                'move_type': 'entry',
                'journal_id': inventory_journal.id,
                'ref': f"{self.name} - {self.product_id.name}",
                'line_ids': [
                    (0, 0, {
                        'account_id': self.total_cost_credit_account_id.id,
                        'name': f"{self.name} - {self.product_id.name}",
                        'debit': 0.0,
                        'credit': self.actual_total_cost,
                    }),
                    (0, 0, {
                        'account_id': self.total_cost_debit_account_id.id,
                        'name': f"{self.name} - {self.product_id.name}",
                        'debit': self.actual_total_cost,
                        'credit': 0.0,
                    }),
                ],
            }
            total_cost = self.env['account.move'].create(total_cost_values)
            total_cost.action_post()

            material_cost_values = {
                'move_type': 'entry',
                'journal_id': inventory_journal.id,
                'ref': f"{self.name} -material",
                'line_ids': [
                    (0, 0, {
                        'account_id':self.material_cost_credit_account_id.id,
                        'name': f"{self.name} - material",
                        'debit': 0.0,
                        'credit': self.mat_total_actual_cost,
                    }),
                    (0, 0, {
                        'account_id':self.material_cost_debit_account_id.id,
                        'name': f"{self.name} - material",
                        'debit': self.mat_total_actual_cost,
                        'credit': 0.0,
                    }),
                ],
            }
            material_cost = self.env['account.move'].create(material_cost_values)
            material_cost.action_post()

            labour_cost_values = {
                'move_type': 'entry',
                'journal_id': inventory_journal.id,
                'ref': f"{self.name} - labour",
                'line_ids': [
                    (0, 0, {
                        'account_id': self.labour_cost_credit_account_id.id,
                        'name': f"{self.name} - labour",
                        'debit': 0.0,
                        'credit': self.lab_total_actual_cost,
                    }),
                    (0, 0, {
                        'account_id': self.labour_cost_debit_account_id.id,
                        'name': f"{self.name} - labour",
                        'debit': self.lab_total_actual_cost,
                        'credit': 0.0,
                    }),
                ],
            }
            labour_cost = self.env['account.move'].create(labour_cost_values)
            labour_cost.action_post()

            overhead_cost_values = {
                'move_type': 'entry',
                'journal_id': inventory_journal.id,
                'ref': f"{self.name} - overhead",
                'line_ids': [
                    (0, 0, {
                        'account_id': self.overhead_cost_credit_account_id.id,
                        'name': f"{self.name} - overhead",
                        'debit': 0.0,
                        'credit': self.ove_total_actual_cost,
                    }),
                    (0, 0, {
                        'account_id':self.overhead_cost_debit_account_id.id,
                        'name': f"{self.name} - overhead",
                        'debit': self.ove_total_actual_cost,
                        'credit': 0.0,
                    }),
                ],
            }
            overhead_cost = self.env['account.move'].create(overhead_cost_values)
            overhead_cost.action_post()

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    #function of Work order done button
    def button_finish(self):
        super(MrpWorkorder, self).button_finish()

        temp = self.env['ir.config_parameter'].sudo().get_param('cr_mrp_process_costing.costing_method_selection')

        if temp == 'work_center':
            for labour_cost in self.production_id.labour_costing_ids:
                for rec in self:
                    if rec.name == labour_cost.lab_operation_id.name:
                        labour_cost.lab_actual_hour = rec.duration / 60

            for overhead_cost in self.production_id.overhead_costing_ids:
                for rec in self:
                    if rec.name == overhead_cost.ove_operation_id.name:
                        overhead_cost.ove_actual_hour = rec.duration / 60
