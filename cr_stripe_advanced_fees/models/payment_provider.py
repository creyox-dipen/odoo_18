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

    # def _stripe_get_inline_form_values(self, amount, currency, partner_id, is_validation, payment_method_sudo=None, sale_order_id=None, **kwargs):
    #     """ Extend the standard Stripe inline form values to include fees """
    #     # Call original method first
    #     res = super()._stripe_get_inline_form_values(amount, currency, partner_id, is_validation, payment_method_sudo=payment_method_sudo, sale_order_id=sale_order_id, **kwargs)
    #     values = json.loads(res)

    #     # === Compute fees ===
    #     fees = 0.0
    #     if self.is_extra_fees:
    #         partner = self.env['res.partner'].browse(partner_id)
    #         company_country = self.env.company.country_id
    #         if partner.country_id != company_country:
    #             # International fees
    #             total_fixed = self.fix_international_fees
    #             total_percent = (self.var_international_fees * amount) / 100 if amount else 0.0
    #         else:
    #             # Domestic fees
    #             total_fixed = self.fix_domestic_fees
    #             total_percent = (self.var_domestic_fees * amount) / 100 if amount else 0.0
    #         fees = total_fixed + total_percent

    #     # Inject fees + currency symbol
    #     values['fees'] = fees
    #     values['currency_symbol'] = currency.symbol

    #     return json.dumps(values)
