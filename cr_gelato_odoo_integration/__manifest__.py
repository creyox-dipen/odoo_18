# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'Odoo To Gelato Integration | Gelato Connector for Odoo ',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "version": "18.0.0.0",
    'summary':
        """
        A seamless integration between Odoo and the Gelato Print-on-Demand platform, enabling automated product sync, 
        order fulfillment, and tracking updates. Designed to streamline e-commerce operations by connecting Odoo’s ERP 
        capabilities with Gelato’s global print network.

        Gelato Connector for Odoo
        Gelato Print-on-Demand Sync
        Gelato Order Sync for Odoo
        Odoo Gelato integration
        Gelato print-on-demand Odoo connector
        Odoo sync with Gelato
        Print-on-demand platform for Odoo
        Automate orders with Gelato in Odoo
        Gelato API Odoo module
        Odoo eCommerce fulfillment automation
        Gelato Odoo connector
        Odoo Gelato module
        Best Odoo app for Gelato integration

        How to connect Gelato with Odoo?
        Is there a Gelato integration for Odoo?
        Can I sync Gelato print-on-demand orders to Odoo?
        How to automate Gelato fulfillment in Odoo?
        How to integrate Gelato API with Odoo?
        Can Odoo manage print-on-demand with Gelato?
        How to sync shipping and tracking from Gelato to Odoo?
        Gelato fulfillment automation for Odoo
        """,
    "sequence": 10,
    "description":
        """
        A seamless integration between Odoo and the Gelato Print-on-Demand platform, enabling automated product sync, 
        order fulfillment, and tracking updates. Designed to streamline e-commerce operations by connecting Odoo’s ERP 
        capabilities with Gelato’s global print network.

        Gelato Connector for Odoo
        Gelato Print-on-Demand Sync
        Gelato Order Sync for Odoo
        Odoo Gelato integration
        Gelato print-on-demand Odoo connector
        Odoo sync with Gelato
        Print-on-demand platform for Odoo
        Automate orders with Gelato in Odoo
        Gelato API Odoo module
        Odoo eCommerce fulfillment automation
        Gelato Odoo connector
        Odoo Gelato module
        Best Odoo app for Gelato integration

        How to connect Gelato with Odoo?
        Is there a Gelato integration for Odoo?
        Can I sync Gelato print-on-demand orders to Odoo?
        How to automate Gelato fulfillment in Odoo?
        How to integrate Gelato API with Odoo?
        Can Odoo manage print-on-demand with Gelato?
        How to sync shipping and tracking from Gelato to Odoo?
        Gelato fulfillment automation for Odoo
        """,
    'category': 'Extra Tools',
    "price": 250,
    "currency": "USD",
    "license": "OPL-1",
    'depends': ['sale_management', 'delivery'],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_carrier.xml',
        'views/sale_order.xml',
        'views/delivery_carrier.xml',
        'views/product_document.xml',
        'views/product_product.xml',
        'views/product_template.xml',
        'views/res_company_settings.xml',
        'views/product_template_attribute_value.xml',
        'wizard/gelato_order_info.xml',
        'wizard/gelato_product_info.xml',
        'wizard/gelato_product_template_info.xml',
        'wizard/gelato_product_price.xml',

    ],
    "installable": True,
    "auto_install": True,
    "application": True,
    "images": ["static/description/banner.png"],
}
