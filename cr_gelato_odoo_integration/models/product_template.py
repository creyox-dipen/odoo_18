# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import Command, _, api, fields, models
import requests
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    cr_template_ref = fields.Char(string="Template Reference from Gelato")
    cr_product_uid = fields.Char(
        string="Product UID of Gelato",
        compute='_compute_gelato_product_uid',
        inverse='_inverse_gelato_product_uid',
        readonly=True,
    )
    cr_image_ids = fields.One2many(
        string="Print Images",
        comodel_name='product.document',
        inverse_name='res_id',
        domain=[('is_gelato', '=', True)],
        readonly=True,
    )
    cr_missing_images = fields.Boolean(string="Missing Print Images")

    @api.depends('product_variant_ids.cr_product_uid')
    def _compute_gelato_product_uid(self):
        self._compute_template_field_from_variant_field('cr_product_uid')

    def _inverse_gelato_product_uid(self):
        self._set_product_variant_field('cr_product_uid')

    def action_sync_gelato_template_info(self):
        try:
            endpoint = f'templates/{self.cr_template_ref}'
            key = self.env.company.sudo().api_key_for_gelato
            template_data = self.gelato_api_request(endpoint, 'ecommerce', key, 'v1', 'GET')
        except UserError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'title': _("Gelato sync failed."),
                    'message': str(e),
                    'sticky': True,
                }
            }

        self._create_attributes_for_product(template_data)
        self._create_print_images_for_product(template_data)

        product = self.env['product.product'].search([('product_tmpl_id', '=', self.id)])
        for data in product:
            if data.cr_product_uid:
                data.list_price = self.apply_price(data.cr_product_uid)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _("Sync with Gelato completed successfully"),
                'message': _("Missing variants and associated images have been added successfully."),
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload'
                }
            }
        }

    def gelato_api_request(self, endpoint, subdomain, api_key, version, payload=None, method='GET'):
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        try:
            url = f'https://{subdomain}.gelatoapis.com/{version}/{endpoint}'
            headers = {
                'X-API-KEY': api_key or None
            }
            if method == 'GET':
                response = requests.get(url=url, params=payload, headers=headers, timeout=10)
            else:
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

    def _create_attributes_for_product(self, template_data):
        if template_data['variants']:
            no_of_variants = len(template_data['variants'])
            if no_of_variants == 1:
                self.cr_product_uid = template_data['variants'][0]['productUid']
            if no_of_variants > 1:
                for variants in template_data['variants']:
                    exhisting_product_attribute_values = self.check_attribute_values(variants)
                    for variant in self.product_variant_ids:
                        current_product_temp_attr_values = variant.product_template_attribute_value_ids.product_attribute_value_id
                        if current_product_temp_attr_values == exhisting_product_attribute_values:
                            variant.cr_product_uid = variants['productUid']
                            break

                variants_having_no_gelato_product_id = self.env['product.product'].search([
                    ('product_tmpl_id', '=', self.id),
                    ('cr_product_uid', '=', False)
                ])
                variants_having_no_gelato_product_id.unlink()

    def check_attribute_values(self, variants):
        exhisting_product_attribute_values = self.env['product.attribute.value']
        for attribute_info in variants['variantOptions']:
            attribute = self.env['product.attribute'].search(
                [
                    ('name', '=', attribute_info['name']),
                    ('create_variant', '=', 'always')
                ],
                limit=1,
            )

            if not attribute:
                attribute = self.env['product.attribute'].create({
                    'name': attribute_info['name']
                })

            attribute_value = self.env['product.attribute.value'].search([
                ('name', '=', attribute_info['value']),
                ('attribute_id', '=', attribute.id),
            ], limit=1)

            if not attribute_value:
                attribute_value = self.env['product.attribute.value'].create({
                    'name': attribute_info['value'],
                    'attribute_id': attribute.id
                })

            exhisting_product_attribute_values += attribute_value

            product_temp_attr_line = self.env['product.template.attribute.line'].search(
                [
                    ('product_tmpl_id', '=', self.id),
                    ('attribute_id', '=', attribute.id)
                ],
                limit=1,
            )

            if not product_temp_attr_line:
                self.env['product.template.attribute.line'].create({
                    'product_tmpl_id': self.id,
                    'attribute_id': attribute.id,
                    'value_ids': [Command.link(attribute_value.id)]
                })
            else:
                product_temp_attr_line.value_ids = [Command.link(attribute_value.id)]

        return exhisting_product_attribute_values

    def _create_print_images_for_product(self, template_data):
        image_info = template_data['variants'][0]['imagePlaceholders']
        for image_data in image_info:
            if image_data['printArea'].lower() in ('1', 'front'):
                image_data['printArea'] = 'default'

            is_image_found = bool(self.env['product.document'].search_count([
                ('name', 'ilike', image_data['printArea']),
                ('res_id', '=', self.id),
                ('res_model', '=', 'product.template'),
                ('is_gelato', '=', True),
            ]))

            if not is_image_found:
                self.cr_image_ids = [Command.create({
                    'name': image_data['printArea'].lower(),
                    'res_id': self.id,
                    'res_model': 'product.template',
                    'is_gelato': True,
                })]

    def msg_notification_from_gelato(self, msg):
        self.message_post(
            body=_("Notificaion from Gelato : %s" % msg),
        )
        if msg == 'store_product_template_updated':
            self.action_sync_gelato_template_info()
            self.store_product_template_updated()

    def is_temp_available(self, key):
        secret_key = self.env.user.company_id.webhook_secret_for_gelato

        if secret_key == key:
            return True
        else:
            return False

    def open_gelato_template_wizard(self):
        template_id = self.cr_template_ref
        wizard = self.env['gelato.template.wizard'].create({
            'template_id': template_id,  # assuming you have 'product_uid' in your template
        })
        wizard.fetch_template_details(template_id)

        return {
            'name': 'Gelato Template Wizard',
            'type': 'ir.actions.act_window',
            'res_model': 'gelato.template.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def set_img(self):
        api_key = self.env.user.company_id.api_key_for_gelato

        url = f'https://ecommerce.gelatoapis.com/v1/templates/{self.cr_template_ref}'

        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            template_data = response.json()
            image_url = template_data.get('previewUrl')

            if image_url:
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    encoded_image = base64.b64encode(image_response.content)

                    for data in self.cr_image_ids:
                        if data.is_gelato:
                            data.datas = encoded_image
                            self.image_1920 = encoded_image
                else:
                    _logger.info(f"Failed to download image from URL: {image_url}")
            else:
                _logger.info("No 'previewUrl' found in response.")
        else:
            _logger.error(f"Failed to get template data from Gelato API.")

    def apply_price(self, product_uid):
        api_key = self.env.user.company_id.api_key_for_gelato
        url = f'https://product.gelatoapis.com/v3/products/{product_uid}/prices'
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            prices = response.json()
            lines = []
            for p in prices:
                if p.get('quantity') == 1:
                    return p.get('price')

    def create_store_product(self, data_info):
        image_url = data_info.get('previewUrl')

        if image_url:
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                encoded_image = base64.b64encode(image_response.content)

                for data in self.cr_image_ids:
                    if data.is_gelato:
                        data.datas = encoded_image
                        self.image_1920 = encoded_image
            else:
                _logger.warning(f"Failed to download image from URL: {image_url}")
        else:
            _logger.info("No 'previewUrl' found in response.")

        api_key = self.env.user.company_id.api_key_for_gelato
        storeId = data_info.get('storeId')
        productId = data_info.get('storeProductId')
        url = f'https://ecommerce.gelatoapis.com/v1/stores/{storeId}/products/{productId}'
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            template_data = response.json()
            self._create_attributes_for_store_product(template_data)

    def create(self, vals):
        ref = super().create(vals)

        if not isinstance(vals, list):
            vals = [vals]

        for record, val in zip(ref, vals):
            record._customize_price(val)

        return ref

    def write(self, vals):
        ref = super().write(vals)

        if self.env.context.get("skip_update_fix_price", False):
            return ref

        for record in self:
            record._customize_price(vals)

        return ref

    def _customize_price(self, vals):
        if 'list_price' in vals:
            for variant in self.product_variant_ids:
                variant.cr_fix_price = vals['list_price']





