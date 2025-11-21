# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    costing_method_selection = fields.Selection([
        ('manually', 'Manually'),
        ('work_center', 'Work-Center Base'),
    ],config_parameter='cr_mrp_process_costing.costing_method_selection',
    default='manually',required=1)

    is_journal_entry = fields.Boolean(string="Accounting for costing",config_parameter='cr_mrp_process_costing.is_journal_entry')

    material_costing_debit_account_id = fields.Many2one('account.account',string="Material Cost Debit Account",config_parameter='cr_mrp_process_costing.material_costing_debit_account_id')
    labour_costing_debit_account_id = fields.Many2one('account.account',string="Labour Cost Debit Account",config_parameter='cr_mrp_process_costing.labour_costing_debit_account_id')
    overhead_costing_debit_account_id = fields.Many2one('account.account',string="Overhead Cost Debit Account",config_parameter='cr_mrp_process_costing.overhead_costing_debit_account_id')
    total_costing_debit_account_id = fields.Many2one('account.account',string="Total Cost Debit Account",config_parameter='cr_mrp_process_costing.total_costing_debit_account_id')

    material_costing_credit_account_id = fields.Many2one('account.account', string="Material Cost Credit Account",
                                               config_parameter='cr_mrp_process_costing.material_costing_credit_account_id')
    labour_costing_credit_account_id = fields.Many2one('account.account', string="Labour Cost Credit Account",
                                             config_parameter='cr_mrp_process_costing.labour_costing_credit_account_id')
    overhead_costing_credit_account_id = fields.Many2one('account.account', string="Overhead Cost Credit Account",
                                               config_parameter='cr_mrp_process_costing.overhead_costing_credit_account_id')
    total_costing_credit_account_id = fields.Many2one('account.account', string="Total Cost Credit Account",
                                            config_parameter='cr_mrp_process_costing.total_costing_credit_account_id')