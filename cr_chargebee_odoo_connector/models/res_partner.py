# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
import logging
import chargebee
from datetime import datetime

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    chargebee_customer_id = fields.Char(string="Chargebee Customer ID", help="Customer ID in Chargebee")

    def create(self, vals):
        print(vals)
        return super(ResPartner, self).create(vals)

    def export_to_chargebee(self):
        """Export customers to Chargebee."""
        # Retrieve Chargebee configuration
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise ValueError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        successful_exports = []
        failed_exports = []
        total_records = 0
        start_time = datetime.now()

        for partner in self:
            if not partner.email:
                failed_exports.append(
                    _("Partner {} does not have an email address.").format(partner.name)
                )
                continue

            try:
                # Create or update customer in Chargebee
                chargebee.Customer.create({
                    "id": f"odoo_{partner.id}",  # Unique ID
                    "first_name": partner.name,
                    "email": partner.email,
                    "company": partner.company_name or partner.name,
                    "phone": partner.phone,
                })
                self.env.cr.commit()
                successful_exports.append(partner.name)
                total_records += 1
            except chargebee.APIError as e:
                error_message = e.json_obj.get("message", _("Unknown error"))
                failed_exports.append(
                    _("Failed to export {}: {}").format(partner.name, error_message)
                )
                # Log the export process
        try:
                self.env['cr.data.processing.log'].sudo()._log_data_processing(
                    table_name='Customers',
                    record_count=total_records,
                    status='success' if total_records > 0 else 'failure',
                    timespan=str(datetime.now() - start_time),
                    initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    cr_configuration_id=chargebee_config.id,
                    context='customers',
                    error_message="\n".join(failed_exports) if failed_exports else None,
                )
        except Exception as log_error:
                _logger.error(f"Failed to log Chargebee export: {log_error}")

        # Prepare notification messages
        title = _("Chargebee Export Results")
        success_message = (
            _("Successfully exported: {}").format(", ".join(successful_exports))
            if successful_exports
            else _("No successful exports.")
        )
        failure_message = (
            _("Failed to export: {}").format(", ".join(failed_exports))
            if failed_exports
            else ""
        )
        message = f"{success_message}\n{failure_message}".strip()

        # Display notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "sticky": False,
            },
        }

    def sync_chargebee_customers(self):
        """Synchronize customers from Chargebee to Odoo."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise ValueError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        # Initialize counters and error messages
        total_synced = 0
        errors = []
        new_customers = []  # Track newly created customers
        start_time = datetime.now()
        # Fetch customers from Chargebee
        customers = chargebee.Customer.list()  # Adjust limit as needed
        for customer_data in customers:
            chargebee_customer = customer_data.customer
            try:
                partner_vals = {
                    'name': f"{chargebee_customer.first_name} {getattr(chargebee_customer, 'last_name', '')}".strip(),
                    'email': chargebee_customer.email,
                    'phone': getattr(chargebee_customer, 'phone', None),
                    'company_name': getattr(chargebee_customer, 'company', None),
                    'id': chargebee_customer.id,
                }

                # Update existing or create new
                existing_partner = self.env['res.partner'].search([('email', '=', chargebee_customer.email)], limit=1)
                if existing_partner:
                    existing_partner.write(partner_vals)
                else:
                    new_partner = self.env['res.partner'].create(partner_vals)
                    new_customers.append(new_partner.name)  # Add the newly created partner's name
                total_synced += 1
            except Exception as e:
                _logger.error(f"Error syncing Chargebee customer {chargebee_customer.id}: {str(e)}")
                errors.append(f"{chargebee_customer.email}: {str(e)}")

                # Log the sync process
        try:
                    self.env['cr.data.processing.log'].sudo()._log_data_processing(
                        table_name='Customers',
                        record_count=total_synced,
                        status='success' if total_synced > 0 else 'failure',
                        timespan=str(datetime.now() - start_time),
                        initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        cr_configuration_id=chargebee_config.id,
                        context='customers',
                        error_message="\n".join(errors) if errors else None,
                    )
        except Exception as log_error:
                    _logger.error(f"Failed to log Chargebee customer sync: {log_error}")

        # Prepare notification message
        message = _(
            f"Synchronization complete.\n"
            f"Total synced: {total_synced}.\n"
            f"Errors: {len(errors)}."
        )
        if errors:
            message += _("\nDetails:\n") + "\n".join(errors)

        # Include names of new customers
        if new_customers:
            message += _("\nNewly created customers:\n") + "\n".join(new_customers)

        # Display notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Chargebee Customer Sync"),
                "message": message,
                "sticky": False,  # Change to True if you want the notification to persist
            },
        }