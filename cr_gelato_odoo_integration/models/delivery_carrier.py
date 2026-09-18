# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import _, api, fields, models
from odoo.exceptions import UserError
import requests
from odoo.exceptions import UserError
from odoo.addons.cr_gelato_odoo_integration import const
import logging

_logger = logging.getLogger(__name__)


class Carrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('gelato', "Gelato")],
        ondelete={'gelato': 'cascade'}
    )
    cr_gelato_shipping_service_type = fields.Selection(
        string="Shipping Service Type of Gelato",
        selection=[('normal', "Standard Delivery"), ('express', "Express Delivery")],
        required=True,
        default='normal',
    )

    def _is_available_for_order(self, order):
        ref = super()._is_available_for_order(order)
        is_order_is_gelato_order = any(order.order_line.product_id.mapped('cr_product_uid'))
        is_delivery_is_gelato_delivery = self.delivery_type == 'gelato'

        if is_order_is_gelato_order and not is_delivery_is_gelato_delivery or not is_order_is_gelato_order and is_delivery_is_gelato_delivery:
            return False

        return ref

    def gelato_rate_shipment(self, order):
        if error_message := self._verify_partner_address(order.partner_id):
            return {
                'success': False,
                'price': 0,
                'error_message': error_message,
            }

        payload = {
            'orderReferenceId': order.id,
            'customerReferenceId': order.partner_id.id,
            'currency': order.currency_id.name,
            'allowMultipleQuotes': 'true',
            'products': order.items_for_order(),
            'recipient': order.partner_shipping_id.prepare_address_values(),
        }
        try:
            cr_api_key = order.company_id.sudo().api_key_for_gelato
            data = self.gelato_api_request(cr_api_key, 'order', 'v4', 'orders:quote', payload=payload)
        except UserError as e:
            return {
                'success': False,
                'price': 0,
                'error_message': str(e),
            }

        cr_total_delivery_price = 0
        for quote in data['quotes']:
            cr_matching_shipment_method_prices = [
                shipment_method_data['price']
                for shipment_method_data in quote['shipmentMethods']
                if shipment_method_data['type'] == self.cr_gelato_shipping_service_type
            ]
            if not cr_matching_shipment_method_prices:
                return {
                    'success': False,
                    'price': 0,
                    'error_message': _("The selected shipping method is not applicable to this order."),
                }
            else:
                cr_total_delivery_price += min(cr_matching_shipment_method_prices)

        return {
            'success': True,
            'price': cr_total_delivery_price,
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

    @api.model
    def _verify_partner_address(self, partner):
        required_fields_for_address = ['city', 'country_id', 'street']
        if partner.country_id.code not in const.COUNTRIES_WITHOUT_ZIPCODE:
            required_fields_for_address.append('zip')
        address_missing_fields = [
            partner._fields[field_name]
            for field_name in required_fields_for_address if not partner[field_name]
        ]
        if address_missing_fields:
            address_translated_field_names = [data._description_string(self.env) for data in address_missing_fields]
            return _(
                "The following essential address fields have not been provided: %s",
                ", ".join(address_translated_field_names),
            )

    def rate_shipment(self, order):
        self.ensure_one()
        if hasattr(self, '%s_rate_shipment' % self.delivery_type):
            res = getattr(self, '%s_rate_shipment' % self.delivery_type)(order)

            company = self.company_id or order.company_id or self.env.company
            if self.delivery_type == 'gelato':
                cr_price = self.gelato_rate_shipment(order)
                res['price'] = cr_price["price"]
            else:
                res['price'] = self.product_id._get_tax_included_unit_price(
                    company,
                    company.currency_id,
                    order.date_order,
                    'sale',
                    fiscal_position=order.fiscal_position_id,
                    product_price_unit=res['price'],
                    product_currency=company.currency_id
                )
            res['price'] = self.with_context(order=order)._apply_margins(res['price'])
            res['carrier_price'] = res['price']
            amount_without_delivery = order._compute_amount_total_without_delivery()

            if (
                    res['success']
                    and self.free_over
                    and self.delivery_type != 'base_on_rule'
                    and self._compute_currency(order, amount_without_delivery, 'pricelist_to_company') >= self.amount
            ):
                res['warning_message'] = _('The shipping is free since the order amount exceeds %.2f.', self.amount)
                res['price'] = 0.0
            else:
                res['warning_message'] = False
            return res

        return super()
