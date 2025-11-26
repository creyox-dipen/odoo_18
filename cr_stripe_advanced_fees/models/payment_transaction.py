# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api
from odoo.addons.payment import utils as payment_utils
import logging

logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    fees = fields.Float(string="Fees")

    def _stripe_prepare_payment_intent_payload(self):
        logger.info("🎯🎯🎯 intent is creating")
        res = super()._stripe_prepare_payment_intent_payload()
        provider = self.provider_id

        if provider.is_extra_fees:
            logger.info("👉👉👉 fees on")
            base_amount = payment_utils.to_major_currency_units(res['amount'], self.currency_id)
            logger.info("Base amount : %d", base_amount)
            total_fixed_fees = 0.0
            total_percent_fees = 0.0

            # Determine if international fees should apply
            partner_country = self.partner_id.country_id
            company_country = self.company_id.country_id
            is_international = (
                    partner_country and company_country and partner_country.id != company_country.id
            )
            logger.info("is International : %d", is_international)

            # Find the matching fee line for the payment method used
            # Assumption: 'payment.method' model exists with a 'code' field matching self.payment_method_type (e.g., 'card', 'ideal')
            used_method = self.env['payment.method'].search([('code', '=', self.payment_method_code)], limit=1)
            fee_line = provider.line_ids.filtered(lambda l: l.payment_method_id == used_method)
            logger.info("used method : %d", used_method)
            logger.info("fee line : %d", fee_line)
            # Fallback to default method if no specific match
            if not fee_line:
                fee_line = provider.line_ids.filtered('default_method', limit=1)
                logger.info("Default Method : %d", fee_line)

            # If still no fee_line (no config at all), fees = 0 (skip)
            if not fee_line:
                return res

            # Apply domestic or international logic based on the matched/default fee_line
            if is_international:
                logger.info("international fee is calculating")
                fee_type_free = fee_line.is_free_international
                fee_type_fixed = fee_line.fix_international_fees
                fee_type_var = fee_line.var_international_fees
                fee_type_threshold = fee_line.free_international_amount
            else:
                logger.info("domestic fee is calculating")
                fee_type_free = fee_line.is_free_domestic
                fee_type_fixed = fee_line.fix_domestic_fees
                fee_type_var = fee_line.var_domestic_fees
                fee_type_threshold = fee_line.free_domestic_amount

            # Compute fees: always apply unless free above threshold
            apply_fees = True
            if fee_type_free:
                if base_amount >= fee_type_threshold:
                    apply_fees = False

            if apply_fees:
                total_fixed_fees = fee_type_fixed
                total_percent_fees = (fee_type_var * base_amount) / 100
            logger.info("➡️➡️ total fixed fees : ", total_fixed_fees)
            self.fees = total_fixed_fees + total_percent_fees
            fees_minor_currency = payment_utils.to_minor_currency_units(self.fees, self.currency_id)
            res['amount'] += fees_minor_currency

        return res