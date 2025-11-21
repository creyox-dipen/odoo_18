# models/sale_order_line.py
# -*- coding: utf-8 -*-
from odoo import models

class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_stock_move_values(self, product_id, product_qty, product_uom, location_id, name, origin, company_id,
                               values):
        vals = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id,
            name, origin, company_id, values
        )

        # Transfer analytic fields from procurement to stock.move
        if values.get('analytic_distribution'):
            vals['analytic_distribution'] = values['analytic_distribution']
        if values.get('analytic_precision'):
            vals['analytic_precision'] = values['analytic_precision']

        return vals