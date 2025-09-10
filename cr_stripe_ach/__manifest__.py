# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe ACH Payment Provider",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Services",
    "summary": """
        Stripe ACH Payment Provider
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
        Stripe ACH Payment Provider
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}