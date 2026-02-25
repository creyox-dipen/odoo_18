# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import chargebee
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class AccountTax(models.Model):
    _inherit = "account.tax"

    chargebee_id = fields.Char(string="Chargebee Tax ID", help="ID of the tax in Chargebee")

    def sync_taxes_from_chargebee(self):
        """Sync taxes from Chargebee based on invoice line items and create or update taxes in Odoo."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise UserError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)
        start_time = datetime.now()
        total_records = 0
        try:
            # Fetch invoices from Chargebee
            invoices = chargebee.Invoice.list()
            for inv_data in invoices:
                invoice = inv_data.invoice

                # Fetch the tax details from invoice line items (if available)
                for line in getattr(invoice, 'line_items', []):
                    if line.tax_amount == 0 or line.tax_exempt_reason:
                        _logger.info(
                            f"Skipping tax processing for line item {line.id} due to tax exemption or zero tax.")
                        continue  # Skip line items with zero tax or tax-exempt

                    # Process tax details
                    tax_id = line.tax_amount  # Use the tax amount as a placeholder, or adjust as needed
                    tax_name = f"Tax for {line.description}"

                    # Check if the tax already exists in Odoo
                    existing_tax = self.env['account.tax'].search([('chargebee_id', '=', tax_id)], limit=1)
                    if existing_tax:
                        # Update the tax if it exists
                        existing_tax.write({
                            'name': tax_name,
                            'amount': line.tax_amount / 100,  # Assuming tax is a percentage
                            'type_tax_use': 'sale',  # Assuming taxes are for sales
                        })
                        _logger.info(f"Updated tax {existing_tax.name} in Odoo.")
                    else:
                        # Create the tax if it doesn't exist
                        self.env['account.tax'].create({
                            'name': tax_name,
                            'amount': line.tax_amount / 100,  # Assuming tax is a percentage
                            'type_tax_use': 'sale',  # Assuming taxes are for sales
                            'chargebee_id': tax_id,
                        })
                        _logger.info(f"Created new tax {tax_name} in Odoo.")

                    total_records += 1

                    # Log successful data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                        table_name='Account Tax',
                        record_count=total_records,
                        status='success',
                        timespan=str(datetime.now() - start_time),
                        initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                        context='taxes',  # Specify context for this page
            )

        except chargebee.APIError as e:
            _logger.error(f"Error syncing taxes from Chargebee: {e.json_obj}")
            # Log failure data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Account Tax',
                record_count=total_records,
                status='failure',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                error_message=str(e),
                context = 'taxes',  # Specify context for this page
            )
            raise UserError(_("Failed to sync taxes. Error: %s") % e.json_obj.get('message', str(e)))
