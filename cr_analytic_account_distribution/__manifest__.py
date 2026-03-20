# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Stock Analytic Distribution Manager | Smart Stock Analytic Integration | Stock Picking Analytic Account | Analytic Distribution on Stock Picking",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Warehouse",
    "summary": """
    The Analytic Account & Distribution Manager for Stock automatically transfers analytic accounts or analytic distribution from Sales and Purchase Orders to Delivery and Receipt operations, eliminating manual data entry and ensuring accurate financial tracking. It supports analytic configuration at both Picking and Stock Move levels, maintains a complete audit trail across inventory operations, and enables precise multi-plan, percentage-based cost allocation for better visibility into operational costs and profitability.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Stock Analytic Account & Distribution Integration for Odoo Inventory</h1>

    <p>This module seamlessly integrates Analytic Accounts and Analytic Distribution into Odoo Inventory operations. It automatically propagates analytic information from Sales Orders and Purchase Orders to Delivery and Receipt transfers, ensuring accurate financial tracking and cost allocation across warehouse processes.</p>
    
    <h2>Hot Features</h2>
    <ul>
        <li>Automatic transfer of Analytic Account or Analytic Distribution from Sales Order to Delivery Order</li>
        <li>Automatic transfer of Analytic data from Purchase Order to Receipt</li>
        <li>Support for both Analytic Account and Analytic Distribution modes</li>
        <li>Apply analytic tracking by Picking level or Stock Move level</li>
        <li>Analytic data automatically copied during Return operations</li>
        <li>Multi-plan and percentage-based analytic distribution support</li>
    </ul>
    
    <h2>Key Features</h2>
    <ul>
        <li>Enable analytic management directly from Inventory settings</li>
        <li>Configure analytic entry selection: Analytic Account or Distribution</li>
        <li>View analytic details on Delivery and Receipt forms</li>
        <li>Access analytic values on individual Stock Move lines</li>
        <li>Maintain full audit trail from order confirmation to stock transfer</li>
        <li>Eliminate manual analytic entry in warehouse operations</li>
        <li>Improve cost center, department, and project-based tracking</li>
    </ul>
    
    <h2>Benefits</h2>
    <ul>
        <li>Accurate warehouse cost allocation</li>
        <li>Improved financial transparency in inventory operations</li>
        <li>Reduced manual work and human error</li>
        <li>Better project and departmental profitability tracking</li>
        <li>Complete analytic consistency across Sales, Purchase, and Stock</li>
    </ul>
    
    <h2>Why Choose This Module?</h2>
    <p>This solution bridges the gap between Sales, Purchase, and Inventory by bringing structured analytic accounting into stock operations. Whether you use traditional Analytic Accounts or advanced Analytic Distribution, this module ensures automation, accuracy, and financial clarity throughout your supply chain workflow.</p>
    
    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_picking_move_from_invoice">Stock Picking/Move From invoice</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_stock_intertransfer_account">Stock Inter Transfer Account</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_actual_costing">Actual Costing Method for Odoo Inventory</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_actual_costing_ent">Actual Costing Method for Odoo Inventory</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_lot_purchase_costing">Lot Purchase Costing</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_mrp_process_costing">MRP Process Costing</a></li>
    </ul>
    
    <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p> 
    <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p> 
    <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    "depends": ["base", "sale_management", "stock", "account", "purchase"],
    "data": [
        "views/res_config_settings.xml",
        "views/stock_picking.xml",
        "views/stock_move_line.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 20,
    "currency": "USD",
}
