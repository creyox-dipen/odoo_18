# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields

class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    stripe_journal_id = fields.Many2one(
        'account.journal',
        string="Stripe Journal",
        domain=[('type', '=', 'bank')],
        help="Bank journal where Stripe transactions will be imported."
    )
