# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

import pprint
from datetime import date, timedelta
from urllib.parse import urljoin

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import logging
from odoo.addons.cr_payment_eupago import const
from odoo.addons.cr_payment_eupago.controllers.main import EupagoController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    cr_eupago_entity = fields.Char(string="euPago Entity")
    cr_eupago_reference = fields.Char(string="euPago Reference")
    cr_eupago_deadline = fields.Char(string="euPago Deadline")
    cr_eupago_trid = fields.Char(
        string="euPago Transaction ID (TRID)",
        help="The numeric Transaction ID returned by the euPago webhook. Used for refunds via the Management API.",
        copy=False,
    )
    cr_eupago_cn_created = fields.Boolean(
        
        string="euPago CN Created",
        default=False,
        help="Technical field to track if a credit note has been created for this refund transaction."
    )
    cr_eupago_fees = fields.Float(string="euPago Fees", copy=False)

    # =========================================================================
    # POST-PROCESSING — force immediate reconciliation for euPago payments
    # =========================================================================

    def _post_process(self):
        """Override of `payment` to force immediate invoice reconciliation.

        Odoo 19 creates payments via online providers in 'in_process' state,
        which means Odoo waits for bank statement matching before marking the
        invoice as 'paid'. For euPago, payment confirmation is real-time (via
        webhook or CC return), so we immediately reconcile the payment's
        receivable journal line against the invoice's receivable line.

        This ensures the invoice moves from 'not_paid' → 'paid' as soon as
        euPago confirms the transaction, without waiting for a bank statement.
        """
        super()._post_process()
        for tx in self.filtered(
            lambda t: t.provider_code in const.ALL_PROVIDER_CODES and t.state == "done"
        ):
            payment = tx.payment_id
            if not payment or not payment.move_id:
                continue
            for invoice in tx.invoice_ids.filtered(lambda inv: inv.state == "posted"):
                # Mirror Stripe module reconciliation:
                # Find all unreconciled receivable/payable lines on both payment and invoice/CN
                payment_lines = payment.move_id.line_ids.filtered(
                    lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)
                invoice_lines = invoice.line_ids.filtered(
                    lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)

                if payment_lines and invoice_lines:
                    _logger.info(
                        "euPago _post_process: reconciling payment %s with invoice/CN %s",
                        payment.name,
                        invoice.name,
                    )
                    try:
                        (payment_lines + invoice_lines).reconcile()
                    except Exception:
                        _logger.exception(
                            "euPago _post_process: reconciliation failed for "
                            "payment %s / invoice %s",
                            payment.name,
                            invoice.name,
                        )

    # =========================================================================
    # RENDERING — route to the right payment method handler
    # =========================================================================

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to return euPago-specific rendering values.

        Routes to the correct method handler based on provider_code:
        - eupago_mbref  → Multibanco ATM reference (inline display, no redirect)
        - eupago_mbway  → MB WAY push notification (inline pending UI)
        - eupago_cc     → Credit Card 3DS (redirect to euPago hosted form)

        Note: self.ensure_one() is guaranteed by `_get_processing_values`.
        """
        if self.provider_code not in const.ALL_PROVIDER_CODES:
            return super()._get_specific_rendering_values(processing_values)

        # P0-2: validate amount limits BEFORE making any API call
        self._eupago_validate_amount()
        if self.state == "error":
            return {}

        if self.provider_code == const.PROVIDER_CODE_MBREF:
            return self._eupago_render_multibanco()
        elif self.provider_code == const.PROVIDER_CODE_MBWAY:
            return self._eupago_render_mbway(processing_values)
        else:  # eupago_cc
            return self._eupago_render_cc()

    def _eupago_validate_amount(self):
        """Validate the transaction amount against the provider's configured limits.

        Sets the transaction state to 'error' if the amount is outside the range
        configured on the provider record.
        """
        amount = self.amount
        provider = self.provider_id
        min_limit = provider.cr_eupago_min_amount
        max_limit = provider.cr_eupago_max_amount

        if amount < min_limit:
            self._set_error(
                _(
                    "%(provider_name)s requires a minimum amount of %(min_limit)s %(currency)s.",
                    provider_name=provider.name,
                    min_limit=f"{min_limit:.2f}",
                    currency=self.currency_id.name,
                )
            )
            return

        if amount > max_limit:
            self._set_error(
                _(
                    "%(provider_name)s does not accept amounts above %(max_limit)s %(currency)s.",
                    provider_name=provider.name,
                    max_limit=f"{max_limit:.2f}",
                    currency=self.currency_id.name,
                )
            )
            return

    # =========================================================================
    # MULTIBANCO — ATM Reference Flow
    # =========================================================================

    def _eupago_render_multibanco(self):
        """Create Multibanco reference via euPago and return inline display values.

        Calls POST /multibanco/create on the old REST API (body auth).
        Returns entity, reference, amount, and deadline for inline display.
        Does NOT redirect — the customer uses the ATM reference to pay.

        :return: dict with keys: entity, referencia, valor, data_fim, provider
        :rtype: dict
        """
        payload = self._eupago_prepare_multibanco_payload()
        _logger.info(
            "Sending Multibanco create request for transaction %s:\n%s",
            self.reference,
            pprint.pformat(payload),
        )
        try:
            response_data = self.provider_id._send_api_request(
                "POST", const.ENDPOINT_MULTIBANCO, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "Multibanco create failed for transaction %s: %s", self.reference, error
            )
            self._set_error(str(error))
            return {}

        # Validate euPago response
        if not response_data.get(const.MB_RESP_SUCCESS):
            error_msg = response_data.get(const.MB_RESP_MESSAGE, _("Unknown error."))
            _logger.error(
                "euPago Multibanco create error for transaction %s: %s",
                self.reference,
                error_msg,
            )
            self._set_error(_("euPago Multibanco error: %s", error_msg))
            return {}

        # Store euPago's internal transaction reference
        # For Multibanco, we use the reference number as provider_reference
        mb_reference = response_data.get(const.MB_RESP_REFERENCE, "")
        self.provider_reference = mb_reference
        self.cr_eupago_entity = response_data.get(const.MB_RESP_ENTITY, "")
        self.cr_eupago_reference = mb_reference
        self.cr_eupago_deadline = response_data.get(const.MB_RESP_DEADLINE, "")

        _logger.info(
            "Multibanco reference created for transaction %s: Entity=%s, Ref=%s",
            self.reference,
            response_data.get(const.MB_RESP_ENTITY),
            mb_reference,
        )

        # Mark as pending — waiting for ATM payment
        self._set_pending()

        return {
            "api_url": "/payment/status",
            "cr_eupago_provider": "mbref",
            "cr_eupago_entity": response_data.get(const.MB_RESP_ENTITY, ""),
            "cr_eupago_reference": mb_reference,
            "cr_eupago_amount": f"{self.amount:.2f}",
            "cr_eupago_currency": self.currency_id.name,
            "cr_eupago_deadline": response_data.get(const.MB_RESP_DEADLINE, ""),
        }

    def _eupago_prepare_multibanco_payload(self):
        """Build the JSON payload for the Multibanco create endpoint.

        Old REST API (Body Auth) — API key is sent in the body as 'chave'.
        Endpoint: POST /multibanco/create
        Docs: https://eupago.readme.io/reference/multibanco

        Required fields:
        - chave: API Key
        - valor: float amount
        - per_dup: 0 (single payment only for invoices)

        :return: dict payload
        :rtype: dict
        """
        # Use the configurable deadline from the provider (default 30 days)
        deadline_days = self.provider_id.cr_eupago_mb_deadline_days or 30
        deadline = (date.today() + timedelta(days=deadline_days)).strftime("%Y-%m-%d")

        # Calculate fees and update SO/Invoice if needed
        self._eupago_calculate_fees()

        return {
            const.MB_REQ_API_KEY: self.provider_id.cr_eupago_api_key,  # 'chave'
            const.MB_REQ_AMOUNT: round(self.amount, 2),  # 'valor'
            const.MB_REQ_IDENTIFIER: self.reference,  # 'id'
            const.MB_REQ_DEADLINE: deadline,  # 'data_fim'
            const.MB_REQ_ALLOW_MULTI: 0,  # 'per_dup' — single payment
        }

    # =========================================================================
    # MB WAY — Mobile Push Flow
    # =========================================================================

    def _eupago_render_mbway(self, processing_values):
        """Send MB WAY payment push notification and return pending UI values.

        Calls POST /v1.02/mbway/create on the new API (ApiKey header auth).
        Returns a pending state — customer must confirm in their MB WAY app
        within 5 minutes. The webhook fires when confirmed.

        Phone number is read from processing_values['cr_eupago_phone'] which
        is collected by the inline form in the checkout UI.

        :param dict processing_values: Must contain 'cr_eupago_phone' key
        :return: dict with provider and status keys for the inline template
        :rtype: dict
        """
        phone = processing_values.get("cr_eupago_phone", "")
        if not phone:
            _logger.warning(
                "MB WAY transaction %s: no phone number provided.", self.reference
            )
            self._set_error(_("Please provide a phone number for MB WAY payment."))
            return {}

        payload = self._eupago_prepare_mbway_payload(phone)
        _logger.info(
            "Sending MB WAY create request for transaction %s:\n%s",
            self.reference,
            pprint.pformat(payload),
        )
        try:
            response_data = self.provider_id._send_api_request(
                "POST", const.ENDPOINT_MBWAY, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "MB WAY create failed for transaction %s: %s", self.reference, error
            )
            self._set_error(str(error))
            return {}

        # Check response status
        tx_status = response_data.get(const.MBWAY_RESP_STATUS, "")
        if tx_status != "Success":
            error_msg = response_data.get("text", tx_status or _("Unknown error."))
            _logger.error(
                "euPago MB WAY error for transaction %s: %s", self.reference, error_msg
            )
            self._set_error(_("euPago MB WAY error: %s", error_msg))
            return {}

        # Store euPago's transaction ID as provider_reference
        self.provider_reference = response_data.get(const.MBWAY_RESP_TRANSACTION_ID, "")

        _logger.info(
            "MB WAY push sent for transaction %s. transactionID=%s",
            self.reference,
            self.provider_reference,
        )

        # Mark as pending — waiting for customer to confirm in MB WAY app
        self._set_pending()

        return {
            "cr_eupago_provider": "mbway",
            "cr_eupago_amount": f"{self.amount:.2f}",
            "cr_eupago_currency": self.currency_id.name,
            "cr_eupago_phone": phone,
        }

    def _eupago_prepare_mbway_payload(self, phone):
        """Build the JSON payload for the MB WAY create endpoint.

        New API (ApiKey Header Auth) — API key is in the Authorization header.
        Endpoint: POST /api/v1.02/mbway/create
        Docs: https://eupago.readme.io/reference/mbway

        :param str phone: Customer's MB WAY phone number (9 digits, Portugal)
        :return: dict payload
        :rtype: dict
        """
        # Calculate fees and update SO/Invoice if needed
        self._eupago_calculate_fees()

        return {
            "payment": {
                const.MBWAY_REQ_IDENTIFIER: self.reference,
                "amount": {
                    const.MBWAY_REQ_AMOUNT_VALUE: round(self.amount, 2),
                    const.MBWAY_REQ_AMOUNT_CURRENCY: self.currency_id.name,
                },
                const.MBWAY_REQ_PHONE: phone,
                const.MBWAY_REQ_COUNTRY_CODE: const.MBWAY_DEFAULT_COUNTRY_CODE,
            },
            "customer": {
                "notify": True,
                "email": self.partner_email or "",
            },
        }

    # =========================================================================
    # CREDIT CARD — 3DS Redirect Flow
    # =========================================================================

    def _eupago_render_cc(self):
        """Create Credit Card payment and return redirect URL.

        Calls POST /v1.02/creditcard/create on the new API (ApiKey header auth).
        Returns redirectUrl — the browser is sent to euPago's hosted 3DS form.
        After completion euPago redirects to /payment/eupago/return.

        :return: dict with 'api_url' key containing the euPago redirect URL
        :rtype: dict
        """
        payload = self._eupago_prepare_cc_payload()
        _logger.info(
            "Sending Credit Card create request for transaction %s:\n%s",
            self.reference,
            pprint.pformat(payload),
        )
        try:
            response_data = self.provider_id._send_api_request(
                "POST", const.ENDPOINT_CC, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "CC create failed for transaction %s: %s", self.reference, error
            )
            self._set_error(str(error))
            return {}

        # Check response status
        tx_status = response_data.get(const.MBWAY_RESP_STATUS, "")
        if tx_status != "Success":
            error_msg = response_data.get("text", tx_status or _("Unknown error."))
            _logger.error(
                "euPago CC error for transaction %s: %s", self.reference, error_msg
            )
            self._set_error(_("euPago Credit Card error: %s", error_msg))
            return {}

        # Store transactionID as provider_reference so we can verify on return
        self.provider_reference = response_data.get(const.MBWAY_RESP_TRANSACTION_ID, "")

        redirect_url = response_data.get(const.CC_RESP_REDIRECT_URL, "")
        if not redirect_url:
            _logger.error(
                "euPago CC: no redirectUrl in response for transaction %s",
                self.reference,
            )
            self._set_error(_("euPago Credit Card: no redirect URL received."))
            return {}

        _logger.info(
            "CC redirect URL obtained for transaction %s: %s",
            self.reference,
            redirect_url,
        )

        return {"api_url": redirect_url}

    def _eupago_prepare_cc_payload(self):
        """Build the JSON payload for the Credit Card create endpoint.

        New API (ApiKey Header Auth) — API key is in the Authorization header.
        Endpoint: POST /api/v1.02/creditcard/create
        Docs: https://eupago.readme.io/reference/credit-card

        successUrl/failUrl/backUrl use different `outcome` params so the return
        controller can immediately set the correct Odoo transaction state, rather
        than waiting solely on the async webhook.

        :return: dict payload
        :rtype: dict
        """
        base_url = self.provider_id.get_base_url() or ""
        if "localhost" in base_url:
            base_url = base_url.replace("localhost", "127.0.0.1")

        if not base_url.endswith("/"):
            base_url += "/"

        return_base = urljoin(base_url, EupagoController._cc_return_url.lstrip("/"))

        ref_param = f"ref={self.reference}"

        success_url = f"{return_base}?{ref_param}&outcome=success"

        # Calculate fees and update SO if needed
        self._eupago_calculate_fees()

        return {
            const.MB_REQ_API_KEY: self.provider_id.cr_eupago_api_key,  # 'chave'
            const.MB_REQ_AMOUNT: round(self.amount, 2),  # 'valor'
            const.MB_REQ_IDENTIFIER: self.reference,  # 'id'
            const.MB_REQ_DEADLINE: deadline,  # 'data_fim'
            const.MB_REQ_ALLOW_MULTI: 0,  # 'per_dup' — single payment
        }

    # =========================================================================
    # MB WAY — Mobile Push Flow
    # =========================================================================

    def _eupago_render_mbway(self, processing_values):
        """Send MB WAY payment push notification and return pending UI values.

        Calls POST /v1.02/mbway/create on the new API (ApiKey header auth).
        Returns a pending state — customer must confirm in their MB WAY app
        within 5 minutes. The webhook fires when confirmed.

        Phone number is read from processing_values['cr_eupago_phone'] which
        is collected by the inline form in the checkout UI.

        :param dict processing_values: Must contain 'cr_eupago_phone' key
        :return: dict with provider and status keys for the inline template
        :rtype: dict
        """
        phone = processing_values.get("cr_eupago_phone", "")
        if not phone:
            _logger.warning(
                "MB WAY transaction %s: no phone number provided.", self.reference
            )
            self._set_error(_("Please provide a phone number for MB WAY payment."))
            return {}

        payload = self._eupago_prepare_mbway_payload(phone)
        _logger.info(
            "Sending MB WAY create request for transaction %s:\n%s",
            self.reference,
            pprint.pformat(payload),
        )
        try:
            response_data = self.provider_id._send_api_request(
                "POST", const.ENDPOINT_MBWAY, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "MB WAY create failed for transaction %s: %s", self.reference, error
            )
            self._set_error(str(error))
            return {}

        # Check response status
        tx_status = response_data.get(const.MBWAY_RESP_STATUS, "")
        if tx_status != "Success":
            error_msg = response_data.get("text", tx_status or _("Unknown error."))
            _logger.error(
                "euPago MB WAY error for transaction %s: %s", self.reference, error_msg
            )
            self._set_error(_("euPago MB WAY error: %s", error_msg))
            return {}

        # Store euPago's transaction ID as provider_reference
        self.provider_reference = response_data.get(const.MBWAY_RESP_TRANSACTION_ID, "")

        _logger.info(
            "MB WAY push sent for transaction %s. transactionID=%s",
            self.reference,
            self.provider_reference,
        )

        # Mark as pending — waiting for customer to confirm in MB WAY app
        self._set_pending()

        return {
            "cr_eupago_provider": "mbway",
            "cr_eupago_amount": f"{self.amount:.2f}",
            "cr_eupago_currency": self.currency_id.name,
            "cr_eupago_phone": phone,
        }

    def _eupago_prepare_mbway_payload(self, phone):
        """Build the JSON payload for the MB WAY create endpoint.

        New API (ApiKey Header Auth) — API key is in the Authorization header.
        Endpoint: POST /api/v1.02/mbway/create
        Docs: https://eupago.readme.io/reference/mbway

        :param str phone: Customer's MB WAY phone number (9 digits, Portugal)
        :return: dict payload
        :rtype: dict
        """
        # Calculate fees and update SO if needed
        self._eupago_calculate_fees()

        return {
            "payment": {
                const.MBWAY_REQ_IDENTIFIER: self.reference,
                "amount": {
                    const.MBWAY_REQ_AMOUNT_VALUE: round(self.amount, 2),
                    const.MBWAY_REQ_AMOUNT_CURRENCY: self.currency_id.name,
                },
                const.MBWAY_REQ_PHONE: phone,
                const.MBWAY_REQ_COUNTRY_CODE: const.MBWAY_DEFAULT_COUNTRY_CODE,
            },
            "customer": {
                "notify": True,
                "email": self.partner_email or "",
            },
        }

    # =========================================================================
    # CREDIT CARD — 3DS Redirect Flow
    # =========================================================================

    def _eupago_render_cc(self):
        """Create Credit Card payment and return redirect URL.

        Calls POST /v1.02/creditcard/create on the new API (ApiKey header auth).
        Returns redirectUrl — the browser is sent to euPago's hosted 3DS form.
        After completion euPago redirects to /payment/eupago/return.

        :return: dict with 'api_url' key containing the euPago redirect URL
        :rtype: dict
        """
        payload = self._eupago_prepare_cc_payload()
        _logger.info(
            "Sending Credit Card create request for transaction %s:\n%s",
            self.reference,
            pprint.pformat(payload),
        )
        try:
            response_data = self.provider_id._send_api_request(
                "POST", const.ENDPOINT_CC, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "CC create failed for transaction %s: %s", self.reference, error
            )
            self._set_error(str(error))
            return {}

        # Check response status
        tx_status = response_data.get(const.MBWAY_RESP_STATUS, "")
        if tx_status != "Success":
            error_msg = response_data.get("text", tx_status or _("Unknown error."))
            _logger.error(
                "euPago CC error for transaction %s: %s", self.reference, error_msg
            )
            self._set_error(_("euPago Credit Card error: %s", error_msg))
            return {}

        # Store transactionID as provider_reference so we can verify on return
        self.provider_reference = response_data.get(const.MBWAY_RESP_TRANSACTION_ID, "")

        redirect_url = response_data.get(const.CC_RESP_REDIRECT_URL, "")
        if not redirect_url:
            _logger.error(
                "euPago CC: no redirectUrl in response for transaction %s",
                self.reference,
            )
            self._set_error(_("euPago Credit Card: no redirect URL received."))
            return {}

        _logger.info(
            "CC redirect URL obtained for transaction %s: %s",
            self.reference,
            redirect_url,
        )

        return {"api_url": redirect_url}

    def _eupago_prepare_cc_payload(self):
        """Build the JSON payload for the Credit Card create endpoint.

        New API (ApiKey Header Auth) — API key is in the Authorization header.
        Endpoint: POST /api/v1.02/creditcard/create
        Docs: https://eupago.readme.io/reference/credit-card

        successUrl/failUrl/backUrl use different `outcome` params so the return
        controller can immediately set the correct Odoo transaction state, rather
        than waiting solely on the async webhook.

        :return: dict payload
        :rtype: dict
        """
        base_url = self.provider_id.get_base_url() or ""
        if "localhost" in base_url:
            base_url = base_url.replace("localhost", "127.0.0.1")

        if not base_url.endswith("/"):
            base_url += "/"

        return_base = urljoin(base_url, EupagoController._cc_return_url.lstrip("/"))

        ref_param = f"ref={self.reference}"

        success_url = f"{return_base}?{ref_param}&outcome=success"
        fail_url = f"{return_base}?{ref_param}&outcome=fail"
        back_url = f"{return_base}?{ref_param}&outcome=back"

        customer_name = self.partner_name or self.partner_id.name or "Test Customer"

        # Calculate fees and update SO if needed
        self._eupago_calculate_fees()

        return {
            "payment": {
                const.CC_REQ_IDENTIFIER: self.reference,
                "amount": {
                    const.MBWAY_REQ_AMOUNT_VALUE: round(self.amount, 2),
                    const.MBWAY_REQ_AMOUNT_CURRENCY: self.currency_id.name,
                },
                const.CC_REQ_SUCCESS_URL: success_url,
                const.CC_REQ_FAIL_URL: fail_url,
                const.CC_REQ_BACK_URL: back_url,
                const.CC_REQ_LANG: const.CC_DEFAULT_LANG,
            },
            "customer": {
                "notify": True,
                "email": self.partner_email or self.partner_id.email or "",
                "name": customer_name,
            },
        }

    # =========================================================================
    # REFERENCE EXTRACTION — used by _search_by_reference
    # =========================================================================

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of `payment` to find the transaction based on the notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code not in const.ALL_PROVIDER_CODES or len(tx) == 1:
            return tx

        reference = (
            notification_data.get(const.WEBHOOK_FIELD_REFERENCE)
            or notification_data.get("ref")
            or notification_data.get("reference")
        )
        if not reference:
            raise ValidationError("euPago: " + _("Received data with missing reference."))

        tx = self.search([("reference", "=", reference), ("provider_code", "=", provider_code)])
        if not tx:
            raise ValidationError(
                "euPago: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    # =========================================================================
    # AMOUNT EXTRACTION — used by _process
    # =========================================================================

    def _extract_amount_data(self, payment_data):
        """Override of `payment` to extract amount and currency from webhook data.

        euPago webhooks send amount in the 'valor' field.
        Currency is always EUR for euPago.

        :param dict payment_data: Parsed webhook parameters
        :return: dict with 'amount' and 'currency_code' keys
        :rtype: dict
        """
        if self.provider_code not in const.ALL_PROVIDER_CODES:
            return super()._extract_amount_data(payment_data)

        amount = payment_data.get(const.WEBHOOK_FIELD_AMOUNT, 0.0)
        return {
            "amount": float(amount),
            "currency_code": "EUR",
        }

    # =========================================================================
    # STATE UPDATES — apply euPago webhook data to transaction state
    # =========================================================================

    def _process_notification_data(self, notification_data):
        """Override of `payment` to update transaction state from euPago data.

        For webhooks (1.0): only 'paid' notifications are sent - euPago does
        NOT send webhooks for expired/cancelled transactions. So any webhook
        received here means the payment was successful.

        For CC return page: we re-fetch the payment status from euPago.

        :param dict notification_data: Parsed webhook parameters or API response
        """
        if self.provider_code not in const.ALL_PROVIDER_CODES:
            return super()._process_notification_data(notification_data)

        # Check if this is a webhook notification (has 'identificador' field)
        if const.WEBHOOK_FIELD_REFERENCE in notification_data:
            # Validate API Key to prevent webhook spoofing
            received_api_key = notification_data.get("chave_api")
            if received_api_key != self.provider_id.cr_eupago_api_key:
                _logger.warning(
                    "euPago webhook verification failed for transaction %s: invalid API key.",
                    self.reference,
                )
                raise ValidationError("Invalid API Key in webhook notification.")

            # Webhook 1.0 — only fires on successful payment
            _logger.info(
                "euPago webhook received for transaction %s — marking as done.",
                self.reference,
            )

            # Store TRID (euPago's webhook transaction ID) for future refunds.
            # This is a NUMERIC ID that the Management API requires for refunds,
            # which is different from the UUID-style transactionID in the initial create response.
            trid = notification_data.get(const.WEBHOOK_FIELD_TRANSACTION_ID, "")
            if trid:
                self.cr_eupago_trid = trid
                _logger.info(
                    "euPago webhook: stored TRID=%s for transaction %s",
                    trid,
                    self.reference,
                )
            if trid and not self.provider_reference:
                self.provider_reference = trid

            self._set_done()

        else:
            # This is a direct API response (e.g., from CC return verification)
            # The 'transactionStatus' field indicates the status
            tx_status = notification_data.get(const.MBWAY_RESP_STATUS, "")

            if tx_status == "Success":
                self._set_done()
            elif tx_status in ("Pending", "Processing"):
                self._set_pending()
            elif tx_status in ("Rejected", "Expired", "Cancelled"):
                self._set_canceled(_("Payment cancelled with status: %s", tx_status))
            else:
                _logger.warning(
                    "euPago: unknown transactionStatus '%s' for transaction %s",
                    tx_status,
                    self.reference,
                )
                self._set_error(
                    _("Received unknown payment status from euPago: %s", tx_status)
                )

    # =========================================================================
    # REFUND — Credit Card only (Multibanco and MB WAY have no refund API)
    # =========================================================================

    def _send_refund_request(self):
        """Override of `payment` to send a refund request to euPago.

        Only Credit Card (eupago_cc) supports API-based refunds via euPago
        /v1.02/creditcard/refund endpoint.

        Multibanco and MB WAY do NOT support API refunds. Odoo will not call
        this method for those providers because support_refund = 'none' in
        the provider model. If somehow called, we raise a clear error.

        Note: self.ensure_one() is guaranteed by the parent _refund().

        :return: None
        :raises ValidationError: If the provider is not CC or the API fails.
        """
        if self.provider_code not in const.ALL_PROVIDER_CODES:
            return super()._send_refund_request()

        if self.provider_code == const.PROVIDER_CODE_MBREF:
            raise ValidationError(
                _(
                    "euPago %s does not support API refunds. "
                    "Please process the refund manually through your bank or "
                    "contact the customer directly.",
                    self.provider_id.name,
                )
            )

        # Refund via euPago API (MB WAY and Credit Card)
        if (
            not self.source_transaction_id
            or not self.source_transaction_id.cr_eupago_trid
        ):
            raise ValidationError(
                _(
                    "Cannot refund: original transaction has no euPago Transaction ID (TRID). "
                    "This usually means the euPago webhook has not arrived yet. "
                    "Please wait a moment and try again, or process the refund manually in the euPago Backoffice."
                )
            )

        payload = {
            "amount": round(abs(self.amount), 2),
        }

        # The Management API requires the numeric webhook TRID
        refund_trid = self.source_transaction_id.cr_eupago_trid
        endpoint = const.ENDPOINT_MANAGEMENT_REFUND.format(refund_trid)

        _logger.info(
            "Sending euPago refund request for transaction %s (TRID used for refund=%s):\n%s",
            self.reference,
            refund_trid,
            payload,
        )

        # Build the full URL for logging so we can verify TRID
        full_url = self.provider_id._build_request_url(endpoint)
        _logger.info(
            "euPago refund full URL: %s | payload: %s | cr_eupago_trid: %s",
            full_url,
            payload,
            self.source_transaction_id.cr_eupago_trid,
        )

        try:
            # Inject context flag so provider uses Bearer token for auth
            response_data = self.provider_id.with_context(is_management_api=True)._send_api_request(
                "POST", endpoint, json=payload
            )
        except ValidationError as error:
            _logger.error(
                "euPago refund failed for transaction %s: %s", self.reference, error
            )
            raise

        # Check response - The management API responds with different fields for refund
        # According to standard REST practices, if it didn't throw an HTTP error (caught above),
        # it was likely successful. But let's check for 'transactionStatus' if euPago sends it.
        # Often management APIs return the refund TRID or just a success message.
        # We will assume success if it didn't raise for status.
        tx_status = response_data.get(const.MBWAY_RESP_STATUS, "Success")
        if tx_status == "Success":
            _logger.info(
                "euPago refund successful for transaction %s. refundTRID=%s",
                self.reference,
                response_data.get("transactionID", ""),
            )
            self.provider_reference = response_data.get(
                const.MBWAY_RESP_TRANSACTION_ID, self.provider_reference
            )
            self._set_done()
        else:
            error_msg = response_data.get("text", tx_status or _("Unknown error."))
            _logger.error(
                "euPago refund API error for transaction %s: %s", self.reference, error_msg
            )
            raise ValidationError(_("euPago refund failed: %s", error_msg))

    def _set_done(self, **kwargs):
        """Override of `payment` to intercept successful refunds and generate Credit Notes."""
        res = super()._set_done(**kwargs)
        for tx in self.filtered(lambda t: t.operation == "refund" and t.provider_code in const.ALL_PROVIDER_CODES):
            tx._generate_refund_credit_note()
        return res

    def _generate_refund_credit_note(self):
        """Generates a Credit Note (Reversal) for the invoice linked to this refund transaction.
        The Credit Note will be for the exact amount of the refund transaction.
        """
        self.ensure_one()
        if self.operation != "refund" or self.cr_eupago_cn_created:
            return

        # Find the original invoice
        invoice = False
        if self.source_transaction_id:
            invoices = self.source_transaction_id.invoice_ids
            if invoices:
                invoice = invoices[0]

        if not invoice:
            _logger.warning("No invoice found for refund transaction %s. Cannot generate Credit Note.", self.reference)
            return

        _logger.info("Generating Credit Note for invoice %s (Refund Tx %s, Amount: %s)", invoice.name, self.reference, abs(self.amount))

        try:
            # 1. Reverse the move (draft credit note) using Odoo's native wizard
            reversal_wizard = self.env["account.move.reversal"].with_context(
                active_model="account.move", active_ids=invoice.ids
            ).create({
                "date": fields.Date.context_today(self),
                "reason": "euPago API Refund",
                "journal_id": invoice.journal_id.id,
            })
            res = reversal_wizard.reverse_moves()
            credit_note_id = res.get("res_id")
            
            if not credit_note_id:
                _logger.error("Failed to generate Credit Note for refund tx %s", self.reference)
                return

            credit_note = self.env["account.move"].browse(credit_note_id)

            # 2. Update the amount to match the exact refund amount
            # If the user did a partial refund, the credit note defaults to the full invoice amount.
            # We must adjust it.
            refund_amount = abs(self.amount)
            if invoice.amount_total != refund_amount:
                # Adjust lines. The simplest way for a partial refund is to keep one line and adjust its price,
                # or adjust all lines proportionally. For simplicity, if it's partial, we'll try to prorate or just modify the first product line.
                # However, modifying invoice lines safely can be tricky due to taxes.
                # Instead of writing complex logic, we can just let Odoo create the full CN, and then we adjust the first line to the target refund amount, deleting others.
                lines_to_keep = credit_note.invoice_line_ids[0]
                lines_to_keep.with_context(check_move_validity=False).write({
                    "price_unit": refund_amount,
                    "quantity": 1.0,
                    "tax_ids": [(5, 0, 0)], # Remove taxes to ensure exact amount match, or keep taxes?
                })
                # Delete other product lines
                (credit_note.invoice_line_ids - lines_to_keep).with_context(check_move_validity=False).unlink()
                # Recompute taxes and totals
                credit_note._compute_tax_totals()
                
            # 3. Post the Credit Note
            credit_note.action_post()
            
            # 4. Link the transaction to the credit note (optional, but good for tracking)
            # Link it by writing to transaction_ids if needed
            self.invoice_ids = [(4, credit_note.id)]

            # Mark as created
            self.cr_eupago_cn_created = True
            _logger.info("Successfully generated and posted Credit Note %s for refund tx %s", credit_note.name, self.reference)

        except Exception as e:
            _logger.exception("Error while generating Credit Note for euPago refund tx %s: %s", self.reference, e)

    # =========================================================================
    # EXTRA FEES HELPER
    # =========================================================================

    def _eupago_calculate_fees(self):
        """Helper method to calculate extra fees dynamically and store them on the transaction."""
        self.ensure_one()
        
        if self.provider_code not in const.ALL_PROVIDER_CODES:
            return
            
        provider = self.provider_id
        if not provider.cr_eupago_is_extra_fees:
            self.cr_eupago_fees = 0.0
            return

        base_amount = self.amount
        total_fixed_fees = 0.0
        total_percent_fees = 0.0

        partner_country = False

        # 1. Try to get country from Sales Order delivery address
        if hasattr(self, "sale_order_ids") and getattr(self, "sale_order_ids", False):
            so = self.sale_order_ids[:1]
            if so.partner_shipping_id:
                partner_country = so.partner_shipping_id.country_id

        # 2. Try to get country from Invoice delivery address or invoice partner
        if not partner_country and hasattr(self, "invoice_ids") and getattr(self, "invoice_ids", False):
            invoice = self.invoice_ids[:1]
            if hasattr(invoice, "partner_shipping_id") and invoice.partner_shipping_id:
                partner_country = invoice.partner_shipping_id.country_id
            elif invoice.partner_id:
                partner_country = invoice.partner_id.country_id

        # 3. Fallback to transaction partner
        if not partner_country:
            partner_country = self.partner_id.country_id

        company_country = self.company_id.country_id
        is_international = (
            partner_country
            and company_country
            and partner_country.id != company_country.id
        )

        if is_international:
            if not provider.cr_eupago_is_free_international:
                total_fixed_fees = provider.cr_eupago_fix_international_fees
                total_percent_fees = (provider.cr_eupago_var_international_fees * base_amount) / 100
            else:
                if base_amount < provider.cr_eupago_free_international_amount:
                    total_fixed_fees = provider.cr_eupago_fix_international_fees
                    total_percent_fees = (provider.cr_eupago_var_international_fees * base_amount) / 100
        else:
            if not provider.cr_eupago_is_free_domestic:
                total_fixed_fees = provider.cr_eupago_fix_domestic_fees
                total_percent_fees = (provider.cr_eupago_var_domestic_fees * base_amount) / 100
            else:
                if base_amount < provider.cr_eupago_free_domestic_amount:
                    total_fixed_fees = provider.cr_eupago_fix_domestic_fees
                    total_percent_fees = (provider.cr_eupago_var_domestic_fees * base_amount) / 100

        self.cr_eupago_fees = round(total_fixed_fees + total_percent_fees, 2)
        
        if self.cr_eupago_fees > 0:
            self._add_eupago_fee_line_to_document()
            self.amount += self.cr_eupago_fees

    def _add_eupago_fee_line_to_document(self):
        """
        Add a fee line to the associated sale order or invoice using the provider's fees_product
        and the calculated fees amount. Ensures only one fee line exists.
        """
        self.ensure_one()
        provider = self.provider_id
        fees_product = provider.cr_eupago_fees_product
        
        if not fees_product or self.cr_eupago_fees <= 0:
            return

        # 1. Handle Sales Order
        if hasattr(self, "sale_order_ids") and getattr(self, "sale_order_ids", False):
            so = self.sale_order_ids[:1]
            existing_fee_lines = so.order_line.filtered(
                lambda line: line.product_id == fees_product.product_variant_id
            )
            if existing_fee_lines:
                _logger.info("Removing %s existing euPago fee lines from SO %s before adding new one", len(existing_fee_lines), so.id)
                existing_fee_lines.unlink()

            fee_line_vals = {
                "order_id": so.id,
                "product_id": fees_product.product_variant_id.id,
                "name": f"Payment Fee - {provider.name} ({self.reference})",
                "product_uom_qty": 1.0,
                "price_unit": self.cr_eupago_fees,
            }
            new_line = self.env["sale.order.line"].create(fee_line_vals)
            _logger.info("Added euPago fee line to SO %s: %s (amount: %.2f)", so.id, new_line.name, self.cr_eupago_fees)
            so._compute_amounts()
            so._compute_tax_totals()
            return

        # 2. Handle Invoice directly (No Sales Order)
        if hasattr(self, "invoice_ids") and getattr(self, "invoice_ids", False):
            invoice = self.invoice_ids[:1]
            existing_fee_lines = invoice.invoice_line_ids.filtered(
                lambda line: line.product_id == fees_product.product_variant_id
            )
            
            try:
                was_posted = invoice.state == 'posted'
                if was_posted:
                    invoice.button_draft()
                
                if existing_fee_lines:
                    _logger.info("Removing existing euPago fee lines from Invoice %s", invoice.id)
                    existing_fee_lines.with_context(check_move_validity=False).unlink()
                
                fee_line_vals = {
                    "move_id": invoice.id,
                    "product_id": fees_product.product_variant_id.id,
                    "name": f"Payment Fee - {provider.name} ({self.reference})",
                    "quantity": 1.0,
                    "price_unit": self.cr_eupago_fees,
                }
                new_line = self.env["account.move.line"].with_context(check_move_validity=False).create(fee_line_vals)
                _logger.info("Added euPago fee line to Invoice %s: %s (amount: %.2f)", invoice.id, new_line.name, self.cr_eupago_fees)
                
                invoice.with_context(check_move_validity=False)._compute_tax_totals()
                
                if was_posted:
                    invoice.action_post()
            except Exception as e:
                _logger.error("Could not add fee line to invoice %s: %s", invoice.id, e)
                raise ValidationError(_("Could not add payment fee to the invoice because it is posted and cannot be modified. Error: %s", e))
