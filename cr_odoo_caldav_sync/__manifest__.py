# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'CalDAV Calendar Sync',
    'author': 'Creyox Technologies',
    'website': 'https://www.creyox.com',
    'support': 'support@creyox.com',
    'category': 'Warehouse',
    'summary': """
    odoo caldav sync,
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    'description': """
    odoo caldav sync
    """,
    'depends': ['base', 'calendar'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/caldav_account_views.xml',
        'views/res_config_settings_views.xml',
        'views/calendar_views.xml',
        'views/menu.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    "price": 100,
    'currency': 'USD'
}
