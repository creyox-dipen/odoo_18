# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

{
    "name": "Credit Note Confirm Warning",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_credit_note_confirm_warning&version=18.0",
    "category": "Accounting",
    "summary": "Shows warning wizard when confirming credit note.\nProvides confirmation step before posting.",
    "license": "OPL-1",
    "version": "18.0.0.1",
    "description": """
        Shows warning wizard when confirming credit note.\nProvides confirmation step before posting.
    """,
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/credit_note_confirm_wizard_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "assets": {},
    "installable": True,
    "application": True,
}
