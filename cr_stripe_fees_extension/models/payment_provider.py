# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api
import json
from odoo.addons.payment import utils as payment_utils

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    is_extra_fees = fields.Boolean(string="Add Extra Fees")
    fix_domestic_fees = fields.Float(string="Fixed Domestic Fees")
    var_domestic_fees = fields.Float(string="Variable Domestic Fees (in percent)")
    is_free_domestic = fields.Boolean(string="Free Domestic Fees if Amount is Above")
    free_domestic_amount = fields.Float(string="Domestic Total Amount")
    fix_international_fees = fields.Float(string="Fixed International Fees")
    var_international_fees = fields.Float(string="Variable International Fees (in percent)")
    is_free_international = fields.Boolean(string="Free International Fees if Amount is Above")
    free_international_amount = fields.Float(string="International Total Amount")

    def _stripe_get_inline_form_values(self, amount, currency, partner_id, is_validation, payment_method_sudo=None, sale_order_id=None, **kwargs):
        """ Extend the standard Stripe inline form values to include fees """
        # Call original method first
        res = super()._stripe_get_inline_form_values(amount, currency, partner_id, is_validation, payment_method_sudo=payment_method_sudo, sale_order_id=sale_order_id, **kwargs)
        values = json.loads(res)

        # === Compute fees ===
        fees = 0.0
        if self.is_extra_fees:
            partner = self.env['res.partner'].browse(partner_id)
            company_country = self.env.company.country_id
            if partner.country_id != company_country:
                # International fees
                total_fixed = self.fix_international_fees
                total_percent = (self.var_international_fees * amount) / 100 if amount else 0.0
            else:
                # Domestic fees
                total_fixed = self.fix_domestic_fees
                total_percent = (self.var_domestic_fees * amount) / 100 if amount else 0.0
            fees = total_fixed + total_percent

        # Inject fees + currency symbol
        values['fees'] = fees
        values['currency_symbol'] = currency.symbol

        return json.dumps(values)
