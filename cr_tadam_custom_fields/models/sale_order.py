# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_tadam_booking_id = fields.Char(string='x_tadam_booking_id')
    x_booking_status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('en_route', 'En Route'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancel_before_match', 'Cancelled Before Match'),
        ('cancel_after_match', 'Cancelled After Match'),
        ('cancel_after_en_route', 'Cancelled After En Route'),
        ('in_dispute', 'In Dispute'),
        ('disputed', 'Disputed'),
    ], string='x_booking_status')
    x_invoice_status = fields.Selection([
        ('pending', 'PENDING'),
        ('invoiced', 'INVOICED'),
        ('cancelled', 'CANCELLED'),
        ('refunded', 'REFUNDED'),
    ], string='x_invoice_status')
    x_payment_status = fields.Selection([
        ('pending', 'PENDING'),
        ('authorized', 'AUTHORIZED'),
        ('charged', 'CHARGED'),
        ('failed', 'FAILED'),
        ('released', 'RELEASED'),
        ('refunded', 'REFUNDED'),
    ], string='x_payment_status')
