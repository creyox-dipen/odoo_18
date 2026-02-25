# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import chargebee
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class ChargebeeSubscription(models.Model):
    _name = 'chargebee.subscription'
    _description = 'Chargebee Subscription'

    name = fields.Char(string="Subscription Name", required=True)
    chargebee_id = fields.Char(string="Chargebee Subscription ID", help="ID of the subscription in Chargebee")
    customer_id = fields.Many2one('res.partner', string="Customer", help="Customer associated with this subscription")
    status = fields.Selection([
        ('active', 'Active'),
        ('non_renewing', 'Non-Renewing'),
        ('cancelled', 'Cancelled'),
        ('paused', 'Paused'),
        ('future', 'Future'),
        ('in_trial', 'In Trial'),
    ], string="Status")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    billing_cycle = fields.Integer(string="Billing Cycle", help="Number of billing cycles")
    plan_id = fields.Char(string="Plan ID", help="ID of the plan associated with the subscription")

    @staticmethod
    def convert_timestamp_to_datetime(timestamp):
        """Convert Unix timestamp to datetime."""
        if timestamp:
            try:
                return datetime.utcfromtimestamp(timestamp).date()
            except (ValueError, OSError):
                _logger.error(f"Invalid timestamp: {timestamp}")
                return None
        return None

    def action_sync_subscriptions(self):
        """Sync subscriptions from Chargebee."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise UserError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        # Fetch subscriptions from Chargebee
        try:
            subscriptions = chargebee.Subscription.list()
            for sub_data in subscriptions:
                subscription = sub_data.subscription
                customer_details = sub_data.customer
                # Safeguard against None values for first_name and last_name
                first_name = customer_details.first_name or ''
                last_name = customer_details.last_name or ''
                full_name = (first_name + ' ' + last_name).strip()
                phone = customer_details.phone or ''
                # Fetch or create customer
                customer = self.env['res.partner'].search([('name', '=', full_name)], limit=1)
                if not customer and full_name:
                    customer = self.env['res.partner'].create({'name': full_name, 'phone' : phone})

                # Prepare values
                vals = {
                    'name': subscription.id,
                    'chargebee_id': subscription.id,
                    'customer_id': customer.id if customer else None,
                    'status': subscription.status,
                    'start_date': self.convert_timestamp_to_datetime(getattr(subscription, 'start_date', None)),
                    'end_date': self.convert_timestamp_to_datetime(getattr(subscription, 'end_date', None)),
                    'billing_cycle': getattr(subscription, 'billing_cycle', None),
                    'plan_id': subscription.plan_id,
                }

                # Update or create subscription
                existing_subscription = self.search([('chargebee_id', '=', subscription.id)], limit=1)
                if existing_subscription:
                    existing_subscription.write(vals)
                else:
                    self.create(vals)

        except Exception as e:
            _logger.error(f"Error syncing subscriptions: {e}")
            raise UserError(_("An error occurred while syncing subscriptions. Please check the logs for details."))

    def action_upgrade_subscription(self):
        """Upgrade subscription plan."""
        for subscription in self:
            new_plan_id = self.env.context.get('new_plan_id')
            if not new_plan_id:
                raise UserError(_("New plan ID is required to upgrade."))

            try:
                chargebee.Subscription.update(subscription.chargebee_id, {
                    "plan_id": new_plan_id
                })
                subscription.plan_id = new_plan_id
            except Exception as e:
                _logger.error(f"Error upgrading subscription {subscription.chargebee_id}: {e}")
                raise UserError(_("An error occurred while upgrading the subscription. Please check the logs for details."))

    def action_downgrade_subscription(self):
        """Downgrade subscription plan."""
        for subscription in self:
            new_plan_id = self.env.context.get('new_plan_id')
            if not new_plan_id:
                raise UserError(_("New plan ID is required to downgrade."))

            try:
                chargebee.Subscription.update(subscription.chargebee_id, {
                    "plan_id": new_plan_id
                })
                subscription.plan_id = new_plan_id
            except Exception as e:
                _logger.error(f"Error downgrading subscription {subscription.chargebee_id}: {e}")
                raise UserError(_("An error occurred while downgrading the subscription. Please check the logs for details."))

    def action_cancel_subscription(self):
        """Cancel subscription."""
        for subscription in self:
            try:
                # Use Chargebee's API for Product Catalog 2.0
                chargebee.Subscription.cancel(subscription.chargebee_id, {
                    "end_of_term": True  # Ensure this matches Product Catalog 2.0 parameters
                })
                subscription.status = 'cancelled'
            except chargebee.APIError as e:
                # Handle Chargebee API-specific errors
                _logger.error(f"Error cancelling subscription {subscription.chargebee_id}: {e.json_obj}")
                raise UserError(_("Failed to cancel the subscription. Error: %s") % e.json_obj.get('message', str(e)))
            except Exception as e:
                # Handle general errors
                _logger.error(f"Error cancelling subscription {subscription.chargebee_id}: {e}")
                raise UserError(
                    _("An error occurred while cancelling the subscription. Please check the logs for details."))
