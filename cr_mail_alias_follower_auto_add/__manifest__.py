# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    "name": "Auto Add Followers via Mail Alias | Mail Alias Auto Follower Manager | Automatic Followers from Email | Automatic Contact Creation from Mail Alias",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "summary": """
    The Auto Add Followers via Mail Alias module enhances Odoo’s default email routing by automatically managing followers from incoming emails. In standard Odoo, recipients from the To and CC fields are added only if a matching contact exists; otherwise, they are skipped. This module automatically creates missing contacts from those email addresses and adds them as followers, ensuring complete and accurate communication tracking.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
        <h1>Auto Add Followers via Mail Alias – Mail Alias Automation</h1>

        <p>The Auto Add Followers via Mail Alias module enhances Odoo’s default email routing by automatically managing followers from incoming emails. It reads all recipients from the To and CC fields and ensures they are properly linked to the related record.</p>
        
        <h2>Key Features</h2>
        <ul>
            <li>Automatically processes To and CC email recipients</li>
            <li>Adds existing contacts as followers to related records</li>
            <li>Auto-creates missing contacts from incoming email addresses</li>
            <li>Works seamlessly with Odoo mail alias routing</li>
            <li>No configuration required – ready to use after installation</li>
            <li>Reads and processes all recipients from both To and CC fields of incoming emails.</li>
        </ul>
        
        <h2>Benefits</h2>
        <ul>
            <li>Prevents missed communication tracking</li>
            <li>Ensures complete follower management</li>
            <li>Reduces manual contact creation effort</li>
            <li>Improves collaboration across teams and customers</li>
            <li>Keeps email conversations fully traceable in Odoo</li>
        </ul>
        
        <h2>Why Choose This Module?</h2>
        <p>By default, Odoo only adds First To recipient as followers if a matching contact already exists. This module improves that behavior by automatically creating missing contacts from To and CC both headers and adding them as followers. It guarantees that every relevant participant stays connected to the record, ensuring accurate and complete communication management.</p>
        
        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_dynamic_user_notification">Dynamic User Notification on Record Creation or State Change</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_mailchamp_integration">Odoo Mailchimp Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_brevo_integration">Odoo Brevo Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_kit_integration">Odoo Kit Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_3cx_crm_connector">Odoo 3CX CRM Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_pos_network_printer_res">POS Network Printer</a></li>
        </ul>
    """,
    "depends": ["mail"],
    "data": [],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png"],
    "price": 20,
    "currency": "USD",
}
