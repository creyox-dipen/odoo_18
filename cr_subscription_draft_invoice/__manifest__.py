# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Subscription draft invoice | Draft Subscription Invoice | Recurring Plan Draft Control | Manual Subscription Billing | Review Before Posting Invoices",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales/Subscriptions",
    "summary": """
    In Odoo 16 and higher, subscription invoices are created and automatically posted, removing the option to review them before validation. For many businesses, this creates challenges as important details like customer info, products, discounts, and taxes often need to be checked before confirming.
    
    This module solves the issue by adding a Draft Invoice option in the Recurring Plan. When enabled, invoices are generated in Draft state, giving users the flexibility to review and confirm them manually. If left unchecked, the system continues posting invoices automatically — ensuring full control and accuracy in your subscription billing process.
    
    draft subscription invoice,  
    subscription draft billing,  
    recurring plan draft invoice,  
    subscription invoice control,  
    review subscription invoice,  
    manual subscription billing,  
    subscription invoice verification,  
    odoo draft invoice module,  
    recurring invoice flexibility,
    generate draft subscription invoices,   
    subscription invoice customization,  
    subscription billing review option,  
    odoo subscription draft invoices,
    How to generate draft invoices for subscriptions in Odoo,  
    How to enable Draft Invoice option in recurring plans,  
    How to review subscription invoices before posting in Odoo,  
    How to control automatic posting of subscription invoices,  
    How to verify customer and product details in subscription invoices,  
    How to prevent auto-posting of subscription invoices,  
    How to manually confirm subscription invoices in Odoo,  
    How to streamline subscription invoice review process in Odoo,  
    How to improve accuracy in recurring subscription billing, 
    How to manage draft vs posted invoices for subscriptions in Odoo,   
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
    In Odoo 16 and higher, subscription invoices are created and automatically posted, removing the option to review them before validation. For many businesses, this creates challenges as important details like customer info, products, discounts, and taxes often need to be checked before confirming.
    
    This module solves the issue by adding a Draft Invoice option in the Recurring Plan. When enabled, invoices are generated in Draft state, giving users the flexibility to review and confirm them manually. If left unchecked, the system continues posting invoices automatically — ensuring full control and accuracy in your subscription billing process.

    draft subscription invoice,  
    subscription draft billing,  
    recurring plan draft invoice,  
    subscription invoice control,  
    review subscription invoice,  
    manual subscription billing,  
    subscription invoice verification,  
    odoo draft invoice module,  
    recurring invoice flexibility,
    generate draft subscription invoices,   
    subscription invoice customization,  
    subscription billing review option,  
    odoo subscription draft invoices,
    How to generate draft invoices for subscriptions in Odoo,  
    How to enable Draft Invoice option in recurring plans,  
    How to review subscription invoices before posting in Odoo,  
    How to control automatic posting of subscription invoices,  
    How to verify customer and product details in subscription invoices,  
    How to prevent auto-posting of subscription invoices,  
    How to manually confirm subscription invoices in Odoo,  
    How to streamline subscription invoice review process in Odoo,  
    How to improve accuracy in recurring subscription billing, 
    How to manage draft vs posted invoices for subscriptions in Odoo, 
    """,
    "depends": ['base', 'sale_subscription'],
    "data": [
        "security/ir.model.access.csv",
        "views/draft_invoice.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
