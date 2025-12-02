# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api
import logging

logger = logging.getLogger(__name__)

class PaymentMethodFees(models.Model):
    _name = "payment.method.fees"
    _description = "Fees Per Payment Method"

    payment_method_id = fields.Many2one("payment.method", string="Payment Method")
    default_method = fields.Boolean(string="Default Payment Method Fee")
    fix_domestic_fees = fields.Float(string="Fixed Domestic Fees")
    var_domestic_fees = fields.Float(string="Variable Domestic Fees (in percent)")
    is_free_domestic = fields.Boolean(string="Free Domestic Fees if Amount is Above")
    free_domestic_amount = fields.Float(string="Domestic Total Amount")
    fix_international_fees = fields.Float(string="Fixed International Fees")
    var_international_fees = fields.Float(string="Variable International Fees (in percent)")
    is_free_international = fields.Boolean(string="Free International Fees if Amount is Above")
    free_international_amount = fields.Float(string="International Total Amount")
    payment_provider_id = fields.Many2one(comodel_name="payment.provider")

    # _sql_constraints = [
    #     ('default_method_unique', 'UNIQUE(payment_provider_id, default_method)',
    #      'Only one payment method can be set as default per payment provider!')
    # ]
