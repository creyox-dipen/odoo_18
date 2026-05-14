# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'CRM Copy Folders',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales/CRM",
    'summary': 'Copy folders in sale order',
    "license": "OPL-1",
    "version": "18.0.0.0",
    'description': """
        This module allows copying folders in CRM.
    """,
    'depends': ['crm', 'sale_management', 'project', 'documents', 'cr_crm_opportunity_document_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_folder_structure_views.xml',
    ],
    'installable': True,
    'application': True,
}
