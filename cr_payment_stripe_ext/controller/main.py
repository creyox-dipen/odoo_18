# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
import logging
import psycopg2

from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController

_logger = logging.getLogger(__name__)

class StripeController(StripeController):

    @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self):
        event = request.get_json_data()
        stripe_object = event.get("data", {}).get("object", {})
        metadata = stripe_object.get("metadata", {}) or {}

        # Make sure the base handler can locate the tx
        if not stripe_object.get("description") and metadata.get("tx_id"):
            stripe_object["description"] = metadata["tx_id"]

        # Call the original stripe webhook first (keeps normal logic)
        response = super().stripe_webhook()

        # Only finalize for successful payment events
        if event.get("type") in ("payment_intent.succeeded", "charge.succeeded"):
            tx_id = metadata.get("tx_id")
            _logger.info("Webhook finalization: tx id: %s", tx_id)

            if not tx_id:
                return response

            tx = request.env["payment.transaction"].sudo().browse(int(tx_id))
            if not tx:
                return response

            try:
                # Step 1: ensure transaction is done
                if tx.state not in ("done", "cancel"):
                    _logger.info("Setting tx %s to done", tx.id)
                    tx._set_done()

                # Step 2: run provider post-process (creates account.payment and tries to reconcile)
                if not tx.is_post_processed:
                    _logger.info("Post-processing tx %s", tx.id)
                    try:
                        tx._post_process()
                        _logger.info("Post-process complete for tx %s", tx.id)
                    except (psycopg2.OperationalError, psycopg2.IntegrityError) as db_e:
                        # DB issues: rollback and ask for retry
                        request.env.cr.rollback()
                        raise Exception("retry")
                    except Exception as e:
                        request.env.cr.rollback()
                        # bubble up to let Stripe retry if desired
                        raise

                else:
                    _logger.info("Transaction %s already post-processed", tx.id)

                payment = tx.payment_id or None

                # Force reconciliation if invoice not paid
                for inv in tx.invoice_ids:
                    if payment and payment.move_id:
                        payment_lines = payment.move_id.line_ids.filtered(
                            lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)
                        invoice_lines = inv.line_ids.filtered(
                            lambda l: l.account_type in ['asset_receivable', 'liability_payable'] and not l.reconciled)
                        if payment_lines and invoice_lines:
                            (payment_lines + invoice_lines).reconcile()


            except Exception:
                raise

        return response
