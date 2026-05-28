# -*- coding: utf-8 -*-
# Part of Creyox Technologies

import logging
import pprint
import time
import urllib.parse

import requests as http_requests
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


_logger = logging.getLogger(__name__)


class NmiController(http.Controller):
    """Handles:
    - /payment/nmi/bin_lookup — JSON-RPC route for card type detection.
    - /payment/nmi/ach/process — ACH payment form submission.
    - /payment/nmi/card/process — Card payment form submission.
    """

    _ach_process_url = '/payment/nmi/ach/process'
    _card_process_url = '/payment/nmi/card/process'

    @http.route('/payment/nmi/bin_lookup', type='json', auth='public', methods=['POST'], csrf=False)
    def nmi_bin_lookup(self, bin_number, provider_id):
        """JSON endpoint for real-time BIN lookup.
        Calls the backend NMI Card Type API.
        """
        _logger.info("BIN lookup requested for %s (Provider ID: %s)", bin_number, provider_id)
        provider = request.env['payment.provider'].sudo().browse(provider_id)
        if not provider or provider.code != 'nmi':
            _logger.warning("Provider not found or not NMI for ID %s", provider_id)
            return {'type': 'unknown'}
        
        card_type = provider._nmi_get_card_type(bin_number)
        _logger.info("NMI returned card type: %s for BIN %s", card_type, bin_number)
        return {'type': card_type}

    @http.route(_card_process_url, type='http', auth='public', methods=['POST'], csrf=False)
    def nmi_card_process(self, **data):
        """Final processing for inline card payments.
        
        This method is the server-side hub for NMI Direct Post. It:
        1. Recalculates the surcharge for security.
        2. Executes the 'sale' transaction via NMI.
        3. Updates the Odoo transaction record based on the result.
        """
        _logger.info("NMI Card Processing: Reference %s", data.get('reference'))
        
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', data.get('reference')),
            ('provider_code', '=', 'nmi')
        ], limit=1)
        
        if not tx_sudo:
            return request.redirect('/payment/status')

        provider = tx_sudo.provider_id
        ccnumber = data.get('ccnumber', '').replace(' ', '')
        ccexp = data.get('ccexp', '').replace('/', '')
        cvv = data.get('cvv', '')
           # Security Re-Validation of Surcharge
        amount_to_charge = tx_sudo.amount
        surcharge_amount = 0.0
        
        card_type = provider._nmi_get_card_type(ccnumber[:6])
        
        # Determine fee based on card type
        fee_percentage = 0.0
        fee_product_code = ''
        fee_label = ''
        
        if card_type in ('credit', 'charge') and provider.is_nmi_card_fee and provider.nmi_credit_card_fee > 0:
            fee_percentage = provider.nmi_credit_card_fee
            fee_product_code = 'CREDIT_CARD_FEE'
            fee_label = "Credit Card Surcharge"
        elif card_type == 'debit' and provider.is_nmi_card_fee and provider.nmi_debit_card_fee > 0:
            fee_percentage = provider.nmi_debit_card_fee
            fee_product_code = 'DEBIT_CARD_FEE'
            fee_label = "Debit Card Surcharge"

        if fee_percentage > 0:
            surcharge_amount = tx_sudo.currency_id.round((tx_sudo.amount * fee_percentage) / 100)
            amount_to_charge = tx_sudo.amount + surcharge_amount
            
            # Update the Sale Order to include the fee so the totals match
            for order in tx_sudo.sale_order_ids:
                _logger.info("NMI: Adding %s line to order %s", fee_label, order.name)
                
                fee_product = request.env['product.product'].sudo().search([
                    ('default_code', '=', fee_product_code)
                ], limit=1)

                # Check if a surcharge line already exists to avoid duplicates
                existing_fee_line = order.order_line.filtered(lambda l: "Surcharge" in l.name)
                if not existing_fee_line:
                    request.env['sale.order.line'].sudo().create({
                        'order_id': order.id,
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id if fee_product else False,
                        'product_uom_qty': 1,
                        'price_unit': surcharge_amount,
                        'sequence': 999,
                    })
                else:
                    # Update existing line if amount or type changed
                    existing_fee_line.sudo().write({
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id if fee_product else False,
                        'price_unit': surcharge_amount
                    })
            
            # Update the Invoices to include the fee so the totals match
            for invoice in tx_sudo.invoice_ids:
                _logger.info("NMI: Adding %s line to invoice %s", fee_label, invoice.name)
                
                fee_product = request.env['product.product'].sudo().search([
                    ('default_code', '=', fee_product_code)
                ], limit=1)
                
                if fee_product:
                    invoice_sudo = invoice.sudo()
                    was_posted = invoice_sudo.state == 'posted'
                    if was_posted:
                        invoice_sudo.button_draft()
                    
                    existing_fee_line = invoice_sudo.invoice_line_ids.filtered(
                        lambda l: l.product_id.default_code in ('CREDIT_CARD_FEE', 'DEBIT_CARD_FEE')
                    )
                    
                    account = fee_product.property_account_income_id or fee_product.categ_id.property_account_income_categ_id
                    if account and invoice_sudo.fiscal_position_id:
                        account = invoice_sudo.fiscal_position_id.map_account(account)
                    account_id = account.id if account else False
                    
                    line_vals = {
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id,
                        'quantity': 1,
                        'price_unit': surcharge_amount,
                        'tax_ids': [(5, 0, 0)],
                    }
                    if account_id:
                        line_vals['account_id'] = account_id
                        
                    if not existing_fee_line:
                        invoice_sudo.write({
                            'invoice_line_ids': [(0, 0, line_vals)]
                        })
                    else:
                        existing_fee_line.write({
                            'name': f"{fee_label} ({fee_percentage}%)",
                            'price_unit': surcharge_amount,
                            'tax_ids': [(5, 0, 0)],
                        })
                    
                    if was_posted and invoice_sudo.state == 'draft':
                        invoice_sudo.action_post()
            
            # Update the Odoo transaction amount to reflect the new total
            _logger.info("NMI Surcharge: Final amount %s for %s", amount_to_charge, tx_sudo.reference)
            tx_sudo.write({'amount': amount_to_charge})

        # Ensure Order ID is unique for every attempt to prevent NMI duplicate blocks
        import time
        attempt_orderid = '%s_%d' % (tx_sudo.reference, int(time.time()))

        # Direct Post API Payload
        post_payload = {
            'security_key': provider.nmi_security_key,
            'type': 'sale',
            'ccnumber': ccnumber,
            'ccexp': ccexp,
            'cvv': cvv,
            'amount': "{:.2f}".format(amount_to_charge),
            'surcharge': "{:.2f}".format(surcharge_amount) if surcharge_amount > 0 else '',
            'orderid': attempt_orderid,
            'first_name': tx_sudo.partner_name or '',
            'address1': tx_sudo.partner_address or '',
            'city': tx_sudo.partner_city or '',
            'state': tx_sudo.partner_state_id.name or '',
            'zip': tx_sudo.partner_zip or '',
            'country': tx_sudo.partner_country_id.name or '',
            'currency': tx_sudo.currency_id.name or 'USD',
        }

        if provider.state == 'enabled' and tx_sudo.partner_email:
            post_payload['email'] = tx_sudo.partner_email

        # If the user requested to save their card, add it to the NMI Customer Vault
        _logger.info("NMI Card: tokenize flag=%s", data.get('tokenize'))
        if data.get('tokenize') == '1':
            tx_sudo.tokenize = True
            post_payload['customer_vault'] = 'add_customer'
            _logger.info("NMI Card: customer_vault=add_customer added to payload")


        try:
            api_url = provider._nmi_get_direct_post_url()
            response = http_requests.post(api_url, data=post_payload, timeout=30)
            response.raise_for_status()
            result = dict(urllib.parse.parse_qsl(response.text))

            # Use Odoo's internal processing flow
            result.update({
                '_ach_flow': True,
                'orderid': tx_sudo.reference,
                'amount': result.get('amount') or "{:.2f}".format(amount_to_charge),
                'currency': result.get('currency') or tx_sudo.currency_id.name,
                # Pass last 4 digits for a friendly token name
                'ccnumber_last4': ccnumber[-4:] if len(ccnumber) >= 4 else ccnumber,
                'card_type': card_type,
            })
            tx_sudo._handle_notification_data('nmi', result)
            
        except Exception as e:
            _logger.error("NMI Card API Error: %s", str(e))
            tx_sudo._set_error("NMI Card: Connection failure.")

        return request.redirect('/payment/status')



    @http.route(
        _ach_process_url,
        type='http',
        auth='public',
        methods=['POST'],
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
        _logger.info("Processing NMI ACH payment for reference: %s", data.get('reference'))

        # Step 1: Find the transaction.
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'nmi', {'reference': data.get('reference'), '_ach_flow': True}
        )

        provider = tx_sudo.provider_id

        # Step 2: Build the NMI Direct Post API payload.
        #
        # DUPLICATE TRANSACTION PREVENTION
        # NMI flags a transaction as a duplicate when the same `orderid` is
        # submitted more than once within the gateway's time window, OR when the
        # same account + amount is submitted within `dup_seconds` seconds.
        # Both conditions fire when a user corrects their bank details and retries.
        #
        # Fix 1 — unique orderid per attempt:
        #   Append a Unix timestamp so every attempt has a distinct orderid.
        #   Example: "S00037-1" → "S00037-1_1713097236"
        #   After parsing the NMI response we reset result['orderid'] back to
        #   the plain reference so the Odoo transaction lookup still works.
        #
        # Fix 2 — dup_seconds=0:
        #   Disables NMI's account+amount time-window duplicate detection,
        #   allowing the customer to retry immediately with correct details.
        attempt_orderid = '%s_%d' % (data.get('reference', ''), int(time.time()))

        post_payload = {
            'security_key': provider.nmi_security_key,
            'type': 'sale',
            'payment': 'check',
            'checkname': data.get('checkname', ''),
            'checkaba': data.get('checkaba', ''),         # 9-digit routing number
            'checkaccount': data.get('checkaccount', ''),
            'account_holder_type': data.get('account_holder_type', 'personal'),
            'account_type': data.get('account_type', 'checking'),
            'sec_code': 'WEB',                             # Standard for online transactions
            'amount': data.get('amount', ''),
            'orderid': attempt_orderid,                   # Unique per attempt — prevents orderid-based duplicate detection
            'first_name': tx_sudo.partner_name or '',
            'address1': tx_sudo.partner_address or '',
            'city': tx_sudo.partner_city or '',
            'state': tx_sudo.partner_state_id.name or '',
            'zip': tx_sudo.partner_zip or '',
            'country': tx_sudo.partner_country_id.name or '',
            'phone': tx_sudo.partner_phone or '',
            'currency': tx_sudo.currency_id.name or 'USD',
        }

        # Handle tokenisation (saving bank details to NMI Customer Vault)
        if data.get('tokenize') in (True, 'true', '1'):
            tx_sudo.tokenize = True
            post_payload['customer_vault'] = 'add_customer'

        # NMI sandbox only allows emails to the sandbox account owner's address.
        # Including a customer email in test mode causes a hard rejection from NMI:
        # "Sandbox accounts can only send emails to their own email address".
        # Email is optional for ACH processing — omit it in test/sandbox mode and
        # include it in production so NMI can send payment receipts.
        if provider.state == 'enabled' and tx_sudo.partner_email:
            post_payload['email'] = tx_sudo.partner_email

        # Step 3: POST server-side to NMI (bank details never leave server → NMI channel).
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
            _logger.error("NMI Direct Post API request failed: %s", str(e))
            tx_sudo._set_error("NMI ACH: Connection error — %s" % str(e))
            return request.redirect('/payment/status')

        # Step 4: Parse key=value response string (e.g. "response=1&responsetext=SUCCESS&...")
        result = dict(urllib.parse.parse_qsl(nmi_response.text))
        _logger.info(
            "NMI Direct Post ACH response for reference %s: response=%s, responsetext=%s",
            data.get('reference'),
            result.get('response'),
            result.get('responsetext'),
        )

        # Step 5: Inject ACH flow marker so the transaction model uses the correct branch.
        result['_ach_flow'] = True
        result['orderid'] = data.get('reference', '')
        result['amount'] = data.get('amount')
        result['currency'] = data.get('currency', 'USD')
        result['checkaccount'] = data.get('checkaccount', '')

        # Step 6: Update transaction state.
        tx_sudo._handle_notification_data('nmi', result)

        return request.redirect('/payment/status')

