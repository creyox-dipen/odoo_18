# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models

class PaymentToken(models.Model):
    _inherit = 'payment.token'

    nmi_card_type = fields.Selection(
        selection=[('credit', 'Credit Card'), ('debit', 'Debit Card'), ('unknown', 'Unknown')],
        string="NMI Card Type",
        default='unknown',
        help="The type of card detected by NMI during the first transaction."
    )
