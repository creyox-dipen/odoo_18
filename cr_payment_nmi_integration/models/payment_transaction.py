# -*- coding: utf-8 -*-
# Part of Creyox Technologies

import logging
import urllib.parse
import requests

from werkzeug import urls

from odoo import _, api, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.cr_payment_nmi_integration import const
from odoo.addons.cr_payment_nmi_integration.controllers.main import NmiController
from odoo.http import request
import hashlib


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    """Extends the payment.transaction model with NMI-specific rendering,
    notification lookup, and state-processing logic for both the Ekashu card
    redirect flow and the NMI Direct Post ACH flow.
    """

    _inherit = 'payment.transaction'

    def _get_specific_processing_values(self, processing_values):
        """Override to add NMI-specific processing values.

        For ACH (ach_direct_debit), we add the metadata needed by the frontend
        to submit the bank details to our local controller.
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'nmi':
            return res

        if self.payment_method_code == 'ach_direct_debit':
            res.update({
                'reference': self.reference,
                'amount': self.amount,
                'partner_name': self.partner_name,
                'ach_process_url': NmiController._ach_process_url,
            })
        return res

    def _get_specific_rendering_values(self, processing_values):
        """Override to build provider-specific rendering values.

        NMI card payments are processed via Direct Post through our own
        controller (/payment/nmi/card/process), handled entirely by
        nmi_card_form.js. We intentionally return an empty dict here so that
        Odoo's base JS uses _processDirectFlow instead of _processRedirectFlow.
        _processRedirectFlow would crash with a TypeError because there is no
        redirect form element to populate.

        ACH (ach_direct_debit) is similarly a direct flow managed by
        nmi_ach_form.js and also falls through to the empty res.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'nmi':
            return res
        # Return empty dict for all NMI methods (card and ACH).
        # nmi_card_form.js / nmi_ach_form.js intercept the Pay Now button and
        # submit directly to our controllers — no redirect form is needed.
        return res

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override to find a transaction from incoming NMI notification data.

        Handles both the Ekashu card callback (uses ekashu_reference) and the
        NMI ACH Direct Post response (uses orderid / reference). Falls through to
        the Odoo core lookup first; only applies NMI-specific logic if needed.

        :param str provider_code: The provider code, e.g. 'nmi'.
        :param dict notification_data: The POST data from the callback or controller.
        :return: The matching payment.transaction record.
        :rtype: payment.transaction recordset
        :raises ValidationError: If no matching transaction can be found.
        """
        # In Odoo 19 the base payment.transaction no longer defines
        # _get_tx_from_notification_data, so we guard with try/except to stay
        # compatible with both Odoo 17/18 (method exists) and 19 (removed).
        try:
            tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        except AttributeError:
            tx = self.env['payment.transaction']

        if provider_code != 'nmi' or len(tx) == 1:
            return tx

        # ACH Direct Post response — NMI echoes our orderid back as 'orderid'.
        if notification_data.get('_ach_flow'):
            reference = notification_data.get('orderid') or notification_data.get('reference')
        else:
            # Ekashu card callback.
            reference = notification_data.get('ekashu_reference')

        if not reference:
            raise ValidationError(
                "Nmi: " + _(
                    "Received data with missing reference %(ref)s.",
                    ref=reference,
                )
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'nmi')])
        if not tx:
            raise ValidationError(
                "Nmi: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Override to update the transaction state from NMI notification data."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'nmi':
            return

        # ---- ACH Direct Post response ----------------------------------------
        if notification_data.get('_ach_flow'):
            response_code = notification_data.get('response')
            response_text = notification_data.get('responsetext', 'Unknown error')
            transaction_id = notification_data.get('transactionid', '')

            if not response_code:
                raise ValidationError(
                    "NMI ACH: " + _("Received response with missing status code.")
                )

            if response_code == '1':
                # Approved — mark transaction as paid.
                self.provider_reference = transaction_id
                self._set_done()
                _logger.info(
                    "ACH transaction %s approved by NMI (transactionid=%s).",
                    self.reference,
                    transaction_id,
                )
            elif response_code == '2':
                # Declined by bank.
                _logger.warning(
                    "ACH transaction %s declined by NMI: %s",
                    self.reference,
                    response_text,
                )
                self._set_canceled()
            else:
                # Error / communication failure.
                _logger.warning(
                    "ACH transaction %s failed with NMI error: %s",
                    self.reference,
                    response_text,
                )
                self._set_error("NMI ACH: " + response_text)
            return

        # ---- Ekashu card callback --------------------------------------------
        auth_result = notification_data.get('ekashu_auth_result')

        if not auth_result:
            raise ValidationError("NMI: " + _("Received data with missing status code."))

        if auth_result == 'success':
            self.provider_reference = notification_data.get('ekashu_reference', self.reference)
            self._set_done()
        else:
            _logger.warning(
                "Received data with invalid success code (%s) for transaction reference %s.",
                auth_result,
                self.reference,
            )
            self._set_error("NMI: " + _("Unknown success code: %s", auth_result))

    def _extract_token_values(self, payment_data):
        """Override to extract NMI token values from notification data.

        For ACH transactions that requested tokenisation, NMI returns a
        `customer_vault_id`. We store this as the provider_reference of the
        newly created token.

        :param dict payment_data: The notification / response data dict.
        :return: Dict of create values for the payment.token record.
        :rtype: dict
        """
        res = super()._extract_token_values(payment_data)
        if self.provider_code != 'nmi':
            return res

        vault_id = payment_data.get('customer_vault_id')
        _logger.info("NMI _extract_token_values: vault_id=%s", vault_id)
        if not vault_id:
            return res

        # Build a friendly name depending on whether this is a card or ACH token
        if payment_data.get('ccnumber_last4'):
            # Card payment tokenization
            last_4 = payment_data['ccnumber_last4']
            token_name = _("Card ending in %s", last_4)
        else:
            # ACH payment tokenization
            account_no = payment_data.get('checkaccount', '')
            last_4 = account_no[-4:] if len(account_no) >= 4 else account_no
            token_name = _("ACH account ending in %s", last_4) if last_4 else _("ACH account")

        return {
            'provider_ref': vault_id,
            'payment_details': token_name,
            'nmi_card_type': payment_data.get('card_type', 'unknown'),
        }

    def _extract_amount_data(self, payment_data):
        """Override to extract the amount and currency from NMI notification data.
        
        This method also synchronizes the transaction amount if a surcharge was
        applied during the controller processing, preventing 'Amount Mismatch' errors.
        """
        res = super()._extract_amount_data(payment_data)
        if self.provider_code != 'nmi':
            return res

        # Extract amount from NMI response (Direct Post or Ekashu)
        amount = payment_data.get('amount') or payment_data.get('ekashu_amount')
        currency_code = payment_data.get('currency') or payment_data.get('ekashu_currency')

        if amount:
            float_amount = float(amount)
            
            # If the amount in the response is different from our record, 
            # and it's an ACH/Card flow with a surcharge, update our record 
            # before the base validation occurs.
            if payment_data.get('_ach_flow') and float_amount != self.amount:
                _logger.info("NMI: Synchronizing transaction amount to %s (includes surcharge)", float_amount)
                self.sudo().write({'amount': float_amount})
                self.invalidate_recordset(['amount'])

            return {
                'amount': float_amount,
                'currency_code': currency_code,
            }
        return res

    def _send_payment_request(self):
        """Override to send a token payment request to NMI.

        For NMI ACH, we use the Direct Post API with a `customer_vault_id`
        instead of raw bank details.

        Note: self.ensure_one()
        """
        super()._send_payment_request()
        if self.provider_code != 'nmi':
            return

        if not self.token_id:
            raise ValidationError("NMI: " + _("No token provided for the payment request."))

        # Surcharge Logic for Saved Credit/Debit Cards
        amount_to_charge = self.amount
        surcharge_amount = 0.0
        provider = self.provider_id
        
        # Determine fee based on card type
        fee_percentage = 0.0
        fee_product_code = ''
        fee_label = ''
        
        if self.token_id.nmi_card_type in ('credit', 'charge') and provider.is_nmi_card_fee and provider.nmi_credit_card_fee > 0:
            fee_percentage = provider.nmi_credit_card_fee
            fee_product_code = 'CREDIT_CARD_FEE'
            fee_label = "Credit Card Surcharge"
        elif self.token_id.nmi_card_type == 'debit' and provider.is_nmi_card_fee and provider.nmi_debit_card_fee > 0:
            fee_percentage = provider.nmi_debit_card_fee
            fee_product_code = 'DEBIT_CARD_FEE'
            fee_label = "Debit Card Surcharge"

        if fee_percentage > 0:
            surcharge_amount = (self.amount * fee_percentage) / 100
            amount_to_charge = self.amount + surcharge_amount
            
            # Update the Sale Order to include the fee
            for order in self.sale_order_ids:
                _logger.info("NMI: Adding %s line to order %s (Saved Card)", fee_label, order.name)
                fee_product = self.env['product.template'].sudo().search([
                    ('default_code', '=', fee_product_code)
                ], limit=1)
                
                existing_fee_line = order.order_line.filtered(lambda l: "Surcharge" in l.name)
                if not existing_fee_line:
                    self.env['sale.order.line'].sudo().create({
                        'order_id': order.id,
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id if fee_product else False,
                        'product_uom_qty': 1,
                        'price_unit': surcharge_amount,
                        'sequence': 999,
                    })
                else:
                    existing_fee_line.sudo().write({
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id if fee_product else False,
                        'price_unit': surcharge_amount
                    })
            
            # Update the Odoo transaction amount
            _logger.info("NMI Token Surcharge: Final amount %s for %s", amount_to_charge, self.reference)
            self.sudo().write({'amount': amount_to_charge})

        # Ensure Order ID is unique for every attempt to prevent NMI duplicate blocks
        import time
        attempt_orderid = '%s_%d' % (self.reference, int(time.time()))

        # Build the NMI Direct Post API payload for a vault-based transaction.
        # Reference: https://secure.nmi.com/api/transact.php
        post_payload = {
            'security_key': provider.nmi_security_key,
            'type': 'sale',
            'customer_vault_id': self.token_id.provider_ref,
            'amount': "{:.2f}".format(amount_to_charge),
            'surcharge': "{:.2f}".format(surcharge_amount) if surcharge_amount > 0 else '',
            'orderid': attempt_orderid,
            'currency': self.currency_id.name or 'USD',
        }

        # POST server-side to NMI.
        direct_post_url = provider._nmi_get_direct_post_url()
        _logger.info("Sending NMI token payment request for reference %s", self.reference)

        try:
            import requests as http_requests
            nmi_response = http_requests.post(
                direct_post_url,
                data=post_payload,
                timeout=30,
            )
            nmi_response.raise_for_status()
        except http_requests.exceptions.RequestException as e:
            _logger.error("NMI Direct Post API token request failed: %s", str(e))
            raise ValidationError("NMI : Connection error — %s" % str(e))

        # Parse and process the response.
        result = dict(urllib.parse.parse_qsl(nmi_response.text))
        _logger.info("NMI token payment response for %s: %s", self.reference, result.get('responsetext'))
        # Inject ACH flow marker so _process_notification_data handles it correctly.
        result['_ach_flow'] = True
        result['amount'] = result.get('amount') or post_payload.get('amount')
        result['currency'] = result.get('currency') or post_payload.get('currency')
        self._handle_notification_data('nmi', result)
