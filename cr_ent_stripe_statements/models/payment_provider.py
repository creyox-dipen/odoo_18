# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import _, api, fields, models
from odoo.addons.payment_stripe import const
import logging

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    is_stripe_collection = fields.Boolean(
        string="Enable Stripe Bank Statement Collection"
    )
    stripe_fees_partner = fields.Many2one(
        string="Stripe Fees Partner", comodel_name="res.partner"
    )
    transfer_account = fields.Many2one(
        string="Stripe Transfer Account",
        comodel_name="account.account",
        domain=[("account_type", "=", "asset_cash")],
    )

    def action_stripe_create_webhook(self):
        """Create or update a webhook with additional events and return a feedback notification.

        Note: This action only works for instances using a public URL

        :return: The feedback notification
        :rtype: dict
        """
        self.ensure_one()

        if not self.stripe_secret_key:
            message = _(
                "You cannot create a Stripe Webhook if your Stripe Secret Key is not set."
            )
            notification_type = "danger"
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": message,
                    "sticky": False,
                    "type": notification_type,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        webhook_url = self._get_stripe_webhook_url()
        extended_events = list(
            set(const.HANDLED_WEBHOOK_EVENTS)
            | {"charge.succeeded", "charge.refunded", "payout.paid"}
        )

        try:
            # List existing webhook endpoints
            endpoints = self._stripe_make_request("webhook_endpoints", method="GET")
            existing_endpoint = next(
                (
                    ep
                    for ep in endpoints.get("data", [])
                    if ep.get("url") == webhook_url
                ),
                None,
            )

            if existing_endpoint:
                current_events = set(existing_endpoint.get("enabled_events", []))
                if current_events != set(extended_events):
                    # Update the endpoint
                    self._stripe_make_request(
                        f"webhook_endpoints/{existing_endpoint['id']}",
                        payload={
                            "enabled_events[]": extended_events,
                        },
                        method="POST",
                    )
                    message = _(
                        "Your Stripe Webhook was successfully updated with additional events."
                    )
                    notification_type = "info"
                    _logger.info(
                        "Updated Stripe webhook endpoint %s with events: %s",
                        existing_endpoint["id"],
                        extended_events,
                    )
                else:
                    message = _(
                        "Your Stripe Webhook is already set up with the required events."
                    )
                    notification_type = "warning"
            else:
                # Create new webhook
                webhook = self._stripe_make_request(
                    "webhook_endpoints",
                    payload={
                        "url": webhook_url,
                        "enabled_events[]": extended_events,
                        "api_version": const.API_VERSION,
                    },
                    method="POST",
                )
                self.stripe_webhook_secret = webhook.get("secret")
                message = _("Your Stripe Webhook was successfully set up!")
                notification_type = "info"
                _logger.info(
                    "Created new Stripe webhook endpoint with events: %s",
                    extended_events,
                )

        except Exception as e:
            _logger.info("Error while setting up Stripe webhook: %s", str(e))
            message = _(
                "An error occurred while setting up the Stripe Webhook. Please try again."
            )
            notification_type = "danger"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "sticky": False,
                "type": notification_type,
                "next": {
                    "type": "ir.actions.act_window_close"
                },  # Refresh the form to show the key if updated
            },
        }
