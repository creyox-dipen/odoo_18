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
    "depends": ["base", "payment"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/payment_transaction.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}