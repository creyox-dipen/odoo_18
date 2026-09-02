# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

{
    "name": "Purchase Order Manufacturing Part Number",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_purchase_manufacturing_part_number&version=18.0",
    "category": "Purchases",
    "summary": """
        Adds Manufacturing Part Number to Product and Purchase Order Lines.
    """,
    "description": """
        Adds Manufacturing Part Number to Product and Purchase Order Lines.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "depends": ["purchase", "bizzup_product_purchase_customization", "bizzup_product_category"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/purchase_order_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
}
