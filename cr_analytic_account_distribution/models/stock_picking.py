# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields

class StockPicking(models.Model):
    _inherit = "stock.picking"

    analytic_account_manage = fields.Selection(
        selection=[('move','By Stock Move'), ('picking', 'By Picking'), ('none', 'Not Applicable')],
        string='Apply Analytic Accounting by : Picking or Move?',
    )
    analytic_mode = fields.Selection(
        selection=[
            ('analytic_account', 'Analytic Account'),
            ('analytic_distribution', 'Analytic Distribution'),
        ],
        compute='_compute_analytic_mode',
    )
    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_precision = fields.Json(string="Analytic Precision")

    def _compute_analytic_mode(self):
        mode = self.env['ir.config_parameter'].sudo().get_param(
            'cr_analytic_account.analytic_account_setting'
        )
        for rec in self:
            rec.analytic_mode = mode or False
