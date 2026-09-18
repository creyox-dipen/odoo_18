# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class GelatoProductPriceWizard(models.TransientModel):
    _name = 'gelato.product.price.wizard'
    _description = 'Gelato Product Price Wizard'

    product_uid = fields.Char(string='Product UID', required=True)
    price_line_ids = fields.One2many(comodel_name='gelato.product.price.line', inverse_name='wizard_id', string='Prices')

    def fetch_product_prices(self, product_uid):
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
                lines.append((0, 0, {
                    'country': p.get('country'),
                    'quantity': p.get('quantity'),
                    'price': p.get('price'),
                    'currency': p.get('currency'),
                    'page_count': p.get('pageCount'),
                }))
            self.price_line_ids = lines