# models/stock_move.py
# -*- coding: utf-8 -*-
# Part of Your Custom Module.
from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = "stock.move"

    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    analytic_precision = fields.Json(string="Analytic Precision")

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        """Override to propagate analytic_distribution and analytic_precision from stock.move to stock.move.line vals."""
        print("prepare move lines")
        res = super()._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        res['analytic_distribution'] = self.analytic_distribution
        res['analytic_account_id'] = self.analytic_account_id.id
        res['analytic_precision'] = self.analytic_precision
        return res

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    analytic_precision = fields.Json(string="Analytic Precision")
    analytic_mode = fields.Selection(
        selection=[
            ('analytic_account', 'Analytic Account'),
            ('analytic_distribution', 'Analytic Distribution'),
        ],
        compute='_compute_analytic_mode',
    )

    def _compute_analytic_mode(self):
        mode = self.env['ir.config_parameter'].sudo().get_param(
            'cr_analytic_account.analytic_account_setting'
        )
        for rec in self:
            rec.analytic_mode = mode or False