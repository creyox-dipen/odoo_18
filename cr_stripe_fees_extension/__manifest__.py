# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Fees Extension",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Services",
    "summary": """
        Stripe Fees Extension
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
        Stripe Fees Extension
    """,
    "depends": ["base", "payment_stripe"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
        # "views/stripe_payment_fees_badge.xml",
    ],
    'assets': {
        'web.assets_frontend': [
            'cr_stripe_fees_extension/static/src/js/payment_fees_badge.js',
            'cr_stripe_fees_extension/static/src/css/payment_fees_badge.css',
        ],
    },

    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
