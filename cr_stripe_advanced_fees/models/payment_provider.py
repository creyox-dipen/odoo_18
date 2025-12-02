# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api
import json
from odoo.addons.payment import utils as payment_utils

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    fees_product = fields.Many2one(string="Product Fees", comodel_name="product.template")
    is_extra_fees = fields.Boolean(string="Add Extra Fees")
    line_ids = fields.One2many(comodel_name="payment.method.fees", inverse_name="payment_provider_id")

    def _stripe_get_inline_form_values(self, amount, currency, partner_id, is_validation, payment_method_sudo=None, sale_order_id=None, **kwargs):
        """ Extend the standard Stripe inline form values to include fees """
        # Call original method first
        res = super()._stripe_get_inline_form_values(amount, currency, partner_id, is_validation, payment_method_sudo=payment_method_sudo, sale_order_id=sale_order_id, **kwargs)
        values = json.loads(res)
        fees = 0.0
        if self.is_extra_fees:
            partner = self.env['res.partner'].browse(partner_id)
            base_amount = payment_utils.to_major_currency_units(amount, currency)
            used_method_code = payment_method_sudo.code if payment_method_sudo else None
            fee_line = self.line_ids.filtered(lambda l: l.payment_method_id.code == used_method_code)

            # Fallback to default method if no specific match
            if not fee_line:
                fee_line = self.line_ids.filtered('default_method')[:1]

            if not fee_line:
                values['fees'] = fees
                return json.dumps(values)
            fee_line = fee_line[0]

            company_country = self.company_id.country_id
            is_international = (
                partner.country_id and company_country and partner.country_id.id != company_country.id
            )

            if is_international:
                fee_type_free = fee_line.is_free_international
                fee_type_fixed = fee_line.fix_international_fees
                fee_type_var = fee_line.var_international_fees
                fee_type_threshold = fee_line.free_international_amount
            else:
                fee_type_free = fee_line.is_free_domestic
                fee_type_fixed = fee_line.fix_domestic_fees
                fee_type_var = fee_line.var_domestic_fees
                fee_type_threshold = fee_line.free_domestic_amount

            apply_fees = True
            if fee_type_free:
                if base_amount >= fee_type_threshold:
                    apply_fees = False
            if apply_fees:
                total_fixed_fees = fee_type_fixed
                total_percent_fees = (fee_type_var * base_amount) / 100
                fees = total_fixed_fees + total_percent_fees
        # Inject fees (in major units to match JS)
        values['fees'] = fees
        values['currency_symbol'] = currency.symbol
        return json.dumps(values)