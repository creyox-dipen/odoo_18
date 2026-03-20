# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, api
from email.utils import parseaddr, getaddresses
import re
import logging

_logger = logging.getLogger(__name__)


class MailThreadAutoFollower(models.AbstractModel):
    _inherit = "mail.thread"

    def _add_to_recipients_as_followers(self, msg_dict):
        """
        Extract email addresses from 'To' and 'CC' headers and add them as followers.
        If a partner with the email already exists, it is subscribed directly.
        If no partner exists, a new one is created and then subscribed.
        """
        to_header = msg_dict.get("to", "")
        cc_header = msg_dict.get("cc", "")

        # Combine 'To' and 'CC' headers so CC recipients are also added as followers
        combined_header = ", ".join(filter(None, [to_header, cc_header]))
        if not combined_header:
            return

        # Extract (name, email) pairs from combined "To" + "CC"
        addr_pairs = getaddresses([combined_header])

        if not addr_pairs:
            return

        partner_model = self.env["res.partner"]
        partner_ids = []

        for name, email in addr_pairs:
            print("name:", name, "email:", email)
            if not email:
                continue
            email = email.lower().strip()
            # Search for existing partner
            partner = partner_model.search([("email", "=ilike", email)], limit=1)

            if not partner:
                # Create new partner if doesn't exist
                print("creating new partner")
                print("name:", name, "email:", email)
                partner = partner_model.create(
                    {
                        "name": name.split("@")[0] or email.split("@")[0],
                        "email": email,
                    }
                )

            # Force email notification for this partner if they are a user
            if partner.user_ids:
                # Set notification type to email for users
                for user in partner.user_ids:
                    if user.notification_type != "email":
                        user.sudo().write({"notification_type": "email"})

            # Avoid duplicates
            if partner.id not in partner_ids:
                partner_ids.append(partner.id)

        # Subscribe partners as followers with ONLY default/relevant subtypes
        if partner_ids:
            try:
                # Get only DEFAULT message subtypes (not all subtypes)
                # This typically includes 'Discussions' but not system subtypes like 'Activities', 'Note', etc.
                subtype_ids = (
                    self.env["mail.message.subtype"]
                    .search(
                        [
                            "|",
                            ("res_model", "=", self._name),
                            ("res_model", "=", False),
                            ("default", "=", True),  # Only default subtypes
                        ]
                    )
                    .ids
                )

                # Remove already subscribed partners to re-subscribe with correct subtypes
                existing_followers = self.message_partner_ids.ids
                partners_to_subscribe = [
                    p for p in partner_ids if p not in existing_followers
                ]
                partners_to_update = [p for p in partner_ids if p in existing_followers]

                # Subscribe new followers
                if partners_to_subscribe:
                    self.message_subscribe(
                        partner_ids=partners_to_subscribe, subtype_ids=subtype_ids
                    )

                # Update existing followers - but DON'T override admin's preferences
                # Only update if they are NOT internal users (to preserve admin's settings)
                if partners_to_update:
                    partners_to_update_filtered = []
                    for pid in partners_to_update:
                        partner = partner_model.browse(pid)
                        # Skip internal users (like admin) - don't change their subscription preferences
                        if not partner.user_ids or not any(
                            u.share == False for u in partner.user_ids
                        ):
                            partners_to_update_filtered.append(pid)

                    if partners_to_update_filtered:
                        followers = self.env["mail.followers"].search(
                            [
                                ("res_model", "=", self._name),
                                ("res_id", "=", self.id),
                                ("partner_id", "in", partners_to_update_filtered),
                            ]
                        )
                        for follower in followers:
                            follower.sudo().write(
                                {"subtype_ids": [(6, 0, subtype_ids)]}
                            )

                _logger.info(
                    f"Added followers from 'To' header: {partner_ids} to {self._name} record {self.id}"
                )
            except Exception as e:
                _logger.error(f"Error adding followers: {str(e)}")

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        Override to add 'To' recipients as followers when creating new records
        """
        record = super().message_new(msg_dict, custom_values=custom_values)

        # Add 'To' recipients as followers
        if record:
            record._add_to_recipients_as_followers(msg_dict)

        return record

    def message_post(self, **kwargs):
        """
        Override message_post to add 'To' recipients as followers AND to partner_ids
        """
        # Check if this is an incoming email
        email_from = kwargs.get("email_from")
        message_type = kwargs.get("message_type", "notification")

        if email_from and message_type in ("comment", "email"):
            # Try to get msg_dict from kwargs or context
            msg_dict = kwargs.get("msg_dict") or self.env.context.get(
                "mail_create_message_dict"
            )

            if msg_dict:
                self._add_to_recipients_as_followers(msg_dict)

                # Store actual sender for use in notifications
                if self.env.context.get("actual_email_sender"):
                    kwargs["email_from"] = self.env.context.get("actual_email_sender")

        subtype_xmlid = kwargs.get("subtype_xmlid", "")

        # CRITICAL: Only add followers to partner_ids when:
        # 1. message_type is 'comment' (user-initiated message, NOT 'notification' for system events)
        # 2. Not an incoming email (email_from is empty)
        # 3. Not a log note
        if (
            message_type == "comment"
            and not email_from
            and subtype_xmlid != "mail.mt_note"
        ):

            # Get the subtype ID
            subtype_id = False
            if subtype_xmlid:
                subtype = (
                    self.env["mail.message.subtype"]
                    .sudo()
                    .search([("name", "=", subtype_xmlid.split(".")[-1])], limit=1)
                )
                if not subtype:
                    subtype = self.env.ref(subtype_xmlid, raise_if_not_found=False)
                if subtype:
                    subtype_id = subtype.id

            # Get followers who are subscribed to this specific subtype
            if subtype_id:
                followers_subscribed_to_subtype = self.env["mail.followers"].search(
                    [
                        ("res_model", "=", self._name),
                        ("res_id", "=", self.id),
                        ("subtype_ids", "in", [subtype_id]),
                    ]
                )
                follower_partners = followers_subscribed_to_subtype.mapped(
                    "partner_id"
                ).ids
            else:
                # If no specific subtype, use all followers (fallback)
                follower_partners = self.message_partner_ids.ids

            _logger.info(
                f"BEFORE message_post - Message Type: {message_type}, Subtype: {subtype_xmlid}"
            )
            _logger.info(
                f"BEFORE message_post - Followers subscribed to subtype: {follower_partners}"
            )
            _logger.info(
                f"BEFORE message_post - kwargs partner_ids: {kwargs.get('partner_ids', [])}"
            )

            if follower_partners:
                existing_partner_ids = kwargs.get("partner_ids", [])
                # Merge follower partners with any explicitly specified partners
                all_partner_ids = list(set(existing_partner_ids + follower_partners))
                kwargs["partner_ids"] = all_partner_ids
                _logger.info(
                    f"AFTER message_post - Updated partner_ids: {all_partner_ids}"
                )

        # Call parent method
        result = super().message_post(**kwargs)

        _logger.info(f"AFTER super().message_post - Result message ID: {result}")

        return result

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        """
        Override to prevent duplicate notifications to TO/CC recipients
        They already received the original email, no need to send Odoo notification
        """
        for route in routes:
            model, thread_id, custom_values, user_id, alias = route
            if thread_id and model:
                try:
                    record = self.env[model].browse(thread_id)
                    if record.exists():
                        existing_follower_ids = record.message_partner_ids.ids

                        to_header = message_dict.get("to", "")
                        cc_header = message_dict.get("cc", "")
                        from_header = message_dict.get("from", "")

                        # Combine TO and CC headers
                        all_recipients_header = (
                            to_header + "," + cc_header if cc_header else to_header
                        )

                        if all_recipients_header:
                            addr_pairs = getaddresses([all_recipients_header])

                            partner_model = self.env["res.partner"]
                            partner_ids = []
                            recipients_who_already_got_email = []

                            for name, email in addr_pairs:
                                if not email:
                                    continue
                                email = email.lower().strip()
                                partner = partner_model.search(
                                    [("email", "=ilike", email)], limit=1
                                )

                                if not partner:
                                    partner = partner_model.create(
                                        {
                                            "name": name.split("@")[0]
                                            or email.split("@")[0],
                                            "email": email,
                                        }
                                    )

                                if partner.user_ids:
                                    for user in partner.user_ids:
                                        if user.notification_type != "email":
                                            user.sudo().write(
                                                {"notification_type": "email"}
                                            )

                                if partner.id not in partner_ids:
                                    partner_ids.append(partner.id)
                                    # These partners ALREADY received the email from the original sender
                                    # Don't send them another notification from Odoo
                                    recipients_who_already_got_email.append(partner.id)

                            if partner_ids:

                                _logger.info(
                                    f"Recipients who already got the original email: {recipients_who_already_got_email}"
                                )
                                _logger.info(
                                    f"NOT sending duplicate Odoo notifications to them"
                                )

                                # Add as followers only (not to current message recipients)
                                record._add_to_recipients_as_followers(message_dict)

                except Exception as e:
                    _logger.error(f"Error in _message_route_process: {str(e)}")

        return super()._message_route_process(message, message_dict, routes)
