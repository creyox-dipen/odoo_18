# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    payment_fee = fields.Float(string="Fixed Payment Fees")
    payment_fee_percent = fields.Float(string="Payment Fees")
    calculated_payment_fee_percent = fields.Float(string="Percentage Payment Fees")
    payment_fee_type = fields.Selection(
        [("fix", "Fixed"), ("percent", "Percentage")],
        string="Payment Fees  Type",
    )
    payment_fee_applied_on = fields.Selection(
        [("less", "Less Than"), ("greater", "Greater Than")],
        string="Payment Fees Applied On",
    )
    payment_fee_product_id = fields.Many2one(
        "product.product",
        string="Payment Fee Product",
        required=True,
        readonly=True,
        default=lambda self: self.env["product.product"].search(
            [("name", "=", "Payment Fee")], limit=1
        ),
    )
    is_applied_on_condition = fields.Boolean(string="Applied Based On Condition")
    amount_fee = fields.Float(string="Order Amount")
