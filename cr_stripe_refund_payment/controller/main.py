# controllers/main.py
import logging

from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController

_logger = logging.getLogger(__name__)


class StripeACHController(StripeController):

    @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self):
        _logger.info("➡️➡️➡️➡️ refund webhook called.")
        event = request.get_json_data()
        stripe_object = event.get("data", {}).get("object", {})
        metadata = stripe_object.get("metadata", {}) or {}

        # # Call Odoo's normal handler first
        response = super().stripe_webhook()

        # reconcile payment journal and credit note journal
        if event.get('type') == "charge.refund.updated":
            # run the cron job to get payment
            request.env['payment.transaction'].sudo()._cron_post_process()

            _logger.info("Charge Refunded Processing...")
            move = request.env['account.move'].sudo().browse(int(metadata.get('move_id')))
            transaction = request.env['payment.transaction'].sudo().browse(int(metadata.get('tx_id')))
            refund_transaction = transaction.child_transaction_ids
            payment = refund_transaction.payment_id
            payment_lines = payment.move_id.line_ids
            credit_note = move.reversal_move_ids
            credit_note_lines = credit_note.line_ids

            # Reconcile payment with the invoice if applicable
            if payment and payment.move_id:
                payment_lines = payment_lines.filtered(
                    lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)
                credit_note_lines = credit_note_lines.filtered(
                    lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)

                if payment_lines and credit_note_lines:
                    (payment_lines + credit_note_lines).reconcile()

        return response

