# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Custom grid report | Sales order matrix cleanup | No duplicate product lines | Product variant table optimization",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales",
    "summary": """
    The Custom Grid Report for Sale Orders module enhances the readability and clarity of the sale order PDF report in Odoo. It introduces three new headings — Product Description, Total Quantity, and Subtotal — for every matrix table where product variants are displayed. This ensures that whenever a product is represented in a grid (matrix) format, all the key details are available at the top of the table itself, making it easier for the user to understand the order summary without confusion.

    In addition, this module prevents the duplication of product information. Normally, when a product is shown in a matrix, Odoo also lists it again as a separate line below the table, which causes repetition. With this module, if the product is displayed in a matrix, the separate product line will not appear. For products that do not have a matrix representation, they will continue to appear as normal product lines. This keeps the sale order report clean, professional, and easy to read, while avoiding redundancy and ensuring that the customer sees a clear representation of their ordered products. 

    custom grid report,
    sales order grid cleanup,
    product matrix report,
    clean sales report,
    no duplicate product lines,
    matrix table optimization,
    product variant grid,
    odoo grid report,
    sales order matrix customization,
    grid subtotal and quantity,
    optimized sales pdf,
    remove repeated product lines,
    matrix style order report,
    clear product variant table, 
    How to avoid duplicate product lines in Odoo Sales PDF reports,
    How to show product description, total quantity, and subtotal in Odoo sales report,
    How to make sales order PDF cleaner with variant grid in Odoo,
    How to organize product variants in matrix tables in Odoo,
    How to hide repeated order lines for grid products in Odoo reports,
    How to improve sales quotation PDF layout in Odoo,
    """,
    "license": "OPL-1",
    "version": "18.0",
    "description": """
    The Custom Grid Report for Sale Orders module enhances the readability and clarity of the sale order PDF report in Odoo. It introduces three new headings — Product Description, Total Quantity, and Subtotal — for every matrix table where product variants are displayed. This ensures that whenever a product is represented in a grid (matrix) format, all the key details are available at the top of the table itself, making it easier for the user to understand the order summary without confusion.

    In addition, this module prevents the duplication of product information. Normally, when a product is shown in a matrix, Odoo also lists it again as a separate line below the table, which causes repetition. With this module, if the product is displayed in a matrix, the separate product line will not appear. For products that do not have a matrix representation, they will continue to appear as normal product lines. This keeps the sale order report clean, professional, and easy to read, while avoiding redundancy and ensuring that the customer sees a clear representation of their ordered products.  

    custom grid report,
    sales order grid cleanup,
    product matrix report,
    clean sales report,
    no duplicate product lines,
    matrix table optimization,
    product variant grid,
    odoo grid report,
    sales order matrix customization,
    grid subtotal and quantity,
    optimized sales pdf,
    remove repeated product lines,
    matrix style order report,
    clear product variant table, 
    How to avoid duplicate product lines in Odoo Sales PDF reports,
    How to show product description, total quantity, and subtotal in Odoo sales report,
    How to make sales order PDF cleaner with variant grid in Odoo,
    How to organize product variants in matrix tables in Odoo,
    How to hide repeated order lines for grid products in Odoo reports,
    How to improve sales quotation PDF layout in Odoo,
    """,
    "depends": ["base", "sale_management", "sale_product_matrix"],
    "data": [
        "security/ir.model.access.csv",
        "views/order_matrix.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
