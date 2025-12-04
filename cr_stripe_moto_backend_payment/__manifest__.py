# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Moto payments",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    Stripe Moto payments
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    Stripe Moto payments
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/stripe_payment_fees_badge.xml",
        "wizards/stripe_payment_fees_badge.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    # "price": ,
    "currency": "USD",
}
