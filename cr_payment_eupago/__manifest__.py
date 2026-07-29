# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

{
    "name": "euPago Payment Provider | euPago Integration | Portuguese Payment Gateway | MB WAY | Multibanco",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_payment_eupago&version=18.0",
    "category": "Accounting",
    "summary": """
        The euPago Payment Provider module seamlessly integrates your Odoo system with Portugal's leading payment gateway, euPago. It empowers businesses to offer a localized and secure checkout experience, directly enhancing customer satisfaction and boosting conversion rates for the Portuguese market.

        Comprehensive integration supports key payment methods including Multibanco (ATM Reference), MB WAY, and 3D Secure Credit Cards. It ensures automated payment synchronization, secure transaction processing, and a streamlined workflow for both administrators and customers.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
        <h1>euPago Payment Provider – Odoo Portuguese Payment Gateway Integration</h1>
        <p>
            The euPago Payment Provider module seamlessly integrates your Odoo system with Portugal's leading payment gateway. By enabling popular localized payment methods, this system eliminates manual reconciliation, reduces friction at checkout, and ensures your transactions are always secure and up-to-date.
        </p>
        
        <h2>Key Features</h2>
        <ul>
            <li>Supports Multibanco (ATM Reference) payments directly in Odoo</li>
            <li>Enables MB WAY transactions for instant mobile payments</li>
            <li>Supports 3D Secure Credit Card payments for enhanced security</li>
            <li>Automated synchronization of payment statuses with Odoo</li>
            <li>Secure and robust transaction processing flow</li>
            <li>Seamless integration with Odoo Accounting and E-commerce</li>
            <li>Real-time payment confirmation and automated invoice reconciliation</li>
        </ul>
        
        <h2>Benefits</h2>
        <ul>
            <li>Increases conversion rates by offering preferred local payment methods in Portugal</li>
            <li>Reduces administrative overhead with automated payment tracking and reconciliation</li>
            <li>Eliminates manual entry for tracking customer payments</li>
            <li>Enhances customer satisfaction with a smooth and secure checkout experience</li>
            <li>Boosts financial management with real-time visibility into incoming payments</li>
        </ul>
        
        <h2>Why Choose This euPago Payment Provider?</h2>
        <p>
            This integration provides a complete payment automation system for businesses operating in Portugal using Odoo. It ensures accurate transaction tracking, faster payment processing, reliable reconciliation, and effortless management of payments—all within a single, secure platform.
        </p>

        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_global_payment_provider">Advanced Global Payments Connector</a></li>

            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_payment_fiserv">Fiserv Payment Gateway</a></li>

            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_paylike_payment">Paylike Payment Gateway for Odoo</a></li>

            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_payment_nmi_integration">NMI Payment Gateway</a></li>

            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_montonio_integration">Montonio Payment Integration</a></li>

            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_payment_conekta_oxoo">Conekta Payment Gateway</a></li>
        </ul>

        <p>
            For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a>
        </p>
        <p>
            Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a>
        </p>
        <p>
            Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a>
        </p>
    """,
    "depends": ["payment", "account_payment"],
    "data": [
        "security/ir.model.access.csv",
        "data/product_data.xml",
        "wizard/eupago_refund_wizard_views.xml",
        "views/account_move_views.xml",
        "views/payment_eupago_templates.xml",
        "views/payment_provider_views.xml",
        "data/payment_provider_data.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cr_payment_eupago/static/src/js/payment_form.js",
            "cr_payment_eupago/static/src/js/payment_fees_badge.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 309,
    "currency": "USD",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
