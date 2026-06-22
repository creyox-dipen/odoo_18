# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'CR Tadam Custom Fields',
    'version': '18.0.0.0',
    'category': 'Extra Tools',
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    'summary': 'Add custom fields for Tadam integration',
    'author': 'Creyox Technologies',
    'depends': ['base', 'sale_management', 'purchase', 'payment', 'mail'],
    'data': [
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/payment_transaction_views.xml',
        'views/purchase_order_views.xml',
        'views/discuss_channel_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}
