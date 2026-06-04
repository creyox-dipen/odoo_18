# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'Channable Odoo Connector: Ultimate Marketplace Sync, Order Import & Tracking',
    'author': "Creyox Technologies",
    'website': "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_channable_connector&version=18.0",
    'version': '18.0.0.0',
    'category': 'Sales',
    'summary': 
    """
    Automate Channable marketplace integration with Odoo. Import orders, sync shipping 
    & tracking, manage cancellations, and streamline eCommerce workflows with the ultimate Channable connector.
    """,
    'description': """
        <h1>Channable Odoo Connector: Ultimate Marketplace Order Sync & Integration</h1>
        <p>The Channable Odoo Connector enables seamless integration between Channable marketplaces and Odoo, automating order import, shipping synchronization, tracking updates, and payment processing for efficient multi-channel operations.</p>

        <h2>Key Features</h2>
        <ul>
            <li>One-click import of Channable marketplace orders into Odoo</li>
            <li>Automatic shipping and tracking synchronization</li>
            <li>Order cancellation sync between Odoo and Channable</li>
            <li>Auto-confirm orders, generate invoices, and register payments</li>
            <li>Manage multiple marketplaces and projects in one system</li>
            <li>Secure API integration with quick API key setup</li>
            <li>Detailed error logging with dedicated sync dashboard</li>
            <li>Instant data refresh for real-time updates</li>
            <li>Advanced data mapping to sales teams, warehouses, and carriers</li>
            <li>High-performance processing for large-scale order volumes</li>
        </ul>

        <h2>Benefits</h2>
        <ul>
            <li>Eliminates manual order entry and reduces operational errors</li>
            <li>Improves order processing speed and fulfillment accuracy</li>
            <li>Centralizes multi-marketplace management in Odoo</li>
            <li>Ensures real-time synchronization of orders and statuses</li>
            <li>Enhances scalability with high-volume optimization</li>
        </ul>

        <h2>Why Choose This Channable | Odoo Integration?</h2>
        <p>This connector is designed for businesses handling multi-channel eCommerce operations through Channable. It streamlines order workflows, ensures accurate synchronization, and provides powerful automation tools to improve efficiency, visibility, and overall performance within Odoo.</p>

        <h2>Related Keywords</h2>
        <ul>
            <li>Channable Odoo Connector</li>
            <li>Ultimate Channable Integration</li>
            <li>Odoo Marketplace Order Sync</li>
            <li>Channable E-commerce Automation</li>
            <li>Odoo Order Import Tracking</li>
            <li>Multi-channel Marketplace Sync</li>
            <li>Odoo implementation</li>
            <li>Odoo ERP implementation</li>
            <li>Odoo setup</li>
            <li>Odoo deployment</li>
            <li>Odoo UI customization</li>
            <li>Odoo access rights</li>
            <li>Odoo user restriction</li>
            <li>Odoo field visibility</li>
            <li>Odoo integration</li>
            <li>API integration Odoo</li>
            <li>Odoo third party app</li>
            <li>payment gateway integration</li>
            <li>data synchronization Odoo</li>
            <li>Odoo migration</li>
            <li>Odoo data migration</li>
            <li>Odoo version upgrade</li>
            <li>AI powered Odoo</li>
            <li>Odoo Artificial Intelligence</li>
            <li>Odoo AI solutions</li>
            <li>Odoo AI automation</li>
            <li>Odoo AI services</li>
            <li>Odoo intelligent automation</li>
            <li>AI Odoo ERP</li>
            <li>Odoo mobile app</li>
            <li>Odoo mobile development</li>
            <li>Odoo Android app</li>
            <li>Odoo iOS app</li>
            <li>Odoo support</li>
            <li>Odoo maintenance</li>
            <li>Odoo technical support</li>
            <li>Odoo bug fix</li>
            <li>Odoo training</li>
            <li>Odoo tutorial</li>
            <li>Odoo onboarding</li>
            <li>learn Odoo</li>
            <li>Odoo POS</li>
            <li>point of sale Odoo</li>
            <li>POS payment terminal</li>
            <li>Odoo restaurant POS</li>
            <li>Odoo reporting</li>
            <li>Odoo dashboard</li>
            <li>KPI dashboard Odoo</li>
            <li>Odoo Power BI</li>
            <li>real-time analytics Odoo</li>
            <li>Odoo MRP</li>
            <li>Odoo manufacturing</li>
            <li>bill of materials Odoo</li>
            <li>production cost tracking</li>
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
    'license': 'OPL-1',
    'depends': ['sale', 'sale_management', 'stock', 'delivery', 'account'],
    'data': [
        'security/channable_security.xml',
        'security/ir.model.access.csv',
        'data/channable_data.xml',
        'views/channable_connection_views.xml',
        'views/channable_project_views.xml',
        'views/channable_marketplace_views.xml',
        'wizard/channable_sync_orders_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/delivery_carrier_views.xml',
        'views/channable_sync_error_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'cr_channable_connector/static/src/js/dark_mode_toggle.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'images': ['static/description/banner.png'],
    'price': 325,
    'currency': "USD",
}