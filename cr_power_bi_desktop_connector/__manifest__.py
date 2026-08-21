# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Power BI Odoo Connector | Odoo to Power BI Integration for Real-Time Dashboards, KPIs & Analytics",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "summary": """
    	Supercharge your reporting by connecting Odoo with Power BI Desktop using this 
    	advanced Odoo Power BI Connector. Seamlessly sync real-time Odoo data—including 
    	Sales, Accounting, Inventory, CRM, HR, and Project records—directly into Power BI 
    	for interactive dashboards and powerful analytics. This module ensures fast, secure, 
    	and automated data extraction from Odoo to Power BI without manual exports.

        Designed for both Odoo Community and Enterprise, it delivers smooth Odoo to Power BI Integration, 
        enabling users to build custom reports, analyze KPIs, and track business performance effortlessly. 
        Perfect for data-driven teams looking for a reliable Odoo Power BI Desktop Connector, 
        Odoo Power BI Dashboard solution, or Odoo Power BI Analytics setup.

        Whether you need a Real-Time Odoo Data in Power BI workflow or an Advanced Power BI Connector for Odoo, 
        this module provides the complete end-to-end Odoo Power BI Integration experience to enhance decision-making 
        and boost productivity.
        """,
    "license": "OPL-1",
    "version": "18.7",
    "description": """
    	<h1>Odoo Power BI Desktop Connector – Real-Time Odoo Data, Reports & Dashboards</h1>
        <p>
            The Odoo Power BI Desktop Connector enables a seamless and secure integration between Odoo and Microsoft Power BI, 
            allowing businesses to sync real-time Odoo data for advanced reporting and analytics. With automated data extraction 
            across Sales, Accounting, Inventory, CRM, HR, Projects, and custom modules, this connector eliminates manual exports 
            and keeps Power BI dashboards always up to date. Perfect for organizations seeking faster decision-making, accurate KPIs, 
            and complete visibility into business performance.
        </p>
        <h2>Key Features</h2>
        <ul>
            <li>Full Odoo to Power BI integration with real-time data sync</li>
            <li>Automated data export for Sales, Accounting, Inventory, CRM, HR & Projects</li>
            <li>Supports Odoo Community & Enterprise editions</li>
            <li>Build custom Power BI dashboards with live Odoo data</li>
            <li>Advanced filtering for models, fields, domains & dynamic queries</li>
            <li>Secure token-based authentication for data access</li>
            <li>Sync unlimited records from Odoo to Power BI Desktop</li>
            <li>Scheduled & on-demand data synchronization</li>
            <li>Track sync logs, performance metrics & error history</li>
            <li>Easy setup with no technical expertise required</li>
        </ul>
        <h2>Benefits</h2>
        <ul>
            <li>Centralizes analytics by bringing all Odoo data into Power BI</li>
            <li>Ensures accurate, real-time dashboards for better decisions</li>
            <li>Eliminates manual CSV exports and repetitive data tasks</li>
            <li>Improves KPI tracking and business performance insights</li>
            <li>Helps teams visualize multi-department data in one place</li>
            <li>Provides scalable performance for growing Odoo databases</li>
        </ul>
        <h2>Why Choose This Odoo Power BI Connector?</h2>
        <p>
            This connector delivers a fast, stable, and highly automated integration between Odoo and Power BI. 
            It empowers businesses to transform raw Odoo data into interactive dashboards, real-time analytics, and 
            actionable insights. Designed for both small and high-volume companies, it provides a reliable and user-friendly 
            solution to build modern BI reporting directly from live Odoo data.
        </p>
        <h2>SEO Keywords</h2>
        <p>
            Odoo Power BI Connector, Odoo to Power BI Integration, Odoo Power BI Desktop Connector, 
            Real-Time Odoo Data Sync, Odoo Power BI Dashboard, Power BI Odoo Reporting, 
            Odoo BI Analytics, Odoo Power BI Real-Time, Advanced Odoo Power BI Integration, 
            Odoo to Power BI Report Connector
        </p>
        <h2>Related Apps</h2>
        <ul>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_tableau_desktop_connector">Tableau Desktop Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/15.0/cr_tableau_desktop_connector_with_sql">Tableau Desktop Connector With SQL</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_tiktok_shop_connector">Tik Tok Shop Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_recurly_connector">Recurly Subscription Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/17.0/cr_smartsheet_connector">Smartsheet Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/19.0/cr_bigquery_connector">Google BigQuery Connector</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/17.0/cr_odoo_to_sheets_connector">Odoo to Google Sheets Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_miro_odoo_integration">Miro Odoo Integration</a></li>
            <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_brevo_integration">Odoo Brevo Integration</a></li>
        </ul>
        <p>For custom Odoo integrations, visit <a href="https://creyox.com">creyox.com</a></p>
        <p>Watch the YouTube demo: <a href="https://www.youtube.com/watch?v=z0FFOSOyJSc">Power BI Odoo Connector</a></p>
        <p>Read our blogs: <a href="https://www.creyox.com/blog/powerbi-desktop-connector-16/power-bi-desktop-connector-a-quick-guide-14">Power BI Odoo Connector</a></p>
        """,
    "depends": [
        "base",
        "web",
        "mail",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/powerbi_config_views.xml",
        "views/powerbi_configuration.xml",
        "views/powerbi_dashboard_views.xml",
        "views/powerbi_dataset_views.xml",
        "views/powerbi_eventhouse_views.xml",
        "views/powerbi_kql_database_views.xml",
        "views/powerbi_report_views.xml",
        "views/powerbi_workspace_views.xml",
        "views/powerbi_pipeline_views.xml",
        "views/powerbi_report_viewer.xml",
        "views/powerbi_dashboard_viewer_views.xml",
        "views/powerbi_pipeline_stages_views.xml",
        "views/logs.xml",
        "views/powerbi_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cr_power_bi_desktop_connector/static/src/js/powerbi_report_viewer.js",
            "cr_power_bi_desktop_connector/static/src/js/powerbi_dashboard_viewer.js",
            "cr_power_bi_desktop_connector/static/src/scss/pipeline_kanban.scss",
            "cr_power_bi_desktop_connector/static/src/scss/powerbi_workspace_kanban.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png", "static/description/thumbnail.png"],
    "price": 510,
    "currency": "USD",
}
