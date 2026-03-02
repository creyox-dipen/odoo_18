# models/purchase_order_line.py
# -*- coding: utf-8 -*-

from odoo import models, api, fields

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

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

    def _prepare_stock_moves(self, picking):
        """Override to include analytic_distribution in stock.move vals."""
        moves_vals = super()._prepare_stock_moves(picking)
        for move_vals in moves_vals:
            move_vals['analytic_distribution'] = self.analytic_distribution
            move_vals['analytic_precision'] = self.analytic_precision
            # Use manually set account first, else extract from distribution
            move_vals['analytic_account_id'] = (
                    self.analytic_account_id.id or self._get_account_from_distribution()
            )
        return moves_vals