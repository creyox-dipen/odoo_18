# models/sale_order_line.py
# -*- coding: utf-8 -*-

from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_precision = fields.Json(string="Analytic Precision")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")

    def _get_account_from_distribution(self):
        """Extract the first analytic account ID from analytic_distribution JSON.
        Keys can be a single ID '42' or comma-separated '7,18' for multi-plan accounts.
        We take the first ID in either case.
        """
        if self.analytic_distribution:
            first_key = next(iter(self.analytic_distribution), None)
            if first_key:
                return int(str(first_key).split(',')[0])
        return False

    def _prepare_procurement_values(self, group_id=False):
        """Override to include analytic_distribution and analytic_precision in procurement values,
        which will propagate to stock.move creation via stock rules."""
        res = super()._prepare_procurement_values(group_id=group_id)
        res['analytic_distribution'] = self.analytic_distribution
        res['analytic_precision'] = self.analytic_precision
        # Use manually set account first, else extract from distribution
        res['analytic_account_id'] = self._get_account_from_distribution()
        return res