# from odoo import http
# from odoo.http import request
# from odoo.addons.payment_stripe.controllers.main import StripeController
# import logging

# _logger = logging.getLogger(__name__)
# class StripeController(StripeController):

#     @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
#     def stripe_webhook(self):
#         _logger.info("➡️➡️➡️ webhook initiated")
#         event = request.get_json_data()
#         # Pre-process ACH-specific data (inject reference if missing)
#         stripe_object = event["data"]["object"]
#         metadata = stripe_object.get("metadata", {})

#         if not stripe_object.get("description") and metadata.get("tx_id"):
#             # Patch the object so Odoo base handler can find the transaction
#             stripe_object["description"] = metadata["tx_id"]

#         # Call Odoo’s original webhook handler
#         response = super().stripe_webhook()
#         # Post-process ACH finalization
#         if event["type"] in ("payment_intent.succeeded", "charge.succeeded"):
#             tx_id = metadata.get("tx_id")
#             _logger.info("tx id : %s",tx_id)
#             if tx_id:
#                 tx = request.env["payment.transaction"].sudo().browse(int(tx_id))
#                 _logger.info("TX : %s",tx)
#                 _logger.info("TX : %s",tx.state)
#                 if tx and tx.state not in ("done", "cancel"):
#                     _logger.info("🤣🤣 transaction getting paid")
#                     tx._set_done()
#                     tx._finalize_post_processing()

#         return response

from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController as BaseStripeController
import logging
import psycopg2

_logger = logging.getLogger(__name__)

class StripeController(BaseStripeController):

    @http.route(BaseStripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self):
        _logger.info("➡️➡️➡️ webhook initiated")
        event = request.get_json_data()
        # Pre-process ACH-specific data (inject reference if missing)
        stripe_object = event["data"]["object"]
        metadata = stripe_object.get("metadata", {})

        if not stripe_object.get("description") and metadata.get("tx_id"):
            # Patch the object so Odoo base handler can find the transaction
            stripe_object["description"] = metadata["tx_id"]

        # Call Odoo’s original webhook handler (keeps existing behaviour)
        response = super().stripe_webhook()

        # Post-process ACH finalization: ensure transaction is done AND post-processed
        if event["type"] in ("payment_intent.succeeded", "charge.succeeded"):
            tx_id = metadata.get("tx_id")
            _logger.info("Webhook finalization: tx id : %s", tx_id)
            if tx_id:
                tx = request.env["payment.transaction"].sudo().browse(int(tx_id))
                if not tx:
                    _logger.warning("Transaction id %s not found", tx_id)
                else:
                    try:
                        # If not done, set to done.
                        if tx.state not in ("done", "cancel"):
                            _logger.info("Setting tx %s to done", tx.id)
                            tx._set_done()

                        # Ensure post-processing happens: this creates account.payment / reconciliations.
                        # Call it only if not already post-processed.
                        if not tx.is_post_processed:
                            _logger.info("Post-processing tx %s", tx.id)
                            try:
                                # Post-process in sudo mode (gives access to referenced documents)
                                tx._post_process()
                            except (psycopg2.OperationalError, psycopg2.IntegrityError) as db_e:
                                # rollback and ask for retry (same pattern as Odoo's post_processing)
                                request.env.cr.rollback()
                                _logger.exception("DB error while post-processing tx %s: %s", tx.id, db_e)
                                raise Exception("retry")
                            except Exception as e:
                                request.env.cr.rollback()
                                _logger.exception("Error while post-processing tx %s: %s", tx.id, e)
                                # Don't crash the webhook: re-raise so Stripe retries if you want, or handle it silently.
                                raise
                        else:
                            _logger.info("Transaction %s already post-processed", tx.id)

                    except Exception:
                        # Let exception bubble (Stripe will retry webhooks), but we already logged
                        raise

        return response
