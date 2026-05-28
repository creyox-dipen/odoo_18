# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'NMI Payment Gateway | NMI API Integration | Payment Provider: NMI | NMI Payment Solutions | NMI Payment Processing | NMI Payment System',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_payment_nmi_integration&version=18.0",
    'category': 'Website',
    'summary': """
        The NMI Payment Gateway integration module brings a highly secure, PCI-DSS compliant, and robust payment processing system directly to your Odoo platform. By utilizing NMI's secure Direct Post API over HTTPS, the module ensures that sensitive credit/debit card and ACH/eCheck bank account credentials are sent directly to NMI without ever touching or being saved on your Odoo server database. To elevate customer convenience, the gateway fully integrates with NMI's secure Customer Vault tokenization, allowing customers to safely save their credit-debit cards or bank accounts for frictionless, one-click checkout on subsequent purchases. This works seamlessly across frontend eCommerce store checkouts and backend Odoo invoice payments.

        Additionally, this feature-rich integration includes real-time card BIN lookup via NMI's official v4 Query API, instantly detecting whether an entered card is credit or debit to enforce an automated surcharge matrix fee system. This allows merchants to dynamically apply custom debit or credit card surcharge percentages, automatically calculating the fees and injecting them as line items into the Sales Order and transaction totals. The module also features built-in duplicate transaction protection that intelligently manages retry checkout attempts using dynamic order timestamp signatures to prevent accidental order-declines, ensuring a smooth and uninterrupted payment experience for both customers and administrators.
        """,
    "license": "OPL-1",
    'version': '18.0.0.2',
    "price": "349",
    "currency": "USD",
    'description': """
        <h1>NMI Payment Gateway for Odoo | Secure eCommerce Payment Integration</h1>
        <p>The NMI Payment Gateway integration for Odoo lets businesses process secure credit/debit cards and ACH eCheck payments directly through their Odoo eCommerce store and backend invoicing. By linking NMI's secure Direct Post API over HTTPS, customer card details are tokenized directly with NMI's secure Customer Vault and are never saved on your local Odoo server. The module also features real-time card type BIN lookup, automated debit and credit card surcharge fees, and retry duplicate protection—boosting customer confidence and ensuring a frictionless checkout experience.</p>
        <h2>Key Features</h2>
        <ul>
            <li>Full NMI Direct Post API integration over HTTPS, keeping cardholder data completely off Odoo servers</li>
            <li>Secure Customer Vault Tokenization for credit/debit cards and ACH bank accounts for 1-click checkouts</li>
            <li>Real-time credit vs. debit card BIN lookup during checkout using NMI's official v4 Query API</li>
            <li>Automated surcharge matrix system to dynamically apply customized credit and debit card fees</li>
            <li>Secure ACH eCheck bank payment flow utilizing routing (ABA) and account numbers</li>
            <li>Built-in duplicate transaction prevention via dynamic order attempt timestamp parameters</li>
            <li>NMI fee line items automatically calculated and added directly to Sales Orders and Invoices</li>
            <li>Unified payment configuration for NMI Card and NMI ACH payment providers inside Odoo</li>
            <li>Seamless integration with frontend Odoo eCommerce checkout and backend invoicing portal</li>
        </ul>
        <h2>Benefits</h2>
        <ul>
            <li>Eliminates server compliance scope by keeping credit card and routing details completely off the Odoo database</li>
            <li>Increases repeat sales and speeds up checkout with secure Customer Vault tokenization for 1-click purchases</li>
            <li>Offsets credit card processing fees by dynamically charging custom credit and debit surcharge percentages</li>
            <li>Lowers payment costs by providing an ACH/eCheck bank account transfer checkout alternative</li>
            <li>Protects customer checkout confidence by preventing duplicate transaction declines on repeated attempts</li>
            <li>Unifies payment flows across frontend Odoo eCommerce and backend customer invoice payments</li>
        </ul>
        <h2>Why Choose This NMI Payment Gateway for Odoo?</h2>
        <p>This NMI Payment Gateway module provides Odoo merchants with an advanced, highly compliant online payment solution. It integrates NMI's robust Direct Post API and secure Customer Vault engine directly into the Odoo checkout and backend invoicing, offering automated surcharge fee line-item additions, real-time credit/debit BIN detection, and direct eCheck/ACH bank transfers. Whether you operate a high-volume eCommerce storefront or handle backend B2B invoicing, this integration delivers a seamless, robust, and compliance-free payment experience on every transaction.</p>
        <h2>Related Keywords</h2>
        <ul>
            <li>Odoo Inventory Module</li>
            <li>Odoo Stripe Integration</li>
            <li>Odoo Accounting Module</li>
            <li>Odoo 3CX Integration</li>
            <li>Odoo DocuSign Integration</li>
            <li>Odoo Invoice Customization</li>
            <li>Odoo Manufacturing Module</li>
            <li>Odoo POS Module</li>
            <li>Odoo Power BI Connector</li>
            <li>Odoo TikTok Integration</li>
            <li>Odoo Website Module</li>
            <li>Odoo eCommerce Module</li>
            <li>Odoo Bank Statement Import</li>
            <li>Odoo Marketing Automation Module</li>
            <li>Odoo POS Kitchen Printer</li>
            <li>Odoo POS Network Printer</li>
            <li>Odoo POS Restaurant Module</li>
            <li>Odoo POS USB Printer</li>
            <li>Odoo Power BI Integration</li>
        </ul>
        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_payment_fiserv">Fiserv Payment Gateway for Odoo</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_global_payment_provider">Global Payment Gateway for Odoo</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_payment_conekta_oxoo">Conekta Payment Gateway for Odoo</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_paylike_payment">Paylike Payment Integration for Odoo</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_moneris_payment_integration">Moneris Payment Integration for Odoo</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_montonio_integration">Montonio Payment Gateway for Odoo</a></li>
        </ul>
        <p>For custom Odoo integrations and payment enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
        <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
        <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    'depends': ["base", "payment", "account", "website"],
    'data': [
        'views/payment_nmi_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cr_payment_nmi_integration/static/src/js/nmi_ach_form.js',
            'cr_payment_nmi_integration/static/src/js/nmi_card_form.js',
        ],
    },
    'application': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    "images": ["static/description/banner.png", ],
}
