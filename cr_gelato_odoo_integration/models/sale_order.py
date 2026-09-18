# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, _, fields
from odoo.exceptions import UserError, ValidationError
import requests
import pprint
from odoo import SUPERUSER_ID, _
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gelato_order_id = fields.Char('Gelato Order Id', readonly=True)
    active = fields.Boolean(string='Active', default='True')

    def _action_cancel(self):
        ref = super()._action_cancel()
        try:
            endpoint = f'orders/{self.gelato_order_id}:cancel'
            api_key = self.company_id.sudo().api_key_for_gelato
            data = self.gelato_api_request(api_key, 'order', 'v4', endpoint)
        except UserError as e:
            raise UserError(_(
                "The order with reference %(order_reference)s was not cancel in Gelato.\n"
                "Reason: %(error_message)s",
                order_reference=self.display_name,
                error_message=str(e),
            ))

        return ref

    def _is_mixing_of_gelato_and_non_gelato_products(self):
        gelato_product = 0
        non_gelato_product = 0

        for data in self:
            for product in data.order_line.product_id:
                if product.cr_product_uid:
                    gelato_product += 1
                elif product.default_code == 'Delivery_008':
                    gelato_product += 1
                elif product.default_code == 'Delivery_009':
                    gelato_product += 1
                else:
                    non_gelato_product += 1

        if gelato_product > 0 and non_gelato_product > 0:
            raise ValidationError(_("You cannot mix Gelato products with non-Gelato products in the same order."))

    def action_confirm(self):
        res = super().action_confirm()
        for data in self:
            for record in data.order_line:
                if record.product_id.cr_product_uid:
                    data._generate_order_in_gelato()
                    break
                else:
                    break
        return res

    def _generate_order_in_gelato(self):
        special_delivery_codes = ['Delivery_008', 'Delivery_009']
        shipment_method = 'normal'

        for line in self.order_line:
            if line.product_id.default_code:
                if line.product_id.default_code in special_delivery_codes:
                    shipment_method = line.product_id.default_code

        payload = {
            'orderType': 'order',
            'orderReferenceId': self.id,
            'customerReferenceId': self.partner_id.id,
            'currency': self.currency_id.name,
            'items': self.items_for_order(),
            'shipmentMethodUid': shipment_method,
            'shippingAddress': self.partner_shipping_id.prepare_address_values(),
        }
        try:
            api_key = self.company_id.sudo().api_key_for_gelato
            data = self.gelato_api_request(api_key, 'order', 'v4', 'orders', payload=payload)
            if data:
                self.gelato_order_id = data['id']
        except UserError as e:
            raise UserError(_(
                "The order with reference %(order_reference)s was not sent to Gelato.\n"
                "Reason: %(error_message)s",
                order_reference=self.display_name,
                error_message=str(e),
            ))

        self.message_post(
            body=_("The order has been successfully passed on Gelato."),
            author_id=self.env.ref('base.partner_root').id,
        )

    def items_for_order(self):
        data = []
        for record in self.order_line:
            if record.product_id.cr_product_uid:
                product_item = {
                    'itemReferenceId': record.product_id.id,
                    'productUid': record.product_id.cr_product_uid,
                    'files': [
                        image._prepare_file_for_gelato()
                        for image in record.product_id.product_tmpl_id.cr_image_ids
                    ],
                    'quantity': int(record.product_uom_qty),
                }
                data.append(product_item)

        return data

    def msg_notification_from_gelato(self, status):
        self.message_post(
            body=_("Order status : %s" % status),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _("Notification From Gelato"),
                'message': 'success',
                'sticky': True,
            }
        }

    def gelato_api_request(self, api_key, subdomain, version, endpoint, payload=None):
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        try:
            url = f'https://{subdomain}.gelatoapis.com/{version}/{endpoint}'
            headers = {
                'X-API-KEY': api_key or None
            }
            response = requests.post(url=url, json=payload, headers=headers, timeout=10)
            response_content = response.json()

            response.raise_for_status()

            return response.json()

        except requests.exceptions.HTTPError as http_err:
            _logger.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            _logger.error(f"Request error occurred: {req_err}")
        except Exception as err:
            _logger.error(f"Unexpected error occurred: {err}")

        return None

    def action_open_gelato_order(self):
        api_key = self.company_id.sudo().api_key_for_gelato
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        try:

            url = f'https://order.gelatoapis.com/v4/orders/{self.gelato_order_id}'
            headers = {
                'X-API-KEY': api_key or None
            }
            response = requests.get(url=url, headers=headers, timeout=10)
            response_content = response.json()

            order_data = response.json()

            ctx = dict(
                default_order_id=order_data.get('id'),
                default_customer_reference_id=order_data.get('customerReferenceId'),
                default_fulfillment_status=order_data.get('fulfillmentStatus'),
                default_financial_status=order_data.get('financialStatus'),
                default_currency=order_data.get('currency'),
                default_channel=order_data.get('channel'),
                default_store_id=order_data.get('storeId'),
                # Handling datetime parsing
                default_created_at=self.parse_datetime_with_timezone(order_data.get('createdAt')),
                default_updated_at=self.parse_datetime_with_timezone(order_data.get('updatedAt')),
                default_ordered_at=self.parse_datetime_with_timezone(order_data.get('orderedAt')),
                # JSON-encoded fields (no change here)
                default_items_json=json.dumps(order_data.get('items', []), indent=4),
                default_shipment_json=json.dumps(order_data.get('shipment', {}), indent=4),
                default_billing_json=json.dumps(order_data.get('billingEntity', {}), indent=4),
                default_shipping_json=json.dumps(order_data.get('shippingAddress', {}), indent=4),
                default_return_json=json.dumps(order_data.get('returnAddress', {}), indent=4),
                default_receipts_json=json.dumps(order_data.get('receipts', []), indent=4),
            )
            return {
                'type': 'ir.actions.act_window',
                'name': 'Gelato Order',
                'res_model': 'gelato.order.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': ctx,
            }
        except requests.exceptions.HTTPError as http_err:
            _logger.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as req_err:
            _logger.error(f"Request error occurred: {req_err}")
        except Exception as err:
            _logger.error(f"Unexpected error occurred: {err}")

        return None

    def parse_datetime_with_timezone(self, date_string):
        try:
            return fields.Datetime.from_string(date_string)
        except ValueError:
            return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S%z")