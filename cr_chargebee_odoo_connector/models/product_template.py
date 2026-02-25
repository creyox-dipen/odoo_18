# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
import chargebee
from odoo.exceptions import UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _description = 'Product Template'

    chargebee_id = fields.Char(string="Chargebee Item ID", help="ID of the item in Chargebee")
    chargebee_created = fields.Boolean(string="Created in Chargebee", default=False)
    item_family_id = fields.Many2one('chargebee.item.family', string="Item Family")

    def sync_items_from_chargebee(self):
        """Sync items from Chargebee and create corresponding product records in Odoo."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise ValueError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)
        start_time = datetime.now()
        total_records = 0
        try:
            # Fetch items from Chargebee
            items = chargebee.Item.list()  # Adjust limit as needed
            for item_data in items:
                item = item_data.item
                # Fetch item prices for the item
                item_prices = chargebee.ItemPrice.list({"item_id[is]": item.id, "limit": 1})
                price = None
                currency = "USD"
                if item_prices:
                    item_price_data = item_prices[0].item_price
                    price = item_price_data.price / 100 if item_price_data.price else 0.0
                    currency = item_price_data.currency_code or "USD"

                # Find the associated family in Odoo
                family = self.env['chargebee.item.family'].search(
                    [('chargebee_id', '=', item.item_family_id)], limit=1
                )
                # Get or create a valid product category
                category = self.env['product.category'].search(
                    [('id', '=', family.id)], limit=1
                )
                if not category:
                    category = self.env['product.category'].create({
                        'name': family.name if family else 'Default Category',
                    })

                # Check if the product already exists in Odoo's base model `product.template`
                existing_product = self.env['product.template'].search(
                    [('default_code', '=', item.id)], limit=1
                )

                if existing_product:
                    # Update the existing product in base model
                    existing_product.write({
                        'name': item.name,
                        'list_price': price if price else 0.0,
                        'default_code': item.id,
                        'description_sale': item.description or "",
                        'description': item.description or "",
                        'categ_id': category.id,
                        'currency_id': self.env['res.currency'].search([('name', '=', currency)], limit=1).id,
                        'chargebee_id': item.id,
                        'chargebee_created': True,
                        'item_family_id': family.id if family else False,
                    })
                else:
                    # Create a new product record in base model
                    self.env['product.template'].create({
                        'name': item.name,
                        'list_price': price if price else 0.0,
                        'default_code': item.id,
                        'description_sale': item.description or "",
                        'description': item.description or "",
                        'categ_id': category.id,
                        'currency_id': self.env['res.currency'].search([('name', '=', currency)], limit=1).id,
                        'type': 'consu',  # Set product type, can be 'consu' or 'service' based on your requirement
                        'chargebee_id': item.id,
                        'chargebee_created': True,
                        'item_family_id': family.id if family else False,
                    })
                total_records += 1
                # Log successful data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                    table_name='Product',
                    record_count=total_records,
                    status='success',
                    timespan=str(datetime.now() - start_time),
                    initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                    context='items',  # Specify context for this page
            )

        except Exception as e:
            _logger.error(f"Unexpected error while syncing items from Chargebee: {e}")
            # Log the failure of data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Product',
                record_count=total_records,
                status='failure',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                error_message=str(e),
                context = 'items',  # Specify context for this page
            )
            raise ValueError(_("Error syncing items from Chargebee: %s") % str(e))


    def create_item_in_chargebee(self):
        """Create an item in Chargebee under the selected family."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise ValueError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)
        start_time = datetime.now()
        total_records = 0
        # Check and create item family in Chargebee if not set
        if not self.item_family_id:
            family_name = f"From Odoo {self.id}"  # Use a unique name
            try:
                existing_family = None
                try:
                    existing_family = chargebee.ItemFamily.retrieve(self.id)
                except chargebee.InvalidRequestError as e:
                   print("not found item family")


                if existing_family:
                    # Link existing item family
                    self.item_family_id = self.env['chargebee.item.family'].create({
                        "name": family_name,
                        "chargebee_id": existing_family.item_family.id,
                    })
                else:
                    # Create a new item family
                    response = chargebee.ItemFamily.create({
                        "id": self.id,
                        "name": family_name,
                        "description": "Auto-created item family from Odoo",
                    })
                    self.item_family_id = self.env['chargebee.item.family'].create({
                        "name": family_name,
                        "chargebee_id": response.item_family.id,
                    })
            except Exception as e:
                raise ValueError(_("Error creating item family in Chargebee: %s") % str(e))

        if not self.item_family_id.chargebee_id:
            raise ValueError(_("The selected item family does not have a Chargebee ID."))

        # Create the item in Chargebee
        item_id = self.default_code.lower().replace(" ", "_")
        try:
            # Check if the item already exists
            existing_item = None
            try:
                existing_item = chargebee.Item.retrieve(item_id)
            except chargebee.InvalidRequestError as e:
               print("no item found with id")

            if existing_item:
                # Item already exists, link it to Odoo
                self.chargebee_id = existing_item.item.id
                self.chargebee_created = True
            else:
                # Item does not exist, create it
                item_data = {
                    "id": item_id,
                    "name": self.name,
                    "description": self.description_sale or "",
                    "type": "plan",
                    "item_family_id": self.item_family_id.chargebee_id,
                }
                response = chargebee.Item.create(item_data)
                self.chargebee_id = response.item.id
                self.chargebee_created = True

            # # Create a price point for the item
            # price_data = {
            #     "id": f"{item_id}_price",
            #     "item_price": {
            #         "item_id": self.chargebee_id,
            #         "name": f"Price for {self.name or self.default_code}" if (self.name or self.default_code) else "Default Price Name",
            #         "pricing_model": "flat_fee",
            #         "price": int(self.list_price * 100),  # Convert price to cents
            #         "currency_code": self.currency_id.name,
            #     }
            # }
            # chargebee.ItemPrice.create(price_data)
            total_records += 1
            # Log successful data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Chargebee Item',
                record_count=total_records,
                status='success',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                context='items',  # Specify context for this page
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Item in Chargebee',
                    'message': f"Successfully Created",
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            _logger.error(f"Unexpected error while creating item in Chargebee: {e}")
            # Log failure data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Chargebee Item',
                record_count=total_records,
                status='failure',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,  # Pass the Chargebee configuration ID here
                error_message=str(e),
                context='items',  # Specify context for this page
            )
            raise ValueError(_("Error creating item in Chargebee: %s") % str(e))

