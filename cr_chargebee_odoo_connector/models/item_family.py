# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
import chargebee
from datetime import datetime

class ChargebeeItemFamily(models.Model):
    _name = 'chargebee.item.family'
    _description = 'Chargebee Item Family'

    name = fields.Char(string="Name")
    chargebee_id = fields.Char(string="Chargebee Family ID", help="ID of the item family in Chargebee")
    item_ids = fields.One2many(
        comodel_name='product.template',
        inverse_name='item_family_id',
        string="Items"
    )

    def sync_item_families(self):
        """Fetch item families from Chargebee and store in Odoo."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise ValueError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        # Fetch item families from Chargebee
        families = chargebee.ItemFamily.list()
        # Initialize log variables
        start_time = datetime.now()
        record_count = 0
        status = 'success'
        error_message = ''

        try:
            for family_data in families:
                chargebee_family = family_data.item_family
                vals = {
                    'name': chargebee_family.name,
                    'chargebee_id': chargebee_family.id,
                }

                # Update existing or create new
                existing_family = self.search([('chargebee_id', '=', chargebee_family.id)], limit=1)
                if existing_family:
                    existing_family.write(vals)
                else:
                    self.create(vals)
                record_count += 1

            # Log success
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Chargebee Item Family',
                record_count=record_count,
                status=status,
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                context='itemsfamily',  # Specify context for this page
            )

        except Exception as e:
            # Log failure in case of an error
            status = 'failure'
            error_message = str(e)

            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Chargebee Item Family',
                record_count=record_count,
                status=status,
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                error_message=error_message,
                cr_configuration_id = chargebee_config.id,  # Pass the Chargebee configuration ID here
                context='itemsfamily',  # Specify context for this page
            )
            raise e
