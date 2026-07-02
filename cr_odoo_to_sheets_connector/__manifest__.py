# -*- coding: utf-8 -*-
# Part of Creyox Technologies

{
    "name": "Odoo to Google Sheets Connector | Two-Way Data Sync & Automated Reporting",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_odoo_to_sheets_connector&version=18.0",
    "category": "Extra Tools",
    "summary": """
    	The Odoo to Google Sheets Connector seamlessly integrates Odoo with Google Sheets, 
    	enabling businesses to streamline data management, automate reporting, and enhance 
    	team collaboration. With this connector, users can push essential Odoo records into 
    	Google Sheets for analysis, reporting, or visualization, while updates in Sheets 
    	automatically sync back to Odoo. It supports two-way synchronization, real-time data 
    	updates, and dynamic table selection, eliminating repetitive manual data entry. 
    	
    	The connector also includes robust logging, tracking all sync actions and errors for 
    	transparency and audit trails. Configurable automatic or manual sync schedules save time 
    	and improve operational efficiency. Teams can transform and analyze data effortlessly, 
    	monitor sync performance, and make informed business decisions faster. Ideal for finance, 
    	sales, inventory, or project teams, this tool simplifies reporting workflows, ensures accurate 
    	records, and enhances productivity by combining the flexibility of Google Sheets with 
    	the power of Odoo’s ERP system.
        """,
    "license": "OPL-1",
    "version": "18.0.0.4",
    "description": """
    	<h1>Odoo to Google Sheets Connector – Two-Way Data Sync & Automated Reporting</h1>
        <p>
            The Odoo to Google Sheets Connector seamlessly integrates Odoo with Google Sheets, enabling businesses to streamline data management, automate reporting, and enhance team collaboration. Users can push essential Odoo records into Google Sheets for analysis or reporting, while updates in Sheets automatically sync back to Odoo, ensuring accurate and up-to-date records.
        </p>
        
        <h2>Key Features</h2>
        <ul>
            <li>Real-time two-way data synchronization between Odoo and Google Sheets</li>
            <li>Automatic or manual sync for selected tables</li>
            <li>Dynamic table selection and mapping of Odoo records</li>
            <li>Data transformation options for custom workflows</li>
            <li>User-friendly setup and configuration</li>
            <li>Smart data availability check to prevent errors</li>
            <li>Detailed logs of all sync actions inside Odoo</li>
            <li>Notifications for successful updates or errors</li>
            <li>Powerful analytics for better decision-making</li>
            <li>Continuous synchronization to keep data up-to-date</li>
            <li>Set up automatic import refresh and export refresh for multiple tables, each with its own hourly interval</li>
            <li>Refresh selected sheets in real time to immediately fetch data from Odoo into Google Sheets</li>
            <li>Relational fields display the record name (_rec_name) if defined, otherwise the related record’s name field</li>
            <li>Search and select specific fields to import or export data from Odoo into Google Sheets</li>
        </ul>
        
        <h2>Benefits</h2>
        <ul>
            <li>Eliminates repetitive manual data entry</li>
            <li>Enables faster reporting and analysis</li>
            <li>Improves team collaboration and productivity</li>
            <li>Ensures accurate and up-to-date records across platforms</li>
            <li>Provides transparency and audit trail for all data syncs</li>
        </ul>
        
        <h2>Why Choose This Odoo–Google Sheets Integration?</h2>
        <p>
            This connector empowers businesses to streamline data management and reporting without manual intervention. With real-time synchronization, robust logging, and easy configuration, teams can focus on analysis and decision-making while ensuring all Odoo records remain consistent with Google Sheets.
        </p>
        
        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_mydsv_odoo">MYDSV Shipping Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_bigquery_connector">BigQuery Odoo Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_hcaptcha">Odoo hCaptcha Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_smartsheet_connector">Odoo Smartsheet Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_recurly_connector">Recurly Odoo Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_3cx_crm_connector">Odoo 3CX CRM Connector</a></li>
        </ul>
        
        <p>
            For custom Odoo integrations and ERP enhancements, visit <a href="https://creyox.com">creyox.com</a>
        </p>
        <p>
            Watch the YouTube demo, visit <a href="https://www.youtube.com/watch?v=9gQvJXItL00">Odoo to Google Sheets Integration</a>
        </p>
        <p>
            Read our blog post, visit <a href="https://creyox.com/blog/odoo-meets-google-sheets-easy-data-export-34/odoo-meets-google-sheets-easy-data-export-32">Odoo to Google Sheets Integration</a>
        </p>
        """,
    "depends": ["base", "web", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/sheet_configuration.xml",
        "views/logs.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png"],
    "price": 345,
    "currency": "USD",
}
