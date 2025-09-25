# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stripe Account Statements",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """
        Stripe Account Statements
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
        Stripe Account Statements
    """,
    "depends": ["base", "payment_stripe", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_provider.xml",
        "views/account_journal.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}