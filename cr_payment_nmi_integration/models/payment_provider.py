# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import base64
import hashlib
import logging

from odoo import api, fields, models
from odoo.addons.cr_payment_nmi_integration import const
from werkzeug import urls
from odoo.addons.cr_payment_nmi_integration.controllers.main import NmiController


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    """Extends the payment.provider model to add NMI (Ekashu) configuration fields
    and business logic for card (Ekashu redirect) and ACH (NMI Direct Post) flows.
    """

    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('nmi', "Nmi")], ondelete={'nmi': 'set default'}
    )
    nmi_security_key = fields.Char(
        string="NMI Security Key (API Key)",
        help=(
            "The primary API Security Key used for both ACH and Credit Card transactions via NMI Direct Post. "
            "Generate this in your NMI merchant portal under Settings → Security Keys."
        ),
    )
    nmi_v4_api_key = fields.Char(
        string="v4 API Key",
        help=(
            "NMI v4 API Key required for Card Type Lookup (credit vs debit detection). "
            "This key must have 'Query API' permissions enabled in NMI."
        ),
    )
    is_nmi_card_fee = fields.Boolean(
        string="Add Card Fees",
        help="If enabled, a surcharge will be applied to card payments calculated in Odoo.",
    )
    nmi_credit_card_fee = fields.Float(
        string="Credit Card Fee (%)",
        help="The percentage of the transaction amount to add as a fee for credit card payments.",
    )
    nmi_debit_card_fee = fields.Float(
        string="Debit Card Fee (%)",
        help="The percentage of the transaction amount to add as a fee for debit card payments.",
    )

    # =========================================================================
    # Surcharge Product Management
    # =========================================================================

    def _check_surcharge_product(self):
        """Automatically create Credit and Debit Card Fee products if they don't exist."""
        products_to_check = [
            ('CREDIT_CARD_FEE', 'Credit Card Fee'),
            ('DEBIT_CARD_FEE', 'Debit Card Fee'),
        ]
        
        for code, name in products_to_check:
            product = self.env['product.template'].sudo().search([
                ('default_code', '=', code)
            ], limit=1)
            
            if not product:
                _logger.info("NMI: Creating %s product...", name)
                self.env['product.template'].sudo().create({
                    'name': name,
                    'type': 'service',
                    'default_code': code,
                    'list_price': 0.0,
                    'sale_ok': True,
                    'purchase_ok': False,
                })

    # ===== BUSINESS METHODS =====

    def _nmi_get_direct_post_url(self):
        """Return the NMI Direct Post API endpoint URL based on the provider state.
        
        :return: The NMI Direct Post API URL (sandbox or live).
        :rtype: str
        """
        if self.state == 'enabled':
            return 'https://secure.nmi.com/api/transact.php'
        return 'https://sandbox.nmi.com/api/transact.php'

    @api.model
    def _get_compatible_providers(self, *args, is_validation=False, **kwargs):
        return super()._get_compatible_providers(*args, is_validation=is_validation, **kwargs)

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable tokenization for NMI. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'nmi').update({
            'support_tokenization': True,
        })

    def _get_ach_rendering_values(self, data):
        """Build the dict of values needed to render the ACH payment form."""
        return {
            'reference': data['reference'],
            'amount': "{:.2f}".format(data['amount']),
            'partner_name': data.get('partner_name', ''),
            'ach_process_url': NmiController._ach_process_url,
        }

    def _get_default_payment_method_codes(self):
        """Override to return NMI-specific default payment method codes."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'nmi':
            return default_codes
        return const.DEFAULT_PAYMENT_METHODS_CODES + const.ACH_PAYMENT_METHODS_CODES

    def _nmi_get_card_type(self, bin_number):
        """Call NMI's official Card Type Lookup API using the dedicated v4 API Key.

        :param str bin_number: The first 6 digits of the card number.
        :return: String 'credit', 'debit', or 'unknown'.
        """
        if not self.nmi_v4_api_key or not bin_number or len(bin_number) < 6:
            return 'unknown'

        endpoint = 'https://secure.nmi.com/api/v4/card_type'
        if self.state != 'enabled':
            endpoint = 'https://sandbox.nmi.com/api/v4/card_type'

        headers = {
            'Authorization': self.nmi_v4_api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {'ccnumber': bin_number}

        try:
            import requests as http_requests
            # Use JSON payload and multiple header variations
            response = http_requests.post(endpoint, json=payload, headers=headers, timeout=5)
            _logger.info("NMI API Response Status: %s", response.status_code)
            _logger.info("NMI API Response Content: %s", response.text)
            response.raise_for_status()
            data = response.json()
            # NMI returns "type": "credit", "debit", etc.
            return data.get('result', 'unknown')
        except Exception as e:
            _logger.error("NMI Card Type Lookup failed: %s", str(e))
            return 'unknown'