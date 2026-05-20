# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Sale Order Product Category Customization",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales",
    "summary": "Restrict product category options to EVR and Bank Hours when creating a product from a Sale Order line.",
    "license": "OPL-1",
    "version": "18.0.0.1",
    "description": """
        Restrict product category options to EVR and Bank Hours when creating a product from a Sale Order line.
    """,
    "depends": [
        "sale_management",
        "product",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
