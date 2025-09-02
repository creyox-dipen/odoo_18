# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    is_extra_fees = fields.Boolean(string="Add Extra Fees")
    fix_domestic_fees = fields.Float(string="Fixed Domestic Fees")
    var_domestic_fees = fields.Float(string="Variable Domestic Fees (in percent)")
    fix_international_fees = fields.Float(string="Fixed International Fees")
    var_international_fees = fields.Float(string="Variable International Fees (in percent)")