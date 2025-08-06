# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'custom delivery address | editable delivery address | one-time shipping location | sales order address override | invoice delivery address | delivery order address customization | dynamic shipping address | odoo delivery address module | temporary delivery location | custom shipping fields | unique order address | no contact duplication | flexible delivery address | delivery site entry | construction site delivery | per-order delivery info | clean contact management | address on sales PDF | address on invoice PDF | address on delivery PDF',
    'author': 'Creyox Technologies',
    "website": "https://www.creyox.com",
    'support': 'support@creyox.com',
    'category': 'warehouse',
    'summary': """
    In many industries, such as construction, logistics, or event management, goods are frequently delivered to different temporary locations. The standard Odoo flow requires creating a new contact (or child contact) for each unique delivery address, which can clutter your database and slow down the order entry process. This module provides a practical solution by allowing users to directly enter a custom delivery address on the Sales Order, without the need to create or link a new contact.

    The custom delivery address fields are automatically populated with the default address of the selected customer, but users can easily modify them to reflect the actual delivery location for that order. The updated address seamlessly flows into the Delivery Order and Invoice records, ensuring consistency across the entire sales and delivery cycle. Additionally, the custom address is displayed on the Sales Order, Delivery Order, and Invoice PDF reports, making it visible and clear to warehouse, logistics, and accounting teams.
    
    This module is especially useful for businesses that regularly deal with project-based or one-time delivery locations. It helps maintain a clean contact database while giving full flexibility in managing where products are shipped. With full backend integration and a user-friendly interface, the Custom Delivery Address module simplifies delivery management without disrupting standard Odoo workflows.

    custom delivery address,  
    editable delivery address,  
    one-time shipping location,  
    temporary delivery address,  
    sales order delivery customization,  
    delivery address without contact,  
    dynamic shipping address,  
    odoo delivery module,  
    invoice delivery address,  
    delivery order address,  
    custom shipping fields,  
    per-order delivery address,  
    no contact duplication,  
    flexible address entry,  
    construction site delivery,  
    unique delivery location,  
    address override in sale order,  
    shipping address in PDF,  
    delivery address on invoice,  
    clean contact management,  
    address auto-fill from partner,  
    shipping location customization  
    """,
    "license": "OPL-1",
    "version": "18.0",
    'description': """
    In many industries, such as construction, logistics, or event management, goods are frequently delivered to different temporary locations. The standard Odoo flow requires creating a new contact (or child contact) for each unique delivery address, which can clutter your database and slow down the order entry process. This module provides a practical solution by allowing users to directly enter a custom delivery address on the Sales Order, without the need to create or link a new contact.

    The custom delivery address fields are automatically populated with the default address of the selected customer, but users can easily modify them to reflect the actual delivery location for that order. The updated address seamlessly flows into the Delivery Order and Invoice records, ensuring consistency across the entire sales and delivery cycle. Additionally, the custom address is displayed on the Sales Order, Delivery Order, and Invoice PDF reports, making it visible and clear to warehouse, logistics, and accounting teams.

    This module is especially useful for businesses that regularly deal with project-based or one-time delivery locations. It helps maintain a clean contact database while giving full flexibility in managing where products are shipped. With full backend integration and a user-friendly interface, the Custom Delivery Address module simplifies delivery management without disrupting standard Odoo workflows.

    custom delivery address,  
    editable delivery address,  
    one-time shipping location,  
    temporary delivery address,  
    sales order delivery customization,  
    delivery address without contact,  
    dynamic shipping address,  
    odoo delivery module,  
    invoice delivery address,  
    delivery order address,  
    custom shipping fields,  
    per-order delivery address,  
    no contact duplication,  
    flexible address entry,  
    construction site delivery,  
    unique delivery location,  
    address override in sale order,  
    shipping address in PDF,  
    delivery address on invoice,  
    clean contact management,  
    address auto-fill from partner,  
    shipping location customization
    """,
    'depends': ['base', 'sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/stock_picking.xml',
        'views/account_move.xml',
        'reports/sale_order_report.xml',
        'reports/invoice_report.xml',
        'reports/delivery_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    "price": 100,
    'currency': 'USD'
}
