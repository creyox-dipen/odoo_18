# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'cr_analytic_account',
    'author': 'Creyox Technologies',
    "website": "https://www.creyox.com",
    'support': 'support@creyox.com',
    'category': 'Warehouse',
    'summary': """
    Analytic Account Distribution
    """,
    "license": "OPL-1",
    "version": "18.0",
    'description': """
    Analytic Account Distribution
    """,
    'depends': ['base', 'sale_management', 'stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings.xml',
        'views/stock_picking.xml',
        'views/stock_move_line.xml',
    ],
    # 'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    "price": 100,
    'currency': 'USD'
}