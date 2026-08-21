# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Dynamic Report Studio | Custom Dynamic Report Designer | Custom Report Designer ",
    "category": "Extra Tools",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": 'https://www.creyox.com/helpdesk?module_tech_name=cr_dynamic_report_studio&version=18.0',
    "category": "Extra Tools",
    "version": "18.0.0.0",
    "summary": """
         Dynamic Report Studio is a powerful, visual document design ecosystem for Odoo that completely replaces 
         the tedious process of coding PDF layouts in HTML and QWeb XML. By introducing an interactive, drag and 
         drop workspace, it empowers functional consultants, business analysts, and developers to build stunning, 
         pixel perfect reports, custom invoices, purchase orders, and shipping labels within minutes. The module 
         features a state of the art canvas supporting diverse components such as text blocks, dynamic database 
         field paths, custom image libraries, layout shapes, dynamic data tables, barcodes, and QR codes.

         Additionally, it offers unified design syncing through automated watermark mirroring across multiple pages, 
         strict margin bounding to keep headers and footers neatly formatted, and full dark theme customization. 
         Dynamic Report Studio bridges the gap between raw database records and presentation ready business documents, 
         drastically accelerating report turnaround times and optimizing document customizability across your entire 
         enterprise.
        """,
    "description": """
        <h1>Dynamic Report Studio – Drag & Drop Odoo PDF Report Designer</h1>
        <p>Dynamic Report Studio is a visual Odoo report designer that replaces slow, manual QWeb and XML coding with an easy drag-and-drop canvas. Build custom invoices, purchase orders, shipping labels, and business reports in minutes—no developer required.</p>

        <h2>Key Features</h2>
        <ul>
            <li>Visual drag-and-drop report designer for Odoo</li>
            <li>Insert dynamic database fields directly into any layout</li>
            <li>Real-time Python expression validator with relational field tracing</li>
            <li>Visual margin controls for clean headers and footers</li>
            <li>Native Odoo dark mode theme for comfortable design sessions</li>
            <li>Full typography controls for fonts, sizing, and spacing</li>
            <li>Flexible component library: text, images, shapes, and tables</li>
            <li>Dynamic data tables that pull live Odoo records</li>
            <li>Built-in barcode and QR code generator</li>
            <li>Watermark mirroring and sync across multiple pages</li>
            <li>Page break component for multi-page documents</li>
            <li>Custom image library and print history log</li>
        </ul>

        <h2>Benefits</h2>
        <ul>
            <li>Cuts report design time from hours to minutes</li>
            <li>Removes the need for QWeb or XML coding knowledge</li>
            <li>Gives business users full control over document branding</li>
            <li>Reduces developer dependency for report customization</li>
            <li>Ensures consistent, professional documents across the company</li>
        </ul>

        <h2>Why Choose Dynamic Report Studio?</h2>
        <p>Dynamic Report Studio turns Odoo report design into a simple visual process. Functional consultants, analysts, and developers can all build polished invoices, orders, and labels without touching code, making document customization faster, easier, and more accessible for the whole team.</p>

        <h2>Related Keywords</h2>
        <ul>
            <li>Odoo Inventory Module</li>
        <li>Odoo Stripe Integration</li>
        <li>Odoo Accounting Module</li>
        <li>Odoo 3CX Integration</li>
        <li>Odoo DocuSign Integration</li>
        <li>Odoo Invoice Customization</li>
        <li>Odoo Manufacturing Module</li>
        <li>Odoo POS Module</li>
        <li>Odoo Power BI Connector</li>
        <li>Odoo TikTok Integration</li>
        <li>Odoo Website Module</li>
        <li>Odoo eCommerce Module</li>
        <li>Odoo Bank Statement Import</li>
        <li>Odoo Marketing Automation Module</li>
        <li>Odoo POS Kitchen Printer</li>
        <li>Odoo POS Network Printer</li>
        <li>Odoo POS Restaurant Module</li>
        <li>Odoo POS USB Printer</li>
        <li>Odoo Power BI Integration</li>
        <li>Odoo TikTok Shop Connector</li>
        <li>Best Odoo Apps by Creyox Technologies</li>
        <li>Creyox Odoo App Store</li>
        <li>Creyox Odoo Custom Modules</li>
        <li>Creyox Odoo Development Company</li>
        <li>Creyox Odoo Solutions</li>
        <li>Creyox Technologies ERP Apps</li>
        <li>Creyox Technologies Odoo Modules</li>
        <li>Creyox Technologies Odoo Partner</li>
        <li>Odoo Actual Costing Method</li>
        <li>Odoo Email Marketing Integration</li>
        <li>Odoo Modules by Creyox</li>
        <li>Odoo Payment Integration Module</li>
        <li>Odoo eCommerce Customization</li>
        <li>Odoo HR Module</li>
        <li>Odoo DocuSign Integration</li>
        <li>Odoo Electronic Signature</li>
        <li>Odoo Employee Management</li>
        <li>Odoo Payroll Module</li>
        <li>Odoo Document Management Module</li>
        <li>Odoo Leave Management</li>
        </ul>

        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_bpmn_workflow_designer">Odoo BPMN Workflow Designer</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_all_in_one_direct_print">All in One Direct Print</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/16.0/cr_manufacturing_lot_report">Manufacturing Order Barcode Report</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/17.0/cr_invoice_ocr">Invoice OCR</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/16.0/cr_export_image_excel">Export Barcode & QR Image in Excel</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/15.0/cr_hide_product_code">DailyBook PDF/XLS Report</a></li>
        </ul>
        <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
        <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
        <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    "license": "OPL-1",
    "depends": [
        'base',
        'web',
        'mail',
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/report_designer_template_views.xml',
        'views/report_designer_resource_views.xml',
        'views/report_designer_font_views.xml',
        'views/report_designer_print_log_views.xml',
        'views/report_designer_menus.xml',
    ],
    "assets": {
        'web.assets_backend': [
            'cr_dynamic_report_studio/static/src/designer/report_designer_app.js',
            'cr_dynamic_report_studio/static/src/designer/report_designer_app.scss',
            'cr_dynamic_report_studio/static/src/designer/report_designer_app.xml',
        ],
        'web.assets_web_dark': [
            'cr_dynamic_report_studio/static/src/designer/report_designer_app.dark.scss',
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png", "static/description/thumbnail.png"],
    "price": 179,
    "currency": "USD",
}
