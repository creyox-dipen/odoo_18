# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import logging
from odoo.addons.cr_payment_eupago import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    # =========================================================================
    # SELECTION FIELD — add all three euPago provider codes
    # =========================================================================
    code = fields.Selection(
        selection_add=[
            ("eupago_mbref", "euPago — Multibanco (ATM Reference)"),
            ("eupago_mbway", "euPago — MB WAY"),
            ("eupago_cc", "euPago — Credit Card"),
        ],
        ondelete={
            "eupago_mbref": "set default",
            "eupago_mbway": "set default",
            "eupago_cc": "set default",
        },
    )

    # =========================================================================
    # FIELDS
    # =========================================================================
    cr_eupago_api_key = fields.Char(
        string="euPago API Key",
        help=(
            "Your euPago API Key found in the euPago Backoffice under:\n"
            "Channels → Channel Listing → (your channel)"
        ),
        required_if_provider="eupago_mbref",
        copy=False,
        groups="base.group_system",
    )

    cr_eupago_client_id = fields.Char(
        string="euPago Client ID",
        help="Client ID for OAuth 2.0 (Required for Refunds)",
        copy=False,
        groups="base.group_system",
    )

    cr_eupago_client_secret = fields.Char(
        string="euPago Client Secret",
        help="Client Secret for OAuth 2.0 (Required for Refunds)",
        copy=False,
        groups="base.group_system",
    )

    cr_eupago_mb_deadline_days = fields.Integer(
        string="Multibanco Deadline (days)",
        default=30,
        help=(
            "Number of days a Multibanco ATM reference is valid before it expires. "
            "Applies to Multibanco (ATM Reference) provider only. Default: 30 days."
        ),
    )

    cr_eupago_min_amount = fields.Float(
        string="Minimum Amount",
        default=1.0,
        help="Minimum payment amount allowed for this provider.",
    )

    cr_eupago_max_amount = fields.Float(
        string="Maximum Amount",
        default=99999.0,
        help="Maximum payment amount allowed for this provider.",
    )

    # =========================================================================
    # EXTRA FEES CONFIGURATION
    # =========================================================================
    cr_eupago_is_extra_fees = fields.Boolean(string="Add Extra Fees")
    cr_eupago_fees_product = fields.Many2one(
        comodel_name="product.template",
        string="Fees Product",
        domain=[("detailed_type", "=", "service")],
        help="The product used to add extra fees to the Sales Order.",
        default=lambda self: self.env.ref('cr_payment_eupago.eupago_fees_product_template', raise_if_not_found=False)
    )
    cr_eupago_fix_domestic_fees = fields.Float(string="Fixed Domestic Fees")
    cr_eupago_var_domestic_fees = fields.Float(string="Variable Domestic Fees (in percent)")
    cr_eupago_is_free_domestic = fields.Boolean(string="Free Domestic Fees if Amount is Above")
    cr_eupago_free_domestic_amount = fields.Float(string="Domestic Total Amount")
    cr_eupago_fix_international_fees = fields.Float(string="Fixed International Fees")
    cr_eupago_var_international_fees = fields.Float(string="Variable International Fees (in percent)")
    cr_eupago_is_free_international = fields.Boolean(string="Free International Fees if Amount is Above")
    cr_eupago_free_international_amount = fields.Float(string="International Total Amount")

    # =========================================================================
    # FEATURE SUPPORT FLAGS
    # =========================================================================

    def _compute_feature_support_fields(self):
        """Override to declare refund support per euPago provider.

        - Multibanco (eupago_mbref): No refund API — must be done manually in bank.
        - MB WAY (eupago_mbway): No refund API — must be done manually.
        - Credit Card (eupago_cc): Supports full refund via euPago API.
        """
        super()._compute_feature_support_fields()
        for provider in self:
            if provider.code in (const.PROVIDER_CODE_CC, const.PROVIDER_CODE_MBWAY):
                provider.support_refund = "full_only"
            elif provider.code == const.PROVIDER_CODE_MBREF:
                provider.support_refund = "none"

    # =========================================================================
    # CONSTRAINTS — ensure API key is set before enabling any euPago provider
    # =========================================================================

    @api.constrains("state", "cr_eupago_api_key", "code")
    def _check_eupago_api_key_required(self):
        """Ensure the API key is configured whenever a euPago provider is enabled.

        Applies to all 3 providers (MB REF, MB WAY, CC). Without an API key
        every API call will fail with 'Invalid API Key' at runtime.
        """
        for provider in self:
            if (
                provider.code in const.ALL_PROVIDER_CODES
                and provider.state != "disabled"
                and not provider.cr_eupago_api_key
            ):
                raise ValidationError(
                    _(
                        "An API Key is required to enable '%s'. "
                        "Please enter your euPago API Key (found in the euPago Backoffice "
                        "under Channels → Channel Listing → your channel) "
                        "before activating this provider.",
                        provider.name,
                    )
                )

    # =========================================================================
    # HELPER — check if current record is any euPago provider
    # =========================================================================
    def _is_eupago(self):
        return self.code in const.ALL_PROVIDER_CODES

    # =========================================================================
    # CURRENCY FILTERING — euPago supports EUR only
    # =========================================================================

    def _get_supported_currencies(self):
        """Override of `payment` to return only EUR for euPago providers."""
        supported_currencies = super()._get_supported_currencies()
        if self._is_eupago():
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    # =========================================================================
    # DEFAULT PAYMENT METHODS
    # =========================================================================

    def _get_default_payment_method_codes(self):
        """Override of `payment` to return the default payment method codes."""
        self.ensure_one()
        if self.code == const.PROVIDER_CODE_MBREF:
            return const.DEFAULT_PAYMENT_METHOD_CODES_MBREF
        if self.code == const.PROVIDER_CODE_MBWAY:
            return const.DEFAULT_PAYMENT_METHOD_CODES_MBWAY
        if self.code == const.PROVIDER_CODE_CC:
            return const.DEFAULT_PAYMENT_METHOD_CODES_CC
        return super()._get_default_payment_method_codes()

    # =========================================================================
    # REQUEST HELPERS
    # =========================================================================

    def _build_request_url(self, endpoint, **kwargs):
        """Override of `payment` to build the euPago request URL.

        euPago has two API styles:
        - Old REST (Body Auth): /clientes/rest_api/... → used by Multibanco
        - New API v1.02 (ApiKey Header): /api/... → used by MB WAY and CC

        The endpoint passed must already include the version prefix
        (e.g., '/v1.02/mbway/create') for the new API.
        """
        if not self._is_eupago():
            return super()._build_request_url(endpoint, **kwargs)

        if self.code == const.PROVIDER_CODE_MBREF:
            # Old REST API — body auth (chave param in JSON body)
            base = (
                const.SANDBOX_REST_URL
                if self.state == "test"
                else const.PRODUCTION_REST_URL
            )
        else:
            # New API — ApiKey header auth (MB WAY and CC)
            base = (
                const.SANDBOX_API_URL
                if self.state == "test"
                else const.PRODUCTION_API_URL
            )

        if not base.endswith("/"):
            base += "/"
        return base + endpoint.lstrip("/")

    def _build_request_headers(self, *args, **kwargs):
        """Override of `payment` to build the euPago request headers.

        Multibanco (old REST) uses body auth — no Authorization header needed
        (the API key goes in the JSON body as 'chave').

        MB WAY and CC use ApiKey header auth:
        Authorization: ApiKey xxxx-xxxx-xxxx-xxxx-xxxx
        """
        if not self._is_eupago():
            return super()._build_request_headers(*args, **kwargs)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.code in (const.PROVIDER_CODE_MBWAY, const.PROVIDER_CODE_CC):
            is_management = self.env.context.get("is_management_api", False)
            if is_management:
                token = self._eupago_get_bearer_token()
                headers["Authorization"] = f"Bearer {token}"
            else:
                headers["Authorization"] = f"ApiKey {self.cr_eupago_api_key}"

        # Multibanco: API key is sent in the JSON body, not as a header.
        # The transaction model adds 'chave' to the payload directly.
        return headers

    def _eupago_get_bearer_token(self):
        """Request an OAuth 2.0 Bearer token for the Management API."""
        self.ensure_one()
        if not self.cr_eupago_client_id or not self.cr_eupago_client_secret:
            raise ValidationError(_("euPago Client ID and Client Secret are required for this operation."))

        base = (
            const.SANDBOX_API_URL
            if self.state == "test"
            else const.PRODUCTION_API_URL
        )
        # Note: const.ENDPOINT_AUTH_TOKEN is /api/auth/token, but base is already /api or something.
        # Actually, SANDBOX_API_URL is 'https://sandbox.eupago.pt/api'. So we need to ensure we don't double '/api'
        # Wait, the url is `https://sandbox.eupago.pt/api/auth/token`. So we use `https://sandbox.eupago.pt` as base.
        base_domain = base.replace("/api", "")
        if not base_domain.endswith("/"):
            base_domain += "/"
        url = base_domain + const.ENDPOINT_AUTH_TOKEN.lstrip("/")

        payload = {
            "client_id": self.cr_eupago_client_id,
            "client_secret": self.cr_eupago_client_secret,
            "grant_type": "client_credentials",
        }

        try:
            import requests
            response = requests.post(
                url, 
                json=payload, 
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("access_token")
        except requests.exceptions.HTTPError as e:
            err_msg = e.response.text if e.response else str(e)
            _logger.error("euPago OAuth error: %s", err_msg)
            raise ValidationError(
                _("euPago Authentication Failed:\n\n%s\n\nPlease check your Client ID/Secret and ensure you are using Sandbox credentials for Test Mode (or Production for Enabled Mode).") % err_msg
            )
        except Exception as e:
            _logger.exception("Failed to fetch euPago Bearer token: %s", e)
            raise ValidationError(_("Failed to authenticate with euPago Management API (OAuth 2.0). Check your Client ID and Secret."))

    def _send_api_request(self, method, endpoint, **kwargs):
        """Send an API request to euPago and return the JSON response."""
        self.ensure_one()
        url = self._build_request_url(endpoint)
        headers = self._build_request_headers()
        import requests
        try:
            response = requests.request(method, url, headers=headers, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as error:
            err_msg = self._parse_response_error(error.response)
            _logger.error("API request error: %s", err_msg)
            raise ValidationError(err_msg)
        except Exception as error:
            _logger.exception("Failed to fetch euPago data: %s", error)
            raise ValidationError(_("Failed to communicate with euPago API."))


    def _parse_response_error(self, response):
        """Override of `payment` to parse euPago API error messages."""
        if not self._is_eupago():
            return super()._parse_response_error(response)

        try:
            data = response.json()
        except Exception:
            return response.text or _("Unknown error from euPago API.")

        # Old REST API (Multibanco) uses 'resposta' field
        # New API (MB WAY / CC) uses 'text' field
        return data.get("resposta") or data.get("text") or str(data)
