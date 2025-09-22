# controllers/main.py
import logging
import psycopg2

from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController

_logger = logging.getLogger(__name__)


class StripeACHController(StripeController):

    @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self):
        _logger.info("➡️ Stripe ACH webhook initiated")
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


                payment = tx.payment_id or tx.account_payment_id or None
                if payment:
                    _logger.info("Payment created for tx %s: %s", tx.id, payment.id)
                    # log payment move lines (id, account, balance, reconciled)
                    pm_lines = payment.move_id.line_ids
                    _logger.info(
                        "Payment move lines: %s",
                        [(l.id, l.account_id.display_name, float(l.balance), bool(l.reconciled)) for l in pm_lines]
                    )

                # Force reconciliation if invoice not paid
                for inv in tx.invoice_ids:
                    _logger.info("Invoice %s before reconcile: state=%s payment_state=%s", inv.id, inv.state, inv.payment_state)

                    if inv.payment_state == 'paid':
                        _logger.info("Invoice %s already paid; skipping.", inv.id)
                        continue

                    # invoice receivable lines (unreconciled)
                    inv_receivables = inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled and l.parent_state == 'posted')
                    if not inv_receivables:
                        continue

                    if not payment:
                        continue

                    pay_receivables = payment.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled and l.parent_state == 'posted')
                    if not pay_receivables:
                        # Sometimes payment uses a different account name: try to match by account id from invoice
                        pay_receivables = payment.move_id.line_ids.filtered(lambda l: l.account_id == inv_receivables[0].account_id and not l.reconciled and l.parent_state == 'posted')

                    # Attempt reconciliation per matching account
                    reconciled_any = False
                    for acc in pay_receivables.mapped('account_id'):
                        to_reconcile = (inv_receivables + pay_receivables).filtered(lambda l: l.account_id == acc and not l.reconciled and l.parent_state == 'posted')
                        if not to_reconcile:
                            continue
                        try:
                            # Use a context key used by register payment if needed (keeps parity)
                            ctx = dict(request.env.context or {})
                            ctx.update({'forced_rate_from_register_payment': None})
                            to_reconcile.with_context(**ctx).reconcile()
                            reconciled_any = True
                            _logger.info("Reconciled invoice %s with payment %s on account %s", inv.id, payment.id, acc.display_name)
                        except Exception as e:
                            _logger.info("Failed to reconcile invoice %s with payment %s on account %s: %s", inv.id, payment.id, acc.display_name, e)

                    if not reconciled_any:
                        _logger.info("Could not reconcile invoice %s with payment %s automatically; please check account/partner/currency settings.", inv.id, payment.id if payment else None)

                    # Log invoice state after attempt
                    _logger.info("Invoice %s after reconcile attempt: state=%s payment_state=%s", inv.id, inv.state, inv.payment_state)

            except Exception:
                # Let exception bubble (Stripe will retry)
                raise

        return response
