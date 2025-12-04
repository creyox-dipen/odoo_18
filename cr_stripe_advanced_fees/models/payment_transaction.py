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
        res = super()._stripe_prepare_payment_intent_payload()
        provider = self.provider_id

        if provider.is_extra_fees:
            base_amount = payment_utils.to_major_currency_units(res['amount'], self.currency_id)
            total_fixed_fees = 0.0
            total_percent_fees = 0.0

            # Determine if international fees should apply
            partner_country = self.partner_id.country_id
            company_country = self.company_id.country_id
            is_international = (
                    partner_country and company_country and partner_country.id != company_country.id
            )

            used_method = self.env['payment.method'].search([('code', '=', self.payment_method_code)], limit=1)
            fee_line = provider.line_ids.filtered(lambda l: l.payment_method_id == used_method)

            if not fee_line:
                fee_line = provider.line_ids.filtered('default_method')[:1]

            if not fee_line:
                return res

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

            self.fees = total_fixed_fees + total_percent_fees

            if self.sale_order_ids and self.fees > 0:
                self._add_fee_line_to_sale_order()

            fees_minor_currency = payment_utils.to_minor_currency_units(self.fees, self.currency_id)
            res['amount'] += fees_minor_currency
            self.amount += self.fees
        return res

    def _add_fee_line_to_sale_order(self):
        """
        Add a fee line to the associated sale order using the provider's fees_product
        and the calculated fees amount. Ensures only one fee line per transaction.
        """
        self.ensure_one()
        so = self.sale_order_ids
        provider = self.provider_id
        fees_product = provider.fees_product

        if not so or not fees_product or not self.fees > 0:
            return

        # Check if a fee line for this transaction already exists (prevent duplicates)
        existing_fee_line = so.order_line.filtered(
            lambda line: line.name == f"Payment Fee - {provider.name} ({self.reference})"
        )
        if existing_fee_line:
            logger.info("Fee line already exists for transaction %s on SO %s", self.id, so.id)
            return

        fee_line_vals = {
            'order_id': so.id,
            'product_id': fees_product.product_variant_id.id,  # Use variant
            'name': f"Payment Fee - {provider.name} ({self.reference})",
            'product_uom_qty': 1.0,
            'price_unit': self.fees,
            'tax_id': False,  # No taxes by default; can be computed if needed via fiscal position
        }
        new_line = self.env['sale.order.line'].create(fee_line_vals)
        logger.info("Added fee line to SO %s: %s (amount: %.2f)", so.id, new_line.name, self.fees)
        so._compute_amounts()
        so._compute_tax_totals()