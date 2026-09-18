# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class GelatoProductTemplateWizard(models.TransientModel):
    _name = 'gelato.product.template.wizard'
    _description = 'Gelato Product Template Wizard'

    product_uid = fields.Char(string='Product UID')
    coating_type = fields.Char(string='Coating Type')
    color_type = fields.Char(string='Color Type')
    folding_type = fields.Char(string='Folding Type')
    orientation = fields.Char(string='Orientation')
    paper_format = fields.Char(string='Paper Format')
    paper_type = fields.Char(string='Paper Type')
    product_status = fields.Char(string='Product Status')
    protection_type = fields.Char(string='Protection Type')
    spot_finishing_type = fields.Char(string='Spot Finishing Type')
    variable = fields.Char(string='Variable')
    weight_value = fields.Float(string='Weight Value')
    weight_unit = fields.Char(string='Weight Unit')
    supported_countries = fields.Text(string='Supported Countries')
    not_supported_countries = fields.Text(string='Not Supported Countries')
    is_stockable = fields.Boolean(string='Is Stockable')
    is_printable = fields.Boolean(string='Is Printable')
    valid_page_counts = fields.Text(string='Valid Page Counts')

    def fetch_product_details(self):
        api_key = self.env.user.company_id.api_key_for_gelato
        url = f'https://product.gelatoapis.com/v3/products/{self.product_uid}'
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            product_data = response.json()

            # Populate fields from the API response
            self.coating_type = product_data.get('attributes', {}).get('CoatingType')
            self.color_type = product_data.get('attributes', {}).get('ColorType')
            self.folding_type = product_data.get('attributes', {}).get('FoldingType')
            self.orientation = product_data.get('attributes', {}).get('Orientation')
            self.paper_format = product_data.get('attributes', {}).get('PaperFormat')
            self.paper_type = product_data.get('attributes', {}).get('PaperType')
            self.product_status = product_data.get('attributes', {}).get('ProductStatus')
            self.protection_type = product_data.get('attributes', {}).get('ProtectionType')
            self.spot_finishing_type = product_data.get('attributes', {}).get('SpotFinishingType')
            self.variable = product_data.get('attributes', {}).get('Variable')
            self.weight_value = product_data.get('weight', {}).get('value')
            self.weight_unit = product_data.get('weight', {}).get('measureUnit')
            self.supported_countries = ', '.join(product_data.get('supportedCountries', []))
            self.not_supported_countries = ', '.join(product_data.get('notSupportedCountries', []))
            self.is_stockable = product_data.get('isStockable', False)
            self.is_printable = product_data.get('isPrintable', False)
            self.valid_page_counts = ', '.join(map(str, product_data.get('validPageCounts', [])))
