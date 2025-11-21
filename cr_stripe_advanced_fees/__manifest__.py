# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Advanced Fees",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
       Stripe Advanced Fees
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    Stripe Advanced Fees
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
        "views/stripe_payment_fees_badge.xml",
    ],
    'assets': {
        'web.assets_frontend': [
            'cr_stripe_advanced_fees/static/src/js/payment_fees_badge.js',
            'cr_stripe_advanced_fees/static/src/css/payment_fees_badge.css',
        ],
    },

    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 70,
    "currency": "USD",
}
