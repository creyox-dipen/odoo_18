# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Odoo Stripe Advanced Payment Fees | Auto Transaction Fees for Domestic & International Payments",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_stripe_advanced_fees&version=18.0",
    "category": "Accounting",
    "summary": """
    Automatically calculate Stripe payment fees in Odoo with advanced domestic 
    and international fee rules. Configure fees per payment method, apply automatic 
    fallback rules, remove fees above limits, and ensure transparent checkout and invoicing 
    with Stripe integration.
    """,
    "license": "OPL-1",
    "version": "18.0.0.1",
    "description": """
    <h1>Stripe Advanced Payment Fees for Odoo – Domestic & International Fee Automation</h1>
    <p>The Stripe Advanced Payment Fees module for Odoo automatically calculates and applies Stripe transaction fees during checkout. Businesses can configure different fee rules for each Stripe payment method, ensuring accurate charges for every payment option. The module also supports domestic and international fee logic based on the customer’s shipping country, allowing companies to apply different rates for local and global transactions. If a payment method does not have a specific rule configured, the system automatically applies a default fee method to ensure continuous and error-free fee calculation.</p>

    <h2>Key Features</h2>
    <ul>
    <li>Automatic Stripe transaction fee calculation during checkout</li>
    <li>Separate domestic and international fee rules</li>
    <li>Configure different fees for each Stripe payment method</li>
    <li>Default payment method fallback for unconfigured methods</li>
    <li>Remove transaction fees when order exceeds configured limit</li>
    <li>Transparent payment fee display for customers</li>
    <li>Seamless integration with Odoo Stripe payment system</li>
    <li>Easy configuration of payment fee rules in Odoo backend</li>
    </ul>

    <h2>Benefits</h2>
    <ul>
    <li>Automates Stripe fee calculations without manual adjustments</li>
    <li>Ensures accurate charges for domestic and international payments</li>
    <li>Improves transparency in payment processing</li>
    <li>Reduces checkout errors and manual work</li>
    <li>Provides flexible fee management for multiple payment methods</li>
    </ul>

    <h2>Why Choose This Stripe Fee Management Module?</h2>
    <p>This module simplifies Stripe payment fee handling in Odoo by automating fee calculations based on payment methods and transaction locations. Businesses can maintain transparent pricing, apply flexible fee rules, and ensure consistent payment processing while reducing manual configuration and errors.</p>

    <h2>Related Apps</h2>
    <ul>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_miro_odoo_integration">Odoo Miro Connector</a></li>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_gelato_odoo_integration">Odoo To Gelato Integration</a></li>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_nacex_odoo_integration">Nacex Shipping Integration</a></li>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_mydsv_odoo">MYDSV Shipping Integration</a></li>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_bigcommerce_odoo_integration">Advanced Odoo BigCommerce Connector</a></li>
    <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_bigquerrys_odoo_integration">Advanced Odoo BigCommerce Connector</a></li>
    </ul>

    <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
    <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
    <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    "depends": [
        "base",
        "payment_stripe",
        "account",
        "sale_management",
        "website",
        "website_sale",
    ],
    "data": [
        "data/product_data.xml",
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
        "views/stripe_payment_fees_badge.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cr_stripe_advanced_fees/static/src/js/payment_fees_badge.js",
            "cr_stripe_advanced_fees/static/src/css/payment_fees_badge.css",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 89,
    "currency": "USD",
}
