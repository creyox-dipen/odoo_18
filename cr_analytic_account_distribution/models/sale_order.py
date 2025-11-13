# models/sale_order_line.py
# -*- coding: utf-8 -*-
# Part of Your Custom Module (extend the existing one).
from odoo import models, api

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_procurement_values(self, group_id=False):
        """Override to include analytic_distribution and analytic_precision in procurement values,
        which will propagate to stock.move creation via stock rules."""
        print("prepare_procurement_values method called")
        res = super()._prepare_procurement_values(group_id=group_id)
        res['analytic_distribution'] = self.analytic_distribution
        res['analytic_precision'] = self.analytic_precision
        return res