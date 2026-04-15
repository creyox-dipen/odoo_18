# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    "name": "Group Subfolder Per Product",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Inventory",
    "summary": """
    Group Subfolder Per Product
    """,
    "license": "OPL-1",
    "version": "18.0.0.1",
    "description": """
    Group Subfolder Per Product
    """,
    "depends": ["base", "documents", "stock_account", "product"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/folder_change_warning.xml",
        "wizard/folder_delete_warning_views.xml",
        "views/product_category_views.xml",
        "views/product_template_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cr_group_subfolder_product/static/src/js/document_remove_filter.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
}
