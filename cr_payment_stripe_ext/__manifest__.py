# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Payment Stripe Extension",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
    Payment Stripe Extension
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
    Payment Stripe Extension
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move.xml",
        "views/payment_access.xml"
    ],

    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
