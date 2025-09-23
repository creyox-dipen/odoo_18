# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Fees Extension | Stripe Transaction Fees in Odoo | Stripe Charges & Fees Extension Odoo | Odoo Stripe Payment Fee Integration",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    The Odoo Stripe Domestic & International Fees module allows businesses to automatically manage Stripe payment fees for both local and global transactions. With this extension, you can define separate fee rules for domestic and international payments, ensuring accurate cost calculation and seamless integration with Odoo’s invoicing and sales workflows.

    This module helps streamline payment management by applying precise transaction fees during checkout, reducing manual adjustments, and improving financial reporting. Perfect for companies using Stripe in multiple regions, it supports both B2B and B2C operations while enhancing transparency and control over payment processing.
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
    The Odoo Stripe Domestic & International Fees module allows businesses to automatically manage Stripe payment fees for both local and global transactions. With this extension, you can define separate fee rules for domestic and international payments, ensuring accurate cost calculation and seamless integration with Odoo’s invoicing and sales workflows.

    This module helps streamline payment management by applying precise transaction fees during checkout, reducing manual adjustments, and improving financial reporting. Perfect for companies using Stripe in multiple regions, it supports both B2B and B2C operations while enhancing transparency and control over payment processing.
    """,
    "depends": ["base", "payment_stripe"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
        "views/stripe_payment_fees_badge.xml",
    ],
    # 'assets': {
    #     'web.assets_frontend': [
    #         'cr_stripe_fees_extension/static/src/js/payment_fees_badge.js',
    #         'cr_stripe_fees_extension/static/src/css/payment_fees_badge.css',
    #     ],
    # },

    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
