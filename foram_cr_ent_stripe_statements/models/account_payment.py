# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import api, fields, models


class PaymentProvider(models.Model):
    _inherit = "account.payment"

    is_internal_transfer = fields.Boolean(string="Internal Transfer")
    destination_journal = fields.Many2one(
        comodel_name="account.journal",
        string="Destination Journal",
        domain=[("type", "=", "bank")],
    )
