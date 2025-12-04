# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    provider_code = fields.Char(string="Payment Provider Code")
    payment_fee = fields.Float(string="Payment Fee", compute="_compute_payment_fee")

    def _compute_payment_fee(self):
        """
        These method is used to compute the payment fee field value based on product_id in particular line
        """
        self.payment_fee = 0.00
        for line in self.order_line:
            if line.product_id.name == "Payment Fee":
                self.payment_fee = line.price_unit
