# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Subscription draft invoice",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales",
    "summary": """
        Subscription draft invoice
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
        Subscription draft invoice
    """,
    "depends": ['base', 'sale_subscription'],
    "data": [
        "security/ir.model.access.csv",
        "views/draft_invoice.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    # "price": 40,
    "currency": "USD",
}