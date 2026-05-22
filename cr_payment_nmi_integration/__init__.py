# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from . import controllers
from . import models
import logging
_logger = logging.getLogger(__name__)
from odoo.addons.payment import setup_provider, reset_payment_provider

def post_init_hook(env):
    setup_provider(env, 'nmi')
    # Link ACH method to the provider
    provider = env['payment.provider'].sudo().search([('code', '=', 'nmi')], limit=1)
    ach_method = env['payment.method'].sudo().search([('code', '=', 'ach_direct_debit')], limit=1)
    if provider and ach_method and ach_method not in provider.payment_method_ids:
        provider.write({'payment_method_ids': [(4, ach_method.id)]})

    Product = env['product.template']
    
    products_to_create = [
        ('CREDIT_CARD_FEE', 'Credit Card Fee'),
        ('DEBIT_CARD_FEE', 'Debit Card Fee'),
    ]

    for code, name in products_to_create:
        existing = Product.search([('default_code', '=', code)], limit=1)
        if not existing:
            vals = {
                'name': name,
                'type': 'service',
                'list_price': 0.0,
                'sale_ok': True,
                'purchase_ok': False,
                'default_code': code,
                'taxes_id': [(5, 0, 0)],
            }
            # Safely add website/sale fields only if they exist on the model
            if 'website_published' in Product._fields:
                vals['website_published'] = False
            if 'invoice_policy' in Product._fields:
                vals['invoice_policy'] = 'order'
            Product.create(vals)
            _logger.info("NMI: %s product created successfully.", name)
        else:
            _logger.info("NMI: %s product already exists, skipping.", name)

def uninstall_hook(env):
    reset_payment_provider(env, 'nmi')
