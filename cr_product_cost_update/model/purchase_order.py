# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        res = super().button_confirm()

        for line in self.order_line:
            if line.product_id.categ_id.property_cost_method == "standard":
                line.product_id.standard_price = line.price_unit

        return res