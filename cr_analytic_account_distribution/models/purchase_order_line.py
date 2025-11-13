# models/purchase_order_line.py
# -*- coding: utf-8 -*-
# Part of Your Custom Module.
from odoo import models, api

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_stock_moves(self, picking):
        """Override to include analytic_distribution in stock.move vals."""
        moves_vals = super()._prepare_stock_moves(picking)
        for move_vals in moves_vals:
            move_vals['analytic_distribution'] = self.analytic_distribution
            move_vals['analytic_precision'] = self.analytic_precision
        return moves_vals

