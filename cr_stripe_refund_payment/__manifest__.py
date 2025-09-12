# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Refund Payment",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Services",
    "summary": """
        Stripe Refund Payment
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
        Stripe Refund Payment
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}