# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "CRM Project Folder Automation",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales/CRM",
    "summary": "Automated Project folder and shortcut creation from CRM Opportunities",
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
        Automates Document workspace organization between CRM and Project modules.
        
        Key Features:
        * Auto-creates "Customer Data" and SO-specific folders in Project workspaces on SO confirmation.
        * Links standard folders from Opportunity to Project using official Odoo shortcuts (Blue links).
        * Global "Folder Structure" configuration wizard for defining standard project sub-folders.
        * Support for complex hierarchies using dot-notation sequences (1.0, 1.1, etc.).
        * Overrides Sale Order "Documents" smart button to navigate directly to the new project folders.
        * Automatic synchronization of document counts on the Sale Order form.
    """,
    "depends": [
        "crm",
        "sale_management",
        "project",
        "documents",
        "cr_crm_opportunity_document_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_folder_structure_views.xml",
    ],
    "installable": True,
    "application": True,
}
