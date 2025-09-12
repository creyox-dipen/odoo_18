# # Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# import logging
# import pprint
#
# from odoo import http
# from odoo.http import request
# from odoo.exceptions import ValidationError
#
# from odoo.addons.payment_stripe.controllers.main import StripeController
# from odoo.addons.payment_stripe.const import HANDLED_WEBHOOK_EVENTS
#
# _logger = logging.getLogger(__name__)
#
#
# # Extend handled events with ACH-related ones
# ACH_EVENTS = [
#     "payment_intent.processing",   # ACH debits are being verified/collected
#     "charge.succeeded",            # Final ACH settlement confirmation
#     "payment_intent.succeeded",    # Sometimes Stripe still sends this for ACH
# ]
# for ev in ACH_EVENTS:
#     if ev not in HANDLED_WEBHOOK_EVENTS:
#         HANDLED_WEBHOOK_EVENTS.append(ev)
#
#
# class StripeACHController(StripeController):
#
#     @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
#     def stripe_webhook(self):
#         """Extend Stripe webhook handler to support ACH events."""
#         event = request.get_json_data()
#         print(event)
#         _logger.info("[ACH] Stripe Webhook received: %s", pprint.pformat(event))
#
#         try:
#             if event["type"] not in HANDLED_WEBHOOK_EVENTS:
#                 _logger.info("[ACH] Ignoring unhandled event type: %s", event["type"])
#                 return request.make_json_response("")
#
#             stripe_object = event["data"]["object"]
#             print(event['data'])
#             print(stripe_object)
#             # Build minimal notification data
#             data = {
#                 "reference": stripe_object.get("description"),
#                 "event_type": event["type"],
#                 "object_id": stripe_object["id"],
#             }
#
#             tx_sudo = request.env["payment.transaction"].sudo()._get_tx_from_notification_data(
#                 "stripe", data
#             )
#             self._verify_notification_signature(tx_sudo)
#
#             if event["type"] == "charge.succeeded":
#                 # ACH settlement confirmed
#                 _logger.info("[ACH] Processing charge.succeeded for tx %s", tx_sudo.reference)
#                 self._include_payment_intent_in_notification_data(stripe_object, data)
#
#             elif event["type"] == "payment_intent.processing":
#                 # Funds are being collected - keep tx pending
#                 _logger.info("[ACH] Payment is processing for tx %s", tx_sudo.reference)
#                 self._include_payment_intent_in_notification_data(stripe_object, data)
#
#             elif event["type"] == "payment_intent.succeeded":
#                 # Final confirmation
#                 _logger.info("[ACH] Payment intent succeeded for tx %s", tx_sudo.reference)
#                 self._include_payment_intent_in_notification_data(stripe_object, data)
#
#             # Call Odoo's core handler
#             tx_sudo._handle_notification_data("stripe", data)
#
#         except ValidationError:
#             _logger.exception("[ACH] Unable to handle webhook; skipping but acknowledging")
#
#         # Always acknowledge the webhook to Stripe
#         return request.make_json_response("")

from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController
import logging

_logger = logging.getLogger(__name__)
class StripeController(StripeController):

    @http.route(StripeController._webhook_url, type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self):
        event = request.get_json_data()
        # Pre-process ACH-specific data (inject reference if missing)
        stripe_object = event["data"]["object"]
        metadata = stripe_object.get("metadata", {})

        if not stripe_object.get("description") and metadata.get("tx_id"):
            # Patch the object so Odoo base handler can find the transaction
            stripe_object["description"] = metadata["tx_id"]

        # Call Odoo’s original webhook handler
        response = super().stripe_webhook()
        # Post-process ACH finalization
        if event["type"] in ("payment_intent.succeeded", "charge.succeeded"):
            tx_id = metadata.get("tx_id")
            _logger.info("tx id : %s",tx_id)
            if tx_id:
                tx = request.env["payment.transaction"].sudo().browse(int(tx_id))
                if tx and tx.state not in ("done", "cancel"):
                    tx._set_done()
                    tx._finalize_post_processing()

        return response