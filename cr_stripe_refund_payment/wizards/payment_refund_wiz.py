# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields
import logging
from odoo.exceptions import UserError
log = logging.getLogger(__name__)

class PaymentRefund(models.TransientModel):
    _name = "payment.refund.wiz"
    _description = "this is payment refund wizard for refund stripe button"

    payment_transaction_id = fields.Many2one(string='Payment Transaction', comodel_name='payment.transaction')
    refund_amount = fields.Float(string='Refund Amount')

    def make_refund_request(self):
        log.info("refund process started...")

