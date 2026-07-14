# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import http
from odoo.http import request
from odoo.addons.payment.controllers.portal import PaymentPortal
import logging

_logger = logging.getLogger(__name__)


class PublicStripeInfo(http.Controller):
    @http.route(
        ["/custom/stripe/provider_config"], type="json", auth="public", csrf=False
    )
    def get_stripe_provider_config(self):
        provider = (
            request.env["payment.provider"]
            .sudo()
            .search([("code", "=", "stripe")], limit=1)
        )
        if not provider:
            return {}
        line_ids_data = []
        for line in provider.line_ids:
            pm = line.payment_method_id
            line_ids_data.append(
                {
                    "payment_method_code": pm.code,
                    "payment_method_name": pm.name,
                    "default_method": line.default_method,
                    "fix_domestic_fees": line.fix_domestic_fees,
                    "var_domestic_fees": line.var_domestic_fees,
                    "is_free_domestic": line.is_free_domestic,
                    "free_domestic_amount": line.free_domestic_amount,
                    "fix_international_fees": line.fix_international_fees,
                    "var_international_fees": line.var_international_fees,
                    "is_free_international": line.is_free_international,
                    "free_international_amount": line.free_international_amount,
                }
            )
        return {
            "is_extra_fees": provider.is_extra_fees,
            "line_ids": line_ids_data,
            "company_id": provider.company_id.id,
        }

    @http.route(
        ["/custom/stripe/company_country/<int:company_id>"],
        type="json",
        auth="public",
        csrf=False,
    )
    def get_company_country(self, company_id):
        company = request.env["res.company"].sudo().browse(company_id)
        return {"country_id": company.country_id.id if company.country_id else None}

    @http.route(
        [
            "/custom/stripe/order_partner_country",
            "/custom/stripe/order_partner_country/<int:order_id>",
        ],
        type="json",
        auth="public",
        csrf=False,
    )
    def get_order_partner_country(self, order_id=None):
        if order_id:
            order = request.env["sale.order"].sudo().browse(order_id)
        else:
            order = request.website.sale_get_order()
        partner = (
            order.partner_shipping_id if order else None
        )  # Use billing partner to match backend transaction logic
        if not partner:
            partner = request.env.user.partner_id
        return {
            "country_id": (
                partner.country_id.id if partner and partner.country_id else None
            )
        }

    @http.route(
        ["/custom/stripe/token_method/<int:token_id>"],
        type="json",
        auth="public",
        csrf=False,
    )
    def get_token_payment_method(self, token_id):
        # Just redirect to the new unified one
        return self.get_payment_method_code(token_id=token_id)

    @http.route(
        ["/custom/stripe/payment_method_code"], type="json", auth="public", csrf=False
    )
    def get_payment_method_code(self, **kwargs):
        """
        Unified endpoint:
        - If token_id is passed → returns actual card brand (visa, mastercard, amex, etc.)
        - If no token_id → returns 'card' (used for new payments before brand detection)
        """
        token_id = kwargs.get("token_id")

        if token_id:
            token = request.env["payment.token"].sudo().browse(int(token_id))

            if not token.exists() or token.provider_code != "stripe":
                return {"payment_method_code": "card"}

            # This is the correct field in Odoo 16+
            stripe_pm_id = token.stripe_payment_method

            if not stripe_pm_id:
                return {"payment_method_code": "card"}

            provider = token.provider_id
            try:
                stripe_pm = provider._stripe_make_request(
                    f"/v1/payment_methods/{stripe_pm_id}", method="GET"
                )
                if stripe_pm.get("card", {}).get("brand"):
                    brand = stripe_pm["card"]["brand"].lower()
                    # Optional: map known brands if you use them as codes in payment.method
                    brand_map = {
                        "visa": "visa",
                        "mastercard": "mastercard",
                        "american express": "amex",
                        "discover": "discover",
                        "diners club": "diners",
                        "jcb": "jcb",
                        "unionpay": "unionpay",
                    }
                    return {"payment_method_code": brand_map.get(brand, "card")}
            except Exception as e:
                print(f"Could not retrieve token brand for token {token_id}: {e}")

            return {"payment_method_code": "card"}

        # No token → new card entry
        return {"payment_method_code": "card"}


class StripePaymentPortal(PaymentPortal):
    @classmethod
    def _validate_transaction_kwargs(cls, kwargs, additional_allowed_keys=()):
        """Override to automatically whitelist stripe_card_brand kwarg in all payment transaction routes."""
        additional_allowed_keys = list(additional_allowed_keys) + ['stripe_card_brand']
        return super()._validate_transaction_kwargs(kwargs, additional_allowed_keys=tuple(additional_allowed_keys))

    def _create_transaction(self, *args, **kwargs):
        """Override _create_transaction to save stripe_card_brand and adjust amount/unlink old fees."""
        stripe_card_brand = kwargs.get('stripe_card_brand')
        tx_sudo = super()._create_transaction(*args, **kwargs)
        if tx_sudo.provider_id.code == 'stripe':
            if stripe_card_brand:
                tx_sudo.stripe_card_brand = stripe_card_brand
            so = tx_sudo.sale_order_ids[:1]
            fees_product = tx_sudo.provider_id.fees_product
            if so and fees_product:
                existing_fee_lines = so.order_line.filtered(
                    lambda line: line.product_id == fees_product.product_variant_id
                )
                if existing_fee_lines:
                    _logger.info("Unlinking old fee lines from SO %s to correct transaction amount", so.id)
                    existing_fee_lines.unlink()
                    so._compute_amounts()
                    so._compute_tax_totals()
                    tx_sudo.amount = so.amount_total
        return tx_sudo
