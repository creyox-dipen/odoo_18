# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from unittest.mock import patch
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from odoo.addons.cr_payment_eupago.tests.common import PaymentEupagoCommon
from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.cr_payment_eupago import const
from odoo.addons.cr_payment_eupago.controllers.main import EupagoController


@tagged("post_install", "-at_install", "eupago")
class TestPaymentTransaction(PaymentEupagoCommon, PaymentHttpCommon):

    # =========================================================================
    # MULTIBANCO (ATM REFERENCE) TESTS
    # =========================================================================

    def test_eupago_render_multibanco_success(self):
        """Test successful Multibanco reference generation & values storage."""
        self.provider = self.provider_mbref
        tx = self._create_transaction(flow="direct")

        # Mock API Response
        mock_response = {
            "sucesso": True,
            "entidade": "12345",
            "referencia": "987654321",
            "valor": 100.00,
            "data_fim": "2026-08-08",
            "resposta": "OK",
        }

        with patch(
            "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
            return_value=mock_response,
        ):
            res = tx._eupago_render_multibanco()

        self.assertEqual(tx.cr_eupago_entity, "12345")
        self.assertEqual(tx.cr_eupago_reference, "987654321")
        self.assertEqual(tx.cr_eupago_deadline, "2026-08-08")
        self.assertEqual(tx.provider_reference, "987654321")
        self.assertEqual(tx.state, "pending")

        # Check returned values for frontend template
        self.assertEqual(res.get("cr_eupago_provider"), "mbref")
        self.assertEqual(res.get("cr_eupago_entity"), "12345")
        self.assertEqual(res.get("cr_eupago_reference"), "987654321")
        self.assertEqual(res.get("cr_eupago_deadline"), "2026-08-08")

    def test_eupago_render_multibanco_failure(self):
        """Test Multibanco reference generation failure sets state to error."""
        self.provider = self.provider_mbref
        tx = self._create_transaction(flow="direct")

        # Mock API Response with failure
        mock_response = {"sucesso": False, "resposta": "Invalid API Key"}

        with patch(
            "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
            return_value=mock_response,
        ):
            res = tx._eupago_render_multibanco()

        self.assertEqual(res, {})
        self.assertEqual(tx.state, "error")
        self.assertIn("Invalid API Key", tx.state_message)

    # =========================================================================
    # MB WAY TESTS
    # =========================================================================

    def test_eupago_render_mbway_success(self):
        """Test successful MB WAY push notification rendering."""
        self.provider = self.provider_mbway
        tx = self._create_transaction(flow="direct")

        # Mock API Response
        mock_response = {
            "transactionStatus": "Success",
            "transactionID": "trid-mbway-999",
            "reference": "987654",
        }

        with patch(
            "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
            return_value=mock_response,
        ):
            res = tx._eupago_render_mbway({"cr_eupago_phone": "912345678"})

        self.assertEqual(tx.provider_reference, "trid-mbway-999")
        self.assertEqual(tx.state, "pending")

        self.assertEqual(res.get("cr_eupago_provider"), "mbway")
        self.assertEqual(res.get("cr_eupago_phone"), "912345678")

    def test_eupago_render_mbway_no_phone(self):
        """Test that MB WAY fails if no phone is provided."""
        self.provider = self.provider_mbway
        tx = self._create_transaction(flow="direct")

        res = tx._eupago_render_mbway({})
        self.assertEqual(res, {})
        self.assertEqual(tx.state, "error")
        self.assertIn("Please provide a phone number", tx.state_message)

    # =========================================================================
    # CREDIT CARD TESTS
    # =========================================================================

    def test_eupago_render_cc_success(self):
        """Test successful Credit Card 3DS redirect URL retrieval."""
        self.provider = self.provider_cc
        tx = self._create_transaction(flow="direct")

        # Mock API Response
        mock_response = {
            "transactionStatus": "Success",
            "transactionID": "trid-cc-888",
            "redirectUrl": "https://sandbox.eupago.pt/checkout/trid-cc-888",
        }

        with patch(
            "odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request",
            return_value=mock_response,
        ):
            res = tx._eupago_render_cc()

        self.assertEqual(tx.provider_reference, "trid-cc-888")
        self.assertEqual(
            res.get("api_url"), "https://sandbox.eupago.pt/checkout/trid-cc-888"
        )

    # =========================================================================
    # WEBHOOK & CONTROLLER TESTS
    # =========================================================================

    def test_webhook_successful_payment(self):
        """Test that a valid webhook GET request updates the transaction to done."""
        self.provider = self.provider_mbref
        tx = self._create_transaction(flow="direct")

        webhook_data = {
            "identificador": tx.reference,
            "valor": tx.amount,
            "transacao": "trid-webhook-111",
            "mp": "PC:PT",
            "chave_api": self.api_key,
        }

        # _process internally resolves the transaction and calls _apply_updates
        tx._process("eupago_mbref", webhook_data)
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.provider_reference, "trid-webhook-111")

    def test_webhook_invalid_api_key(self):
        """Test that webhook fails and raises ValidationError on wrong API Key."""
        self.provider = self.provider_mbref
        tx = self._create_transaction(flow="direct")

        webhook_data = {
            "identificador": tx.reference,
            "valor": tx.amount,
            "transacao": "trid-webhook-111",
            "mp": "PC:PT",
            "chave_api": "wrong-api-key",
        }

        with self.assertRaises(ValidationError):
            tx._apply_updates(webhook_data)

    def test_controller_webhook_endpoint(self):
        """Test that the webhook GET route handles the notification and returns HTTP 200."""
        self.provider = self.provider_mbref
        tx = self._create_transaction(flow="direct")

        webhook_data = {
            "identificador": tx.reference,
            "valor": str(tx.amount),
            "transacao": "trid-webhook-222",
            "mp": "PC:PT",
            "chave_api": self.api_key,
        }

        url = self._build_url(EupagoController._webhook_url)
        response = self._make_http_get_request(url, params=webhook_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "")
        self.assertEqual(tx.state, "done")
        self.assertEqual(tx.provider_reference, "trid-webhook-222")

    def test_controller_cc_return_endpoint(self):
        """Test that the Credit Card return route redirects correctly."""
        self.provider = self.provider_cc
        tx = self._create_transaction(flow="direct")
        tx.provider_reference = "trid-cc-888"

        return_data = {
            "ref": tx.reference,
        }

        url = self._build_url(EupagoController._cc_return_url)
        # We block redirects to check the target redirect destination
        response = self.url_open(url + "?ref=" + tx.reference, allow_redirects=False)

        self.assertEqual(
            response.status_code, 303
        )  # Odoo redirects are typically 303 see other
        self.assertIn("/payment/status", response.headers.get("Location", ""))
