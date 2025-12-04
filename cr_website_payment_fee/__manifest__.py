# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    "name": "Website Payment Fee | E-Commerce Payment Charge | Website Checkout Fee | Website Transaction Fee",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "description": """
        This module enables you to configure and apply additional fees during checkout based on the selected payment method, 
        making it especially useful for covering payment gateway charges or service-related costs from specific providers. 
        From the "Extra Fees" tab in the Payment Provider settings, users can define either fixed or percentage-based fees, 
        which are automatically calculated and applied during the checkout process on the website. The applied fee is clearly 
        displayed in the checkout amount summary, ensuring transparency for the customer. A corresponding line is added in the 
        backend Sale Order using a configurable product, allowing easy identification of the payment fee. For percentage-based fees, 
        the amount is dynamically updated based on changes in the cart total. Additionally, the module supports conditional application 
        of fees, allowing charges to be triggered only when the cart total is less than or greater than a specified amount.
        Website Payment Fee,
        E-Commerce Payment Charge,
        Website Checkout Fee,
        Website Transaction Fee,
        Payment Method Extra Fees,
        Payment Gateway Fee Manager,
        Checkout Payment Surcharge,
        Payment Fee by Method,
        Dynamic Payment Charges
        Advanced Payment Fees,
        Odoo Payment Fee Rules,
        eCommerce Payment Fee,
        Payment Provider Fee Configurator.
        Conditional Payment Fees
        How to set payment charge?
        How to apply payment fee?
        How to add extra charges based on payment method in Odoo?
        How can I add extra fees based on the selected payment method in Odoo?
        Is there a way to apply payment gateway charges automatically during checkout in Odoo?
        How do I configure fixed or percentage-based payment fees in Odoo?
        Can Odoo apply different fees depending on the payment provider?
        How can I show payment fees in the website checkout summary in Odoo?
        Is there an Odoo module to charge customers extra for specific payment methods?
        How can I dynamically update payment fees when the cart total changes in Odoo?
        Can I set conditions to apply fees only when the order amount is above or below a certain value in Odoo?
        How do I add a payment fee product to the Sale Order automatically in Odoo?
        What’s the best way to manage service or gateway charges during Odoo eCommerce checkout?
        """,
    "license": "OPL-1",
    "version": "18.0",
    "summary": """
        This module enables you to configure and apply additional fees during checkout based on the selected payment method, 
        making it especially useful for covering payment gateway charges or service-related costs from specific providers. 
        From the "Extra Fees" tab in the Payment Provider settings, users can define either fixed or percentage-based fees, 
        which are automatically calculated and applied during the checkout process on the website. The applied fee is clearly 
        displayed in the checkout amount summary, ensuring transparency for the customer. A corresponding line is added in the 
        backend Sale Order using a configurable product, allowing easy identification of the payment fee. For percentage-based fees, 
        the amount is dynamically updated based on changes in the cart total. Additionally, the module supports conditional application 
        of fees, allowing charges to be triggered only when the cart total is less than or greater than a specified amount.
        Website Payment Fee,
        E-Commerce Payment Charge,
        Website Checkout Fee,
        Website Transaction Fee,
        Payment Method Extra Fees,
        Payment Gateway Fee Manager,
        Checkout Payment Surcharge,
        Payment Fee by Method,
        Dynamic Payment Charges
        Advanced Payment Fees,
        Odoo Payment Fee Rules,
        eCommerce Payment Fee,
        Payment Provider Fee Configurator.
        Conditional Payment Fees
        How to set payment charge?
        How to apply payment fee?
        How to add extra charges based on payment method in Odoo?
        How can I add extra fees based on the selected payment method in Odoo?
        Is there a way to apply payment gateway charges automatically during checkout in Odoo?
        How do I configure fixed or percentage-based payment fees in Odoo?
        Can Odoo apply different fees depending on the payment provider?
        How can I show payment fees in the website checkout summary in Odoo?
        Is there an Odoo module to charge customers extra for specific payment methods?
        How can I dynamically update payment fees when the cart total changes in Odoo?
        Can I set conditions to apply fees only when the order amount is above or below a certain value in Odoo?
        How do I add a payment fee product to the Sale Order automatically in Odoo?
        What’s the best way to manage service or gateway charges during Odoo eCommerce checkout?
    """,
    "depends": [
        "base",
        "mail",
        "account",
        "sale_management",
        "website",
        "web",
        "website_sale",
        "payment",
    ],
    "data": [
        "data/product_data.xml",
        "views/payment_provider.xml",
        "views/website_payment_method_form_inherited.xml",
        "views/website_sale_total_inherited.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "cr_website_payment_fee/static/src/js/payment_form.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": [
        "static/description/banner.png",
    ],
    "price": 129,
    "currency": "USD",
}
