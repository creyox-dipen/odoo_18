# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from odoo.tests import tagged
from odoo.addons.cr_payment_eupago.tests.common import PaymentEupagoCommon
from odoo.addons.cr_payment_eupago import const


@tagged("post_install", "-at_install", "eupago")
class TestPaymentProvider(PaymentEupagoCommon):

    def test_supported_currencies(self):
        """Test that only EUR is supported by euPago providers."""
        for provider in (self.provider_mbref, self.provider_mbway, self.provider_cc):
            currencies = provider._get_supported_currencies()
            self.assertEqual(currencies.mapped("name"), ["EUR"])

    def test_default_payment_method_codes(self):
        """Test that correct default payment methods are returned for each provider."""
        self.assertEqual(
            self.provider_mbref._get_default_payment_method_codes(),
            const.DEFAULT_PAYMENT_METHOD_CODES_MBREF,
        )
        self.assertEqual(
            self.provider_mbway._get_default_payment_method_codes(),
            const.DEFAULT_PAYMENT_METHOD_CODES_MBWAY,
        )
        self.assertEqual(
            self.provider_cc._get_default_payment_method_codes(),
            const.DEFAULT_PAYMENT_METHOD_CODES_CC,
        )

    def test_request_url_construction(self):
        """Test sandbox and production request URL construction for all endpoints."""
        # --- Multibanco (Old REST API) ---
        self.provider_mbref.state = "test"
        self.assertEqual(
            self.provider_mbref._build_request_url(const.ENDPOINT_MULTIBANCO),
            "https://sandbox.eupago.pt/clientes/rest_api/multibanco/create",
        )
        self.provider_mbref.state = "enabled"
        self.assertEqual(
            self.provider_mbref._build_request_url(const.ENDPOINT_MULTIBANCO),
            "https://clientes.eupago.pt/clientes/rest_api/multibanco/create",
        )

        # --- MB WAY (New API v1.02) ---
        self.provider_mbway.state = "test"
        self.assertEqual(
            self.provider_mbway._build_request_url(const.ENDPOINT_MBWAY),
            "https://sandbox.eupago.pt/api/v1.02/mbway/create",
        )
        self.provider_mbway.state = "enabled"
        self.assertEqual(
            self.provider_mbway._build_request_url(const.ENDPOINT_MBWAY),
            "https://clientes.eupago.pt/api/v1.02/mbway/create",
        )

        # --- Credit Card (New API v1.02) ---
        self.provider_cc.state = "test"
        self.assertEqual(
            self.provider_cc._build_request_url(const.ENDPOINT_CC),
            "https://sandbox.eupago.pt/api/v1.02/creditcard/create",
        )
        self.provider_cc.state = "enabled"
        self.assertEqual(
            self.provider_cc._build_request_url(const.ENDPOINT_CC),
            "https://clientes.eupago.pt/api/v1.02/creditcard/create",
        )

    def test_request_headers_construction(self):
        """Test header building (header auth vs body auth)."""
        # Multibanco uses body auth, so it should not have Authorization header
        headers_mbref = self.provider_mbref._build_request_headers()
        self.assertNotIn("Authorization", headers_mbref)
        self.assertEqual(headers_mbref["Content-Type"], "application/json")

        # MB WAY and CC use ApiKey header auth
        headers_mbway = self.provider_mbway._build_request_headers()
        self.assertEqual(headers_mbway["Authorization"], f"ApiKey {self.api_key}")

        headers_cc = self.provider_cc._build_request_headers()
        self.assertEqual(headers_cc["Authorization"], f"ApiKey {self.api_key}")
