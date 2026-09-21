# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'Odoo To Gelato Integration | Gelato Connector for Odoo ',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_gelato_odoo_integration&version=18.0",
    "version": "18.0.0.0",
    'summary':
        """
        A seamless integration between Odoo and the Gelato Print-on-Demand platform, enabling automated product sync, 
        order fulfillment, and tracking updates. Designed to streamline e-commerce operations by connecting Odoo’s ERP 
        capabilities with Gelato’s global print network.
        """,
    "sequence": 10,
    "description":
        """
            <h1>Gelato Odoo Integration: Ultimate Print-on-Demand Order Sync & Integration</h1>
            <p>The Gelato Odoo Connector enables seamless integration between Gelato print-on-demand platform and Odoo, automating order fulfillment, product sync, print file handling, shipping synchronization, and tracking updates for efficient print-on-demand operations.</p>

            <h2>Key Features</h2>
            <ul>
                <li>Automated synchronization of Gelato product templates and variants into Odoo</li>
                <li>Automatic transmission of confirmed Odoo sale orders to Gelato for fulfillment</li>
                <li>Seamless attachment and handling of print design files and mockups</li>
                <li>Automatic shipping and tracking synchronization with carriers</li>
                <li>Order cancellation sync between Odoo and Gelato</li>
                <li>Interactive pricing wizards to fetch live product and shipping rates from Gelato</li>
                <li>Manage multiple Gelato stores and companies in one system</li>
                <li>Secure API integration with quick API key setup</li>
                <li>Detailed error logging with transparent request and response tracking</li>
                <li>Instant data refresh for real-time order updates</li>
                <li>Advanced data mapping to sales teams, warehouses, and carriers</li>
                <li>High-performance processing for large-scale order volumes</li>
            </ul>

            <h2>Benefits</h2>
            <ul>
                <li>Eliminates manual order entry and reduces operational errors</li>
                <li>Improves order processing speed and fulfillment accuracy via global print hubs</li>
                <li>Centralizes print-on-demand catalog and order management in Odoo</li>
                <li>Ensures real-time synchronization of orders and shipment statuses</li>
                <li>Enhances scalability with zero inventory overhead</li>
            </ul>

            <h2>Why Choose This Gelato | Odoo Integration?</h2>
            <p>This connector is designed for businesses handling print-on-demand eCommerce operations through Gelato. It streamlines order workflows, ensures accurate synchronization, and provides powerful automation tools to improve efficiency, visibility, and overall performance within Odoo.</p>

            <h2>Related Keywords</h2>
            <ul>
                <li>Gelato Odoo Connector</li>
                <li>Ultimate Gelato Integration</li>
                <li>Odoo Print-on-Demand Order Sync</li>
                <li>Gelato E-commerce Automation</li>
                <li>Odoo Gelato Order Fulfillment</li>
                <li>Print-on-Demand Marketplace Sync</li>
                <li>Odoo implementation</li>
                <li>Odoo ERP implementation</li>
                <li>Odoo setup</li>
            </ul>
            
            <h2>Related Apps</h2>
            <ul>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_3cx_crm_connector">3CX CRM Connector</a></li>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_tiktok_shop_connector">Tiktok Shop Connector</a></li>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_power_bi_desktop_connector">Power BI Desktop Connector</a></li>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_brevo_integration">Odoo Brevo Integration</a></li>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_to_sheets_connector">Odoo To Sheets Connector</a></li>
                <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_chargebee_odoo_connector">Chargebee Odoo Connector</a></li>
            </ul>

            <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
            <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
            <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
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
