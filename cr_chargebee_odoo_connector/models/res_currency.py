# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, api, _
import chargebee
from odoo.exceptions import UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def sync_chargebee_currencies(self):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        """
        Sync currencies from Chargebee to Odoo's res.currency model.
        """
        try:
            # Initialize Chargebee API
            chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
            if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
                raise UserError(_("Chargebee configuration is incomplete. Please configure the API key and site name."))

            # Configure Chargebee
            chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

            # Fetch currencies from Chargebee
            currencies_response = chargebee.Currency.list()
            start_time = datetime.now()
            total_records = 0
            for currency_data in currencies_response:
                # Access the 'currency' attribute of each result
                cb_currency = currency_data.currency
                cb_currency_code = cb_currency.currency_code.strip()

                # Check if the currency already exists in Odoo
                existing_currency = self.env['res.currency'].search(
                    [('name', '=', cb_currency_code), ('active', 'in', [True, False])], limit=1)
                if existing_currency:
                    _logger.info(f"Currency {cb_currency_code} already exists. Skipping creation.")
                    continue

                    # Create the currency in Odoo
                self.create({
                    'name': cb_currency_code,
                    'symbol': cb_currency_code,  # Adjust symbol mapping if needed
                    'rounding': 0.01,  # Default rounding
                    'active': True,
                })
                total_records += 1
                _logger.info(f"Created new currency: {cb_currency_code}")

                # Log the successful data processing
                self.env['cr.data.processing.log'].sudo()._log_data_processing(
                    table_name='Currency',
                    record_count=total_records,
                    status='success',
                    timespan=str(datetime.now() - start_time),  # Replace with actual timestamp
                    initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                    context='currencies',  # Specify context for this page
                )

                return True

        except Exception as e:
            _logger.error(f"Unexpected error while syncing currencies from Chargebee: {e}")
            # Log the failure of data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Currency',
                record_count=total_records,
                status='failure',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                error_message=str(e),
                context = 'currencies',  # Specify context for this page
            )
            return False
