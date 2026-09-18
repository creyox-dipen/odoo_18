# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class GelatoTemplateWizard(models.TransientModel):
    _name = 'gelato.template.wizard'
    _description = 'Gelato Template Wizard'

    template_id = fields.Char(string='Template ID', required=True)
    template_name = fields.Char(string='Template Name')
    description = fields.Html(string='Description')
    preview_url = fields.Char(string='Preview URL')
    product_type = fields.Char(string='Product Type')
    vendor = fields.Char(string='Vendor')
    variants = fields.Text(string='Variants')


    def fetch_template_details(self, template_id):
        api_key = self.env.user.company_id.api_key_for_gelato
        url = f'https://ecommerce.gelatoapis.com/v1/templates/{template_id}'

        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            template_data = response.json()

            self.template_name = template_data.get('templateName')
            self.description = template_data.get('description')
            self.preview_url = template_data.get('previewUrl')
            self.product_type = template_data.get('productType')
            self.vendor = template_data.get('vendor')
            self.variants = json.dumps(template_data.get('variants', []), indent=4)
        else:
            raise ValueError(f"Failed to fetch template data: {response.text}")
