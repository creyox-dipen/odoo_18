# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api
from odoo.addons.payment import utils as payment_utils

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fees = fields.Float(string="Fees")

    def _stripe_prepare_payment_intent_payload(self):
        res = super()._stripe_prepare_payment_intent_payload()
        stripe_provider = self.env['payment.provider'].search([('code', '=', 'stripe')], limit=1)

        if stripe_provider.is_extra_fees:
            base_amount = payment_utils.to_major_currency_units(res['amount'], self.currency_id)

            # Default to domestic fees
            total_fixed_fees = stripe_provider.fix_domestic_fees
            total_percent_fees = (stripe_provider.var_domestic_fees * base_amount) / 100

            # Determine if international fees should apply
            partner_country = self.partner_id.country_id
            company_country = self.company_id.country_id
            is_international = (
                    partner_country and company_country and partner_country.id != company_country.id
            )

            if is_international:
                total_fixed_fees += stripe_provider.fix_international_fees
                total_percent_fees += (stripe_provider.var_international_fees * base_amount) / 100

            self.fees = total_fixed_fees + total_percent_fees
            fees_minor_currency = payment_utils.to_minor_currency_units(self.fees, self.currency_id)
            res['amount'] += fees_minor_currency

        return res

        return res
