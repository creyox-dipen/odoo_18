# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    'name': 'NMI Payment Gateway | NMI API Integration | Payment Provider: NMI | NMI Payment Solutions | NMI Payment Processing | NMI Payment System',
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    'category': 'Website',
    'description':"""
        NMI Payment Gateway is a module where users will Streamline your payment processing with NMI,
        NMI payment gateway for an Odoo website includes setting up the framework to permit clients to 
        make secure and fearless payment for their purchase online, It creates a secure and efficient 
        payment process, allowing your customers to complete transactions seamlessly, This integration 
        includes configuring NMI API with odoo's eCommerce platform to process the payments for customer purchases.
        
        NMI Payment Gateway
        NMI API Integration,
        Payment Provider: NMI,
        NMI Payment Solutions,
        NMI Payment System,
        NMI Payment Processing,
        NMI recurring billing,
        NMI mobile payments,
        NMI payment acceptance,
        Payment NMI Gateway,
        NMI Payment Integratio,
        NMI Payment Connector,
        NMI Payment Gateway Integration,
        NMI Checkout Integration,
        NMI Online Payment Gateway,
        NMI Secure Payment System,
        NMI Payment Processor,
        NMI Payment Solution,
        NMI Payment Extension,
        How can the NMI payment integration help my website accept payments easily?
        What steps are required to set up NMI as a checkout option?
        How secure is the NMI payment method for customers?
        Can I handle both sales and invoices using NMI payments?
        What types of payments can my customers make with NMI?
        """,
    "license": "OPL-1",
    'version': '18.0.0.2',
    "price": "349",
    "currency": "USD",
    'summary': """
        NMI Payment Gateway is a module where users will Streamline your payment processing with NMI,
        NMI payment gateway for an Odoo website includes setting up the framework to permit clients to 
        make secure and fearless payment for their purchase online, It creates a secure and efficient 
        payment process, allowing your customers to complete transactions seamlessly, This integration 
        includes configuring NMI API with odoo's eCommerce platform to process the payments for customer purchases.
        
        NMI Payment Gateway
        NMI API Integration,
        Payment Provider: NMI,
        NMI Payment Solutions,
        NMI Payment System,
        NMI Payment Processing,
        NMI recurring billing,
        NMI mobile payments,
        NMI payment acceptance,
        Payment NMI Gateway,
        NMI Payment Integration,
        NMI Payment Connector,
        NMI Payment Gateway Integration,
        NMI Checkout Integration,
        NMI Online Payment Gateway,
        NMI Secure Payment System,
        NMI Payment Processor,
        NMI Payment Solution,
        NMI Payment Extension,
        How can the NMI payment integration help my website accept payments easily?
        What steps are required to set up NMI as a checkout option?
        How secure is the NMI payment method for customers?
        Can I handle both sales and invoices using NMI payments?
        What types of payments can my customers make with NMI?
    """,
    'depends': ["base", "payment", "account", "website"],
    'data': [
        'views/payment_nmi_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cr_payment_nmi_integration/static/src/js/nmi_ach_form.js',
            'cr_payment_nmi_integration/static/src/js/nmi_card_form.js',
        ],
    },
    'application': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    "images": ["static/description/banner.png", ],
}
