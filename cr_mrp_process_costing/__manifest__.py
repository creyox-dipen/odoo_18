# -*- coding: utf-8 -*-
# Part of Creyox Technologies

{
    "name": "MRP Process Costing | MRP Process Costing With Accounting | Automatic Calculation Of Manufacturing Order Costing | "
            "Advanced MRP Process Costing | Accounting For Manufacturing Order With Costing",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    'depends': ['base', 'mrp', 'account'],
    "category": "Manufacturing",
    "description": """The Cost of Manufacturing Order module in Odoo is a comprehensive tool designed to calculate 
    and manage the costs associated with manufacturing orders. This module seamlessly integrates manufacturing 
    and accounting processes, enabling businesses to monitor and control Material, Labor, and Overhead costs with 
    precision.

    The module offers two flexible costing options: Manual Entry and Work-center Based Calculation. Manual Entry 
    allows users to input costs directly, while the Work-center Based Calculation automatically determines costs 
    based on pre-configured rates in the work centers. With its advanced accounting integration, the module can 
    also generate journal entries to track these costs in your financial records, ensuring a transparent and 
    accurate financial workflow.

    Users can generate detailed PDF reports for each manufacturing order, showcasing the cost breakdown and 
    overall manufacturing expenses. This feature-rich solution not only simplifies production cost management 
    but also ensures a seamless connection between operational and financial data.

    Cost of Manufacturing Order,
        Advanced Manufacturing Costing,
        Material, Labor & Overhead Cost Management,
        Total Manufacturing Cost Solution,
        Odoo Manufacturing Accounting Integration,
        Smart Costing for Manufacturing,
        Work-center Based Cost Calculation,
        Manual and Automated Costing,
        How to manage production costs in Odoo?,
        How does the module handle cost accounting for manufacturing?,
        Can this module generate costing reports in PDF?,
        How does the Work-center Based Calculation work?,
        How to enable journal entries for manufacturing orders in Odoo?,
        How does this module enhance financial tracking for production costs?,
        Cost of Manufacturing Order in odoo,
        Advanced Manufacturing Costing in odoo,
        Material, Labor & Overhead Cost Management in odoo,
        Total Manufacturing Cost Solution in odoo,
        Odoo Manufacturing Accounting Integration in odoo,
        Smart Costing for Manufacturing in odoo,
        Work-center Based Cost Calculation in odoo,
        Manual and Automated Costing in odoo,
        """,

    "license": "OPL-1",
    "version": "18.0.0.1",
    "summary": """
        The MRP Process Costing module is designed to streamline the calculation of production costs by
         providing a comprehensive breakdown of Material, Labor, and Overhead costs. Users can choose between
          two costing methods: Manual or Work-center Based Calculation. In the manual mode, users input the costs
           for materials, labor, and overhead directly, ensuring full control over the values. Alternatively,
            the work-center-based option automatically calculates costs by leveraging pre-configured rates and 
            parameters in the work centers, such as labor rates, and overhead allocations.

       The MRP Process Costing module not only calculates production costs but also integrates
        seamlessly with Odoo's Accounting module to provide robust financial tracking.
         If the accounting feature is enabled, the module automatically generates journal
          entries for each manufacturing order, ensuring that the calculated costs are reflected in
           the selected accounts. 

        Cost of Manufacturing Order,
        Advanced Manufacturing Costing,
        Material, Labor & Overhead Cost Management,
        Total Manufacturing Cost Solution,
        Odoo Manufacturing Accounting Integration,
        Smart Costing for Manufacturing,
        Work-center Based Cost Calculation,
        Manual and Automated Costing,
        How to manage production costs in Odoo?,
        How does the module handle cost accounting for manufacturing?,
        Can this module generate costing reports in PDF?,
        How does the Work-center Based Calculation work?,
        How to enable journal entries for manufacturing orders in Odoo?,
        How does this module enhance financial tracking for production costs?,
        Cost of Manufacturing Order in odoo,
        Advanced Manufacturing Costing in odoo,
        Material, Labor & Overhead Cost Management in odoo,
        Total Manufacturing Cost Solution in odoo,
        Odoo Manufacturing Accounting Integration in odoo,
        Smart Costing for Manufacturing in odoo,
        Work-center Based Cost Calculation in odoo,
        Manual and Automated Costing in odoo,
    """,
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/mrp_bom_form_view.xml',
        'views/mrp_production_form_view.xml',
        'views/mrp_workcenter_view.xml',
        'reports/templates.xml',
        'reports/bom_costing_report.xml',
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": [
        "static/description/banner.png",
    ],
    "price": 130,
    "currency": "USD",
}
