# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

import logging
import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.account_payment.controllers.payment import (
    PaymentPortal as AccountPaymentPortal,
)
from odoo.addons.cr_payment_eupago import const


_logger = logging.getLogger(__name__)


class EupagoPaymentPortal(AccountPaymentPortal):
    """Override `PaymentPortal` to make `access_token` optional (`default=None`) in
    `invoice_transaction`. This prevents 500 Internal Server Error when authenticated
    users click 'Pay Now' on portal invoice pages without `access_token` parameter.
    """

    @http.route("/invoice/transaction/<int:invoice_id>", type="json", auth="public")
    def invoice_transaction(self, invoice_id, access_token=None, **kwargs):
        return super().invoice_transaction(
            invoice_id, access_token=access_token, **kwargs
        )


class EupagoController(http.Controller):
    """Controller for euPago payment callbacks and webhooks.

    euPago has two types of callbacks:
    1. Webhook (realtime notification) — euPago sends a GET request with URL
       params to your configured callback URL when a payment is received.
       Only fires on successful payments (not cancelled/expired).

    2. CC Return — after 3DS, euPago redirects the browser back to successUrl/
       failUrl/backUrl. We verify the transaction status via TRID and redirect
       to Odoo's /payment/status.

    Webhook setup:
    In euPago Backoffice → Channels → Channel Listing → Edit channel →
    Enable "Receive notification for a URL" and paste the webhook URL.
    """

    # =========================================================================
    # URL definitions — import these into models to avoid hardcoding
    # =========================================================================
    _webhook_url = "/payment/cr_eupago/webhook"
    _cc_return_url = "/payment/cr_eupago/cc/return"
    _mbway_status_url = "/payment/cr_eupago/mbway/status"

    # =========================================================================
    # WEBHOOK — handles Multibanco, MB WAY, and all other euPago methods
    # =========================================================================

    @http.route(
        [_webhook_url, "/payment/cr_eupago/callback"],
        type="http",
        auth="public",
        methods=["GET", "POST"],  # euPago Webhook 1.0 sends GET
        csrf=False,
        save_session=False,
    )
    def eupago_webhook(self, **data):
        """Process payment notification from euPago.

        euPago Webhook 1.0 sends a GET request with URL query parameters
        to the configured callback URL. Parameters include:
        - identificador: our internal reference (maps to self.reference)
        - valor: paid amount
        - transacao: euPago's transaction ID
        - mp: payment method code (PC:PT, MW:PT, CC:PT, etc.)
        - entidade: ATM entity (Multibanco only)
        - referencia: ATM reference (Multibanco only)
        - data: payment date

        IMPORTANT: This endpoint MUST return HTTP 200. If it doesn't, euPago
        will retry the notification every 2 minutes for 3 attempts, then hourly
        for 24 hours.

        :param dict data: URL query parameters from euPago webhook
        :return: Empty string (HTTP 200) to acknowledge the notification
        :rtype: str
        """
        _logger.info("euPago webhook notification received:\n%s", pprint.pformat(data))

        # Determine the provider code from the mp (payment method) field
        mp_code = data.get(const.WEBHOOK_FIELD_PAYMENT_METHOD, "")
        provider_code = self._get_provider_code_from_mp(mp_code)

        if not provider_code:
            _logger.warning(
                "euPago webhook: unknown payment method code '%s'. Ignoring.", mp_code
            )
            return ""  # Always return 200

        try:
            # Find the transaction by our internal reference ('identificador')
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                ._get_tx_from_notification_data(provider_code, data)
            )
            if not tx_sudo:
                _logger.warning(
                    "euPago webhook: no transaction found for identificador='%s'",
                    data.get(const.WEBHOOK_FIELD_REFERENCE, "N/A"),
                )
                return ""  # Always return 200

            # Extract and store the numeric TRID immediately. 
            # This ensures we capture it for refunds even if `_process` skips `_apply_updates` 
            # because the transaction was already marked 'done' by the CC return page.
            trid = data.get(const.WEBHOOK_FIELD_TRANSACTION_ID, "")
            if trid and not tx_sudo.cr_eupago_trid:
                tx_sudo.cr_eupago_trid = trid
            if trid and not tx_sudo.provider_reference:
                tx_sudo.provider_reference = trid

            # Process the payment data
            tx_sudo._process_notification_data(data)
            
            # --- NEW CUSTOM REFUND LOGIC ---
            # If this webhook confirmed a refund, generate the credit note.
            if tx_sudo.operation == "refund" and tx_sudo.provider_code == const.PROVIDER_CODE_CC and tx_sudo.state == "done":
                if not tx_sudo.cr_eupago_cn_created:
                    _logger.info("euPago Webhook: Detected successful refund. Generating credit note for tx %s", tx_sudo.reference)
                    tx_sudo._generate_refund_credit_note()

        except Exception:
            # Catch ALL exceptions — we must always return HTTP 200
            _logger.exception(
                "euPago webhook: unexpected error while processing data:\n%s",
                pprint.pformat(data),
            )

        return ""  # HTTP 200 acknowledge

    # =========================================================================
    # CREDIT CARD RETURN — customer returns after 3DS
    # =========================================================================

    @http.route(
        _cc_return_url,
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        save_session=False,
    )
    def eupago_cc_return(self, **data):
        """Process the customer's return from euPago Credit Card (3DS) form.

        euPago redirects the customer's browser back to successUrl/failUrl/
        backUrl after the 3DS form is completed. Each URL now carries a distinct
        `outcome` query parameter:
        - ``outcome=success`` → payment confirmed  → set transaction to ``done``
        - ``outcome=fail``    → payment rejected   → set transaction to ``cancel``
        - ``outcome=back``    → customer cancelled → set transaction to ``cancel``

        Setting the state here ensures immediate invoice reconciliation even if
        euPago's async webhook is delayed or lost (e.g. during a network outage).
        The webhook is still processed if it arrives later — idempotency guards
        prevent double-processing.

        :param dict data: URL parameters (includes 'ref' = our reference,
                          'outcome' = success | fail | back)
        :return: Redirect to /payment/status
        """
        _logger.info("euPago CC return received with data:\n%s", pprint.pformat(data))

        outcome = data.get("outcome", "")  # 'success' | 'fail' | 'back' | ''

        try:
            tx_sudo = (
                request.env["payment.transaction"]
                .sudo()
                ._get_tx_from_notification_data(const.PROVIDER_CODE_CC, data)
            )
            if tx_sudo:
                if outcome == "success":
                    # Customer completed 3DS successfully — mark done immediately.
                    # The async webhook will arrive shortly and be a no-op (already done).
                    if tx_sudo.state not in ("done", "cancel", "error"):
                        _logger.info(
                            "CC return success: marking transaction %s as done (outcome=success).",
                            tx_sudo.reference,
                        )
                        tx_sudo._set_done()
                elif outcome in ("fail", "back"):
                    # Customer cancelled or card was rejected.
                    if tx_sudo.state not in ("done", "cancel", "error"):
                        reason = (
                            _("Payment cancelled by customer.")
                            if outcome == "back"
                            else _("Payment rejected by card issuer.")
                        )
                        _logger.info(
                            "CC return %s: marking transaction %s as cancel.",
                            outcome,
                            tx_sudo.reference,
                        )
                        tx_sudo._set_canceled(reason)
                else:
                    # No outcome param (legacy / manual redirect) — mark pending,
                    # rely on webhook for final confirmation.
                    if tx_sudo.state == "draft":
                        _logger.info(
                            "CC return: no outcome for %s, setting pending.",
                            tx_sudo.reference,
                        )
                        tx_sudo._set_pending()
            else:
                _logger.warning(
                    "euPago CC return: no transaction found for ref='%s'",
                    data.get("ref", "N/A"),
                )
        except Exception:
            _logger.exception(
                "euPago CC return: unexpected error while processing data:\n%s",
                pprint.pformat(data),
            )
        
        return request.redirect("/payment/status")

    # =========================================================================
    # FRONTEND JS CONFIGURATION FETCHERS
    # =========================================================================

    @http.route(
        ["/custom/eupago/provider_config"], type="json", auth="public", csrf=False
    )
    def get_eupago_provider_config(self, provider_code="eupago_cc"):
        provider = (
            request.env["payment.provider"]
            .sudo()
            .search([("code", "=", provider_code)], limit=1)
        )
        if not provider:
            return {}
        return {
            "cr_eupago_is_extra_fees": provider.cr_eupago_is_extra_fees,
            "cr_eupago_is_free_domestic": provider.cr_eupago_is_free_domestic,
            "cr_eupago_is_free_international": provider.cr_eupago_is_free_international,
            "cr_eupago_free_domestic_amount": provider.cr_eupago_free_domestic_amount,
            "cr_eupago_free_international_amount": provider.cr_eupago_free_international_amount,
            "cr_eupago_fix_domestic_fees": provider.cr_eupago_fix_domestic_fees,
            "cr_eupago_var_domestic_fees": provider.cr_eupago_var_domestic_fees,
            "cr_eupago_fix_international_fees": provider.cr_eupago_fix_international_fees,
            "cr_eupago_var_international_fees": provider.cr_eupago_var_international_fees,
            "company_id": provider.company_id.id,
        }

    @http.route(
        ["/custom/eupago/company_country/<int:company_id>"],
        type="json",
        auth="public",
        csrf=False,
    )
    def get_company_country(self, company_id):
        company = request.env["res.company"].sudo().browse(company_id)
        return {"country_id": company.country_id.id if company.country_id else None}

    @http.route(
        ["/custom/eupago/document_shipping_country/<int:doc_id>"],
        type="json",
        auth="public",
        csrf=False,
    )
    def get_document_shipping_country(self, doc_id, is_invoice=False):
        if is_invoice:
            invoice = request.env["account.move"].sudo().browse(doc_id)
            if hasattr(invoice, "partner_shipping_id") and invoice.partner_shipping_id:
                partner = invoice.partner_shipping_id
            else:
                partner = invoice.partner_id
        else:
            order = request.env["sale.order"].sudo().browse(doc_id)
            partner = order.partner_shipping_id or order.partner_id
        
        return {
            "country_id": (
                partner.country_id.id if partner and partner.country_id else None
            )
        }

    # =========================================================================
    # MB WAY STATUS POLLING (optional) — for real-time UI feedback
    # =========================================================================

    @http.route(
        _mbway_status_url,
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def eupago_mbway_status(self, ref=None, **kwargs):
        """Poll MB WAY transaction status for real-time UI updates.

        Called by the frontend JS to check if the MB WAY push has been
        confirmed by the customer. The transaction state is read from Odoo.

        :param str ref: Our internal transaction reference
        :return: dict with 'state' key
        :rtype: dict
        """
        if not ref:
            return {"state": "unknown"}

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            .search(
                [
                    ("reference", "=", ref),
                    ("provider_code", "=", const.PROVIDER_CODE_MBWAY),
                ],
                limit=1,
            )
        )
        if not tx_sudo:
            return {"state": "unknown"}

        return {"state": tx_sudo.state}

    @http.route(
        "/payment/cr_eupago/mbway/pay",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def eupago_mbway_pay(self, reference, phone, **kwargs):
        """Call euPago API to send MB WAY push notification for draft transaction.

        :param str reference: Our internal transaction reference
        :param str phone: MB WAY customer phone number
        :return: dict with status key
        :rtype: dict
        """
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            .search(
                [
                    ("reference", "=", reference),
                    ("provider_code", "=", const.PROVIDER_CODE_MBWAY),
                ],
                limit=1,
            )
        )
        if not tx_sudo:
            raise ValidationError("Transaction not found")

        # Call the private render method which prepares the payload, calls euPago API, and sets transaction to pending
        rendering_values = tx_sudo._eupago_render_mbway({"cr_eupago_phone": phone})
        if not rendering_values:
            raise ValidationError(
                tx_sudo.state_message or "Failed to initiate MB WAY payment"
            )

        return {"status": "pending"}

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _get_provider_code_from_mp(mp_code):
        """Map euPago's payment method code (mp field) to our provider_code.

        :param str mp_code: euPago's mp field value (e.g., 'PC:PT', 'MW:PT')
        :return: Odoo provider code or None if not recognized
        :rtype: str | None
        """
        mapping = {
            const.EUPAGO_MP_MULTIBANCO: const.PROVIDER_CODE_MBREF,
            const.EUPAGO_MP_MBWAY: const.PROVIDER_CODE_MBWAY,
            const.EUPAGO_MP_CC: const.PROVIDER_CODE_CC,
        }
        return mapping.get(mp_code)
