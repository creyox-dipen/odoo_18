# -*- coding: utf-8 -*-
{
    'name': "VendorBridge Procurement & Vendor Management ERP",
    'summary': "Procurement and Vendor Management System for Hackathon",
    'description': """
        Manage vendor profiles, track performance, raise procurement requests,
        and handle purchase orders seamlessly in Odoo 18.
    """,
    'author': "Heet,Dipen,Sujal",
    'category': 'Inventory/Purchase',
    'version': '18.0.0.1',
    'depends': [
        'purchase',
        'purchase_stock',
        'account',
        'contacts',
        'mail',
        'portal',
        'web'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/mail_templates.xml',
        'views/res_partner_views.xml',
        'views/vendor_quotation_views.xml',
        'views/approval_remark_wizard_views.xml',
        'views/purchase_order_views.xml',
        'views/approval_views.xml',
        'views/dashboard_views.xml',
        'views/portal_templates.xml',
        'reports/quotation_report.xml',
    ],
    'installable': True,
    'application': True,
}

