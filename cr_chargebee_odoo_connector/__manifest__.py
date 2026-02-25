# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Chargebee Integration | Odoo Chargebee Connection | Chargebee Subscription Management | Chargebee Odoo Connector | Odoo Chargebee Integration | Odoo Chargebee Connector",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Accounting",
    "summary": """The Chargebee Integration module connects Odoo with Chargebee's subscription management services. 
    This integration facilitates efficient handling of subscriptions, customers, and invoices 
    directly within the Odoo interface.

        Chargebee Integration,
        Odoo Chargebee Integration,
        Subscription Management Integration,
        Customer Management in Odoo,
        Invoice Synchronization in Odoo,
        Chargebee Integration for Odoo,
        Odoo Chargebee Connector,
        Sync Chargebee with Odoo,
        How to integrate Chargebee with Odoo,
        How to manage Chargebee subscriptions in Odoo,
        Subscription Management in Odoo,
        Manage Chargebee customers in Odoo,
        How to set up Chargebee with Odoo,
        Automate subscription workflows in Odoo,
        Real-time updates from Chargebee in Odoo,
        Chargebee-Odoo subscription synchronization,
        Centralized customer and invoice management in Odoo,
        How to configure Chargebee integration settings in Odoo,
        How to link Odoo and Chargebee accounts using API credentials,
        How to sync Chargebee invoices with Odoo invoices,
        How to import existing Chargebee customers into Odoo,
        How to manage Chargebee subscription renewals from Odoo,
        How to track subscription statuses in Chargebee and Odoo,
        How to add Chargebee customer details in Odoo,
        How to access and sync Chargebee invoices in Odoo,
        How to track invoice payments between Chargebee and Odoo,
        How to receive notifications for Chargebee subscription updates in Odoo,
        How to automate invoice and subscription updates between Chargebee and Odoo,
        How to manage subscription billing cycles in Odoo,
        How to generate reports for Chargebee subscription data in Odoo,
        How to export Odoo customer data to Chargebee for enhanced billing,
        How to configure Chargebee user roles and permissions in Odoo,
        How to troubleshoot Chargebee and Odoo integration issues,
        Best Chargebee solution for Odoo,
        Odoo Chargebee Integration Guide,
        How to track subscription metrics in Odoo,
        Automate Chargebee data sync with Odoo,
        Subscription reporting in Odoo using Chargebee,
        Chargebee customer performance tracking,
        Chargebee-Odoo data mapping,
        Chargebee CRM and Odoo Integration,
        How to configure Chargebee in Odoo,
        Advanced Chargebee-Odoo Connector,
        Best subscription management solution in Odoo.
    """,
    "version": "18.0",
    "license": "OPL-1",
    "description": """
    The Chargebee Integration module provides a powerful connection between Odoo and Chargebee's subscription management services. 
    From handling customer subscriptions to synchronizing invoices and payments, this module delivers comprehensive tools for managing recurring revenue directly in Odoo.

        Chargebee Integration,
        Odoo Chargebee Integration,
        Subscription Management Integration,
        Customer Management in Odoo,
        Invoice Synchronization in Odoo,
        Chargebee Integration for Odoo,
        Odoo Chargebee Connector,
        Sync Chargebee with Odoo,
        How to integrate Chargebee with Odoo,
        How to manage Chargebee subscriptions in Odoo,
        Manage Chargebee customers in Odoo,
        How to set up Chargebee with Odoo,
        Automate subscription workflows in Odoo,
        Real-time updates from Chargebee in Odoo,
        How to manage subscription billing cycles in Odoo,
        How to generate reports for Chargebee subscription data in Odoo,
        How to export Odoo customer data to Chargebee for enhanced billing,
        How to configure Chargebee user roles and permissions in Odoo,
        How to troubleshoot Chargebee and Odoo integration issues,
        Best Chargebee solution for Odoo,
        Odoo Chargebee Integration Guide,
        How to track subscription metrics in Odoo,
        Automate Chargebee data sync with Odoo,
        Subscription reporting in Odoo using Chargebee,
        Chargebee customer performance tracking,
        Chargebee-Odoo data mapping,
        Chargebee CRM and Odoo Integration,
        Advanced Chargebee-Odoo Connector,
        Best subscription management solution in Odoo.

    - Customer Management: Import and synchronize customer details between Chargebee and Odoo.
    - Subscription Handling: Automatically update subscription statuses, renewals, and cancellations.
    - Invoice Synchronization: Sync Chargebee invoices to Odoo for seamless accounting.
    - Reporting: Access subscription and revenue reports directly in Odoo.
    - Notifications: Receive real-time notifications for subscription and invoice updates.
    - User Management: Assign roles and permissions for Chargebee access in Odoo.

    Why Choose This Integration?
    - Centralized Management: Manage subscriptions, customers, and invoices from one platform.
    - Automation: Save time with automated data synchronization and real-time updates.
    - Accuracy: Minimize errors by ensuring Chargebee and Odoo data remain consistent.

    Use Cases:
    - Managing recurring revenue and subscription plans.
    - Synchronizing customer details and invoices for accounting purposes.
    - Automating subscription renewals and updates.

    Perfect for:
    - Subscription-based businesses looking for streamlined management tools.
    - Accounting teams that require accurate and up-to-date billing data.
    - Businesses aiming to enhance their subscription lifecycle management.
    """,
    "depends": ["sale_management", "account", "base", "contacts"],
    "external_dependencies": {
        'python': ['chargebee'],
    },
    "data": [
        "views/chargebee_config_views.xml",
        "views/res_partner_views.xml",
        "views/item_family_views.xml",
        "views/product_template_views.xml",
        "views/chargebee_item_family_sync_wizard_form_views.xml",
        "data/ir_sequence_data.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png"],
    "price": 239,
    "currency": "USD",
}
