# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import pprint
import time
import urllib.parse

import requests as http_requests
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

try:
    from odoo.addons.website_sale.controllers.payment import PaymentPortal as WebsiteSalePaymentPortal
except ImportError:
    WebsiteSalePaymentPortal = http.Controller


_logger = logging.getLogger(__name__)


class NmiController(http.Controller):
    """Handles:
    - /payment/nmi/bin_lookup — JSON-RPC route for card type detection.
    - /payment/nmi/clear_surcharge — Remove fee surcharge lines from sale order.
    - /payment/nmi/token_surcharge — Calculate surcharge for saved tokens.
    - /payment/nmi/ach/process — ACH payment form submission.
    - /payment/nmi/card/process — Card payment form submission.
    """

    _ach_process_url = "/payment/nmi/ach/process"
    _card_process_url = "/payment/nmi/card/process"

    def _update_order_surcharge(self, order, provider, card_type):
        """Update or remove the NMI card fee line on the given sale order based on card type.

        :param recordset order: The sale.order record.
        :param recordset provider: The payment.provider record.
        :param str card_type: 'credit', 'debit', or 'unknown'.
        :return: Tuple of (surcharge_amount, new_total)
        :rtype: tuple
        """
        if not order or not provider or provider.code != "nmi":
            _logger.info("NMI Surcharge update skipped: order=%s, provider=%s", order, provider)
            return 0.0, order.amount_total if order else 0.0

        fee_percentage = 0.0
        fee_product_code = ""
        fee_label = ""

        if (
            card_type in ("credit", "charge")
            and provider.is_nmi_card_fee
            and provider.nmi_credit_card_fee > 0
        ):
            fee_percentage = provider.nmi_credit_card_fee
            fee_product_code = "CREDIT_CARD_FEE"
            fee_label = "Credit Card Surcharge"
        elif (
            card_type == "debit"
            and provider.is_nmi_card_fee
            and provider.nmi_debit_card_fee > 0
        ):
            fee_percentage = provider.nmi_debit_card_fee
            fee_product_code = "DEBIT_CARD_FEE"
            fee_label = "Debit Card Surcharge"

        order_sudo = order.sudo()
        existing_fee_lines = order_sudo.order_line.filtered(
            lambda l: "Surcharge" in (l.name or "")
            or (l.product_id and l.product_id.default_code in ("CREDIT_CARD_FEE", "DEBIT_CARD_FEE"))
        )

        if fee_percentage > 0:
            non_fee_lines = order_sudo.order_line - existing_fee_lines
            base_amount = sum(non_fee_lines.mapped("price_total"))
            if not base_amount and order_sudo.amount_total:
                base_amount = order_sudo.amount_total - sum(existing_fee_lines.mapped("price_total"))

            surcharge_amount = order_sudo.currency_id.round((base_amount * fee_percentage) / 100)
            fee_product = (
                request.env["product.product"]
                .sudo()
                .search([("default_code", "=", fee_product_code)], limit=1)
            )
            if not fee_product:
                template = (
                    request.env["product.template"]
                    .sudo()
                    .search([("default_code", "=", fee_product_code)], limit=1)
                )
                if template:
                    fee_product = template.product_variant_id

            if existing_fee_lines:
                first_line = existing_fee_lines[0]
                if len(existing_fee_lines) > 1:
                    existing_fee_lines[1:].unlink()
                first_line.write({
                    "name": f"{fee_label} ({fee_percentage}%)",
                    "product_id": fee_product.id if fee_product else False,
                    "price_unit": surcharge_amount,
                })
            else:
                request.env["sale.order.line"].sudo().create({
                    "order_id": order_sudo.id,
                    "name": f"{fee_label} ({fee_percentage}%)",
                    "product_id": fee_product.id if fee_product else False,
                    "product_uom_qty": 1,
                    "price_unit": surcharge_amount,
                    "sequence": 999,
                })
            _logger.info(
                "NMI Surcharge line updated on order %s: %s (%s)",
                order_sudo.name,
                fee_label,
                surcharge_amount,
            )
        else:
            if existing_fee_lines:
                _logger.info("NMI Surcharge line unlinked from order %s", order_sudo.name)
                existing_fee_lines.unlink()

        order_sudo.invalidate_recordset(["amount_untaxed", "amount_tax", "amount_total"])
        return surcharge_amount if fee_percentage > 0 else 0.0, order_sudo.amount_total

    def _get_rendered_cart_summary(self, order):
        """Render standard QWeb cart summary templates for website payment page.

        :param recordset order: The sale.order record.
        :return: Dict containing total_html, cart_lines_html, and summary_html.
        :rtype: dict
        """
        if not order:
            return {}
        res = {}
        try:
            order_sudo = order.sudo()
            ctx = {
                "website_sale_order": order_sudo,
                "website": request.website if hasattr(request, "website") else None,
            }
            total_view_id = request.env["ir.model.data"]._xmlid_to_res_id(
                "website_sale.total", raise_if_not_found=False
            )
            if total_view_id:
                try:
                    total_html = request.env["ir.qweb"]._render(total_view_id, ctx)
                    res["total_html"] = total_html
                    res["summary_html"] = total_html
                except Exception as e:
                    _logger.info("Error rendering website_sale.total: %s", str(e))

            cart_lines_id = request.env["ir.model.data"]._xmlid_to_res_id(
                "website_sale.cart_lines", raise_if_not_found=False
            )
            if cart_lines_id:
                try:
                    cart_lines_html = request.env["ir.qweb"]._render(cart_lines_id, ctx)
                    res["cart_lines_html"] = cart_lines_html
                except Exception as e:
                    _logger.info("Error rendering website_sale.cart_lines: %s", str(e))

        except Exception as e:
            _logger.info("Error rendering cart summary: %s", str(e))

        return res

    def _get_active_sale_order(self):
        """Helper method to get the active website sale order from request context or session."""
        order = getattr(request, "cart", None)
        if not order and hasattr(request, "session") and request.session.get("sale_order_id"):
            order = request.env["sale.order"].sudo().browse(request.session.get("sale_order_id")).exists()
        if not order and hasattr(request, "website") and request.website:
            try:
                order = request.website.sale_get_order()
            except Exception:
                pass
        return order

    @http.route(
        "/payment/nmi/bin_lookup",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def nmi_bin_lookup(self, bin_number, provider_id):
        """JSON endpoint for real-time BIN lookup.
        Calls the backend NMI Card Type API and updates the Sale Order surcharge line.
        """
        _logger.info(
            "BIN lookup requested for %s (Provider ID: %s)", bin_number, provider_id
        )
        provider = request.env["payment.provider"].sudo().browse(provider_id)
        if not provider or provider.code != "nmi":
            _logger.info("Provider not found or not NMI for ID %s", provider_id)
            return {"type": "unknown"}

        card_type = provider._nmi_get_card_type(bin_number)
        _logger.info("NMI returned card type: %s for BIN %s", card_type, bin_number)

        order = self._get_active_sale_order()
        _logger.info("Active Sale Order for BIN lookup: %s (ID: %s)", order.name if order else "None", order.id if order else "None")

        surcharge_amount, new_total = 0.0, 0.0
        rendered_summary = {}

        if order:
            surcharge_amount, new_total = self._update_order_surcharge(order, provider, card_type)
            rendered_summary = self._get_rendered_cart_summary(order)

        res = {
            "type": card_type,
            "surcharge_amount": surcharge_amount,
            "new_total": new_total,
        }
        res.update(rendered_summary)
        return res

    @http.route(
        "/payment/nmi/clear_surcharge",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def nmi_clear_surcharge(self, provider_id=None):
        """JSON endpoint to remove NMI card surcharge from the current order.
        Called when switching payment options (e.g. to ACH or token) or clearing card input.
        """
        _logger.info("NMI clear surcharge requested")
        order = self._get_active_sale_order()
        if not order:
            return {"status": "ok"}

        provider = None
        if provider_id:
            provider = request.env["payment.provider"].sudo().browse(provider_id)
        if not provider:
            provider = request.env["payment.provider"].sudo().search([("code", "=", "nmi")], limit=1)

        self._update_order_surcharge(order, provider, "unknown")
        rendered_summary = self._get_rendered_cart_summary(order)

        res = {
            "status": "ok",
            "new_total": order.amount_total,
        }
        res.update(rendered_summary)
        return res

    @http.route(
        "/payment/nmi/token_surcharge",
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def nmi_token_surcharge(self, token_id, provider_id=None):
        """JSON endpoint to update sale order surcharge when a saved NMI token is selected."""
        _logger.info("NMI token surcharge requested for token ID %s", token_id)
        token = request.env["payment.token"].sudo().browse(int(token_id)) if token_id else None
        if not token or token.provider_id.code != "nmi":
            return {"status": "ok"}

        order = self._get_active_sale_order()
        if not order:
            return {"status": "ok"}

        card_type = token.nmi_card_type or "unknown"
        surcharge_amount, new_total = self._update_order_surcharge(order, token.provider_id, card_type)
        rendered_summary = self._get_rendered_cart_summary(order)

        res = {
            "status": "ok",
            "type": card_type,
            "surcharge_amount": surcharge_amount,
            "new_total": new_total,
        }
        res.update(rendered_summary)
        return res

    @http.route(
        _card_process_url, type="http", auth="public", methods=["POST"], csrf=False
    )
    def nmi_card_process(self, **data):
        """Final processing for inline card payments.

        This method is the server-side hub for NMI Direct Post. It:
        1. Recalculates the surcharge for security.
        2. Executes the 'sale' transaction via NMI.
        3. Updates the Odoo transaction record based on the result.
        """
        _logger.info("NMI Card Processing: Reference %s", data.get("reference"))

        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            .search(
                [
                    ("reference", "=", data.get("reference")),
                    ("provider_code", "=", "nmi"),
                ],
                limit=1,
            )
        )

        if not tx_sudo:
            return request.redirect("/payment/status")

        provider = tx_sudo.provider_id
        ccnumber = data.get("ccnumber", "").replace(" ", "")
        ccexp = data.get("ccexp", "").replace("/", "")
        cvv = data.get("cvv", "")
        # Security Re-Validation of Surcharge
        amount_to_charge = tx_sudo.amount
        surcharge_amount = 0.0

        card_type = provider._nmi_get_card_type(ccnumber[:6])

        # Determine fee based on card type
        fee_percentage = 0.0
        fee_product_code = ""
        fee_label = ""

        if (
            card_type in ("credit", "charge")
            and provider.is_nmi_card_fee
            and provider.nmi_credit_card_fee > 0
        ):
            fee_percentage = provider.nmi_credit_card_fee
            fee_product_code = "CREDIT_CARD_FEE"
            fee_label = "Credit Card Surcharge"
        elif (
            card_type == "debit"
            and provider.is_nmi_card_fee
            and provider.nmi_debit_card_fee > 0
        ):
            fee_percentage = provider.nmi_debit_card_fee
            fee_product_code = "DEBIT_CARD_FEE"
            fee_label = "Debit Card Surcharge"

        if fee_percentage > 0:
            has_preexisting_fee = False
            for order in tx_sudo.sale_order_ids:
                existing_fee_lines = order.order_line.filtered(
                    lambda l: "Surcharge" in (l.name or "")
                    or (l.product_id and l.product_id.default_code in ("CREDIT_CARD_FEE", "DEBIT_CARD_FEE"))
                )
                if existing_fee_lines:
                    has_preexisting_fee = True
                    surcharge_amount = sum(existing_fee_lines.mapped("price_subtotal"))
                    break

            if has_preexisting_fee:
                amount_to_charge = tx_sudo.amount
                _logger.info(
                    "NMI Surcharge: Pre-existing fee line found on order. Amount to charge: %s, Surcharge portion: %s",
                    amount_to_charge,
                    surcharge_amount,
                )
            else:
                surcharge_amount = tx_sudo.currency_id.round(
                    (tx_sudo.amount * fee_percentage) / 100
                )
                amount_to_charge = tx_sudo.amount + surcharge_amount

                # Update the Sale Order to include the fee so the totals match
                for order in tx_sudo.sale_order_ids:
                    _logger.info("NMI: Adding %s line to order %s", fee_label, order.name)

                    fee_product = (
                        request.env["product.product"]
                        .sudo()
                        .search([("default_code", "=", fee_product_code)], limit=1)
                    )
                    if not fee_product:
                        template = (
                            request.env["product.template"]
                            .sudo()
                            .search([("default_code", "=", fee_product_code)], limit=1)
                        )
                        if template:
                            fee_product = template.product_variant_id

                    existing_fee_line = order.order_line.filtered(
                        lambda l: "Surcharge" in (l.name or "")
                    )
                    if not existing_fee_line:
                        request.env["sale.order.line"].sudo().create(
                            {
                                "order_id": order.id,
                                "name": f"{fee_label} ({fee_percentage}%)",
                                "product_id": fee_product.id if fee_product else False,
                                "product_uom_qty": 1,
                                "price_unit": surcharge_amount,
                                "sequence": 999,
                            }
                        )
                    else:
                        existing_fee_line.sudo().write(
                            {
                                "name": f"{fee_label} ({fee_percentage}%)",
                                "product_id": fee_product.id if fee_product else False,
                                "price_unit": surcharge_amount,
                            }
                        )

                # Update the Invoices to include the fee so the totals match
                for invoice in tx_sudo.invoice_ids:
                    _logger.info(
                        "NMI: Adding %s line to invoice %s", fee_label, invoice.name
                    )

                    fee_product = (
                        request.env["product.product"]
                        .sudo()
                        .search([("default_code", "=", fee_product_code)], limit=1)
                    )
                    if not fee_product:
                        template = (
                            request.env["product.template"]
                            .sudo()
                            .search([("default_code", "=", fee_product_code)], limit=1)
                        )
                        if template:
                            fee_product = template.product_variant_id

                    if fee_product:
                        invoice_sudo = invoice.sudo()
                        was_posted = invoice_sudo.state == "posted"
                        if was_posted:
                            invoice_sudo.button_draft()

                        existing_fee_line = invoice_sudo.invoice_line_ids.filtered(
                            lambda l: l.product_id.default_code
                            in ("CREDIT_CARD_FEE", "DEBIT_CARD_FEE")
                        )

                        account = (
                            fee_product.property_account_income_id
                            or fee_product.categ_id.property_account_income_categ_id
                        )
                        if account and invoice_sudo.fiscal_position_id:
                            account = invoice_sudo.fiscal_position_id.map_account(account)
                        account_id = account.id if account else False

                        line_vals = {
                            "name": f"{fee_label} ({fee_percentage}%)",
                            "product_id": fee_product.id,
                            "quantity": 1,
                            "price_unit": surcharge_amount,
                            "tax_ids": [(5, 0, 0)],
                        }
                        if account_id:
                            line_vals["account_id"] = account_id

                        if not existing_fee_line:
                            invoice_sudo.write({"invoice_line_ids": [(0, 0, line_vals)]})
                        else:
                            existing_fee_line.write(
                                {
                                    "name": f"{fee_label} ({fee_percentage}%)",
                                    "price_unit": surcharge_amount,
                                    "tax_ids": [(5, 0, 0)],
                                }
                            )

                        if was_posted and invoice_sudo.state == "draft":
                            invoice_sudo.action_post()

                # Update the Odoo transaction amount to reflect the new total
                _logger.info(
                    "NMI Surcharge: Final amount %s for %s",
                    amount_to_charge,
                    tx_sudo.reference,
                )
                tx_sudo.write({"amount": amount_to_charge})

        # Ensure Order ID is unique for every attempt to prevent NMI duplicate blocks
        import time

        attempt_orderid = "%s_%d" % (tx_sudo.reference, int(time.time()))

        # Direct Post API Payload
        post_payload = {
            "security_key": provider.nmi_security_key,
            "type": "sale",
            "ccnumber": ccnumber,
            "ccexp": ccexp,
            "cvv": cvv,
            "amount": "{:.2f}".format(amount_to_charge),
            "surcharge": (
                "{:.2f}".format(surcharge_amount) if surcharge_amount > 0 else ""
            ),
            "orderid": attempt_orderid,
            "first_name": tx_sudo.partner_name or "",
            "address1": tx_sudo.partner_address or "",
            "city": tx_sudo.partner_city or "",
            "state": tx_sudo.partner_state_id.name or "",
            "zip": tx_sudo.partner_zip or "",
            "country": tx_sudo.partner_country_id.name or "",
            "currency": tx_sudo.currency_id.name or "USD",
        }

        if provider.state == "enabled" and tx_sudo.partner_email:
            post_payload["email"] = tx_sudo.partner_email

        # If the user requested to save their card, add it to the NMI Customer Vault
        _logger.info("NMI Card: tokenize flag=%s", data.get("tokenize"))
        if data.get("tokenize") == "1":
            tx_sudo.tokenize = True
            post_payload["customer_vault"] = "add_customer"
            _logger.info("NMI Card: customer_vault=add_customer added to payload")

        try:
            api_url = provider._nmi_get_direct_post_url()
            response = http_requests.post(api_url, data=post_payload, timeout=30)
            response.raise_for_status()
            result = dict(urllib.parse.parse_qsl(response.text))

            # Use Odoo's internal processing flow
            result.update(
                {
                    "_ach_flow": True,
                    "orderid": tx_sudo.reference,
                    "amount": result.get("amount") or "{:.2f}".format(amount_to_charge),
                    "currency": result.get("currency") or tx_sudo.currency_id.name,
                    # Pass last 4 digits for a friendly token name
                    "ccnumber_last4": ccnumber[-4:] if len(ccnumber) >= 4 else ccnumber,
                    "card_type": card_type,
                }
            )
            tx_sudo._handle_notification_data("nmi", result)

        except Exception as e:
            _logger.info("NMI Card API Error: %s", str(e))
            tx_sudo._set_error("NMI Card: Connection failure.")

        return request.redirect("/payment/status")

    @http.route(
        _ach_process_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def nmi_ach_process(self, **data):
        """Process an ACH (eCheck) payment submitted from the Odoo checkout page.

        Flow:
        1. Find the matching transaction from the posted 'reference' field.
        2. Build the NMI Direct Post API payload using the merchant Security Key.
        3. Perform a server-side HTTPS POST to the NMI Direct Post API endpoint.
        4. Parse the NMI response (key=value query-string format).
        5. Inject an _ach_flow marker so process_notification_data uses the ACH branch.
        6. Update the transaction state via _process_notification_data.
        7. Redirect the customer to Odoo's standard payment status page.

        :param dict data: POST parameters from the ACH form (reference, amount,
                          checkname, checkaba, checkaccount, account_type,
                          account_holder_type).
        :return: HTTP redirect to /payment/status.
        """
        _logger.info(
            "Processing NMI ACH payment for reference: %s", data.get("reference")
        )

        # Step 1: Find the transaction.
        tx_sudo = (
            request.env["payment.transaction"]
            .sudo()
            ._get_tx_from_notification_data(
                "nmi", {"reference": data.get("reference"), "_ach_flow": True}
            )
        )

        provider = tx_sudo.provider_id

        attempt_orderid = "%s_%d" % (data.get("reference", ""), int(time.time()))

        post_payload = {
            "security_key": provider.nmi_security_key,
            "type": "sale",
            "payment": "check",
            "checkname": data.get("checkname", ""),
            "checkaba": data.get("checkaba", ""),  # 9-digit routing number
            "checkaccount": data.get("checkaccount", ""),
            "account_holder_type": data.get("account_holder_type", "personal"),
            "account_type": data.get("account_type", "checking"),
            "sec_code": "WEB",  # Standard for online transactions
            "amount": data.get("amount", ""),
            "orderid": attempt_orderid,  # Unique per attempt — prevents orderid-based duplicate detection
            "first_name": tx_sudo.partner_name or "",
            "address1": tx_sudo.partner_address or "",
            "city": tx_sudo.partner_city or "",
            "state": tx_sudo.partner_state_id.name or "",
            "zip": tx_sudo.partner_zip or "",
            "country": tx_sudo.partner_country_id.name or "",
            "phone": tx_sudo.partner_phone or "",
            "currency": tx_sudo.currency_id.name or "USD",
        }

        # Handle tokenisation (saving bank details to NMI Customer Vault)
        if data.get("tokenize") in (True, "true", "1"):
            tx_sudo.tokenize = True
            post_payload["customer_vault"] = "add_customer"

        if provider.state == "enabled" and tx_sudo.partner_email:
            post_payload["email"] = tx_sudo.partner_email

        direct_post_url = provider._nmi_get_direct_post_url()
        _logger.info("Sending ACH request to NMI Direct Post API: %s", direct_post_url)

        try:
            nmi_response = http_requests.post(
                direct_post_url,
                data=post_payload,
                timeout=30,
            )
            nmi_response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            _logger.info("NMI Direct Post API request failed: %s", str(e))
            tx_sudo._set_error("NMI ACH: Connection error — %s" % str(e))
            return request.redirect("/payment/status")

        result = dict(urllib.parse.parse_qsl(nmi_response.text))
        _logger.info(
            "NMI Direct Post ACH response for reference %s: response=%s, responsetext=%s",
            data.get("reference"),
            result.get("response"),
            result.get("responsetext"),
        )

        result["_ach_flow"] = True
        result["orderid"] = data.get("reference", "")
        result["amount"] = data.get("amount")
        result["currency"] = data.get("currency", "USD")
        result["checkaccount"] = data.get("checkaccount", "")

        tx_sudo._handle_notification_data("nmi", result)

        return request.redirect("/payment/status")


class PaymentPortalNmi(WebsiteSalePaymentPortal):
    """Extends WebsiteSale PaymentPortal controller to synchronize transaction creation amounts
    when an NMI surcharge fee line is present on the sale order.
    """

    @http.route(
        "/shop/payment/transaction/<int:order_id>",
        type="json",
        auth="public",
        website=True,
    )
    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        """Override to synchronize kwargs['amount'] with order_sudo.amount_total when an NMI
        fee surcharge line is present, preventing 'The cart has been updated' ValidationError.
        """
        _logger.info("NMI: shop_payment_transaction called for order_id=%s", order_id)
        try:
            order_sudo = self._document_check_access("sale.order", order_id, access_token)
            if order_sudo and kwargs.get("amount") is not None:
                existing_fee_lines = order_sudo.order_line.filtered(
                    lambda l: "Surcharge" in (l.name or "")
                    or (l.product_id and l.product_id.default_code in ("CREDIT_CARD_FEE", "DEBIT_CARD_FEE"))
                )
                if existing_fee_lines:
                    _logger.info(
                        "NMI Surcharge line present on order %s (%s). Synchronizing kwargs['amount'] from %s to %s",
                        order_sudo.name,
                        order_id,
                        kwargs.get("amount"),
                        order_sudo.amount_total,
                    )
                    kwargs["amount"] = order_sudo.amount_total
        except Exception as e:
            _logger.info("NMI: Pre-transaction check info: %s", str(e))

        return super().shop_payment_transaction(order_id, access_token, **kwargs)
