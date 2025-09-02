# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fees = fields.Float(string="Fees")
    
    def _get_specific_processing_values(self, processing_values):
        processing_values['amount'] += 20
        print(processing_values)
        return super()._get_specific_processing_values(processing_values)