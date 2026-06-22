# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    x_tranzila_transaction_id = fields.Char(string='x_tranzila_transaction_id')
    x_tranzila_transaction_url = fields.Char(string='x_tranzila_transaction_url')
    x_payment_cc_last4 = fields.Char(string='x_payment_cc_last4')
    x_payment_cc_type = fields.Char(string='x_payment_cc_type')
    x_payment_amount = fields.Float(string='x_payment_amount')
    x_payment_currency = fields.Char(string='x_payment_currency')
    x_payment_status = fields.Selection([
        ('pending', 'PENDING'),
        ('authorized', 'AUTHORIZED'),
        ('charged', 'CHARGED'),
        ('failed', 'FAILED'),
        ('released', 'RELEASED'),
        ('refunded', 'REFUNDED'),
    ], string='x_payment_status')
    x_payment_error_code = fields.Char(string='x_payment_error_code')
