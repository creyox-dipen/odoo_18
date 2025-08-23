# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Merge Duplicate Data Extended",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Services",
    "summary": """
        Merge Duplicate Data Extended
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
        Merge Duplicate Data Extended
    """,
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/merge_access.xml",
        "views/res_partner.xml",
        "views/find_duplicate_wiz.xml",
        "views/merge_menu.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    # "price": ,
    "currency": "USD",
}