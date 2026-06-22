# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    x_tadam_payout_id = fields.Char(string='x_tadam_payout_id')
    x_tadam_booking_id = fields.Char(string='x_tadam_booking_id')
    x_payout_status = fields.Selection([
        ('pending', 'PENDING'),
        ('invoice_received', 'INVOICE_RECEIVED'),
        ('invoice_approved', 'INVOICE_APPROVED'),
        ('paid', 'PAID'),
    ], string='x_payout_status')
