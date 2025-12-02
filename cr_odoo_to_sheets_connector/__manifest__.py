# -*- coding: utf-8 -*-
# Part of Creyox Technologies

{
    "name": "Odoo to Google Sheets Integration | Odoo Google Sheets Connector | Odoo Google Sheets Sync | GoogleSheets Odoo Connector",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "summary": """
    	The Odoo to Google Sheets Connector bridges Odoo and Google Sheets, enabling smooth data flow between 
    	the two platforms. With this tool, users can effortlessly push essential Odoo into Google Sheets for
    	quick analysis and team collaboration. The connector also allows updates in Google Sheets to sync
    	back to Odoo, ensuring all records are kept accurate and up-to-date.

        With this connector, Odoo records are mapped to Google Sheets. Users can choose to sync data 
        automatically at intervals or manually when needed, eliminating repetitive data entry and 
        speeding up reporting tasks. This connector empowers teams to analyze, report, and share data
        efficiently, providing better insights for decision-making and simplifying business operations.
        
        Logs are also generated in Odoo to track all sync actions and monitor the performance of data 
        transfers. These logs help users keep track of the connector’s operations, including any successful
        updates or errors, providing transparency and aiding in troubleshooting. The logging system ensures 
        that all records and sync activities are logged for future reference, enabling better audit trails
        and accountability.
        
        Google Sheets Sync for Odoo,
        Odoo Google Sheets Connector,
        Odoo Sheets Flow,
        Google Sheets Integration for Odoo,
        How to Set Up Google Sheets Data Export in Odoo,
        How to Integrate Odoo with Google Sheets for Data Syncing,
        Odoo Google Sheets Connector for Seamless Data Export,
        How to Import Data from Google Sheets to Odoo,
        How to Sync Records from Odoo to Google Sheets Automatically,
        Real-Time Data Integration Between Odoo and Google Sheets,
        How to Configure Google Sheets Export Settings in Odoo,
        Best Practices for Exporting Odoo Data to Google Sheets,
        How to Handle Data Schema Mismatches Between Odoo and Google Sheets,
        How to Automate Data Exports from Odoo to Google Sheets,
        Odoo Google Sheets Data Export Tool Setup Guide,
        How to Import Specific Tabs from Google Sheets into Odoo,
        How to Monitor Odoo-Google Sheets Data Sync Progress,
        Odoo Google Sheets Connector Installation Guide,
        What are the Best Tools for Odoo-Google Sheets Data Integration?,
        How to Schedule Odoo Data Exports to Google Sheets,
        How to Set Up Google Sheets Job Configurations in Odoo,
        Best Google Sheets Solution for Odoo,
        Odoo Google Sheets Integration Tutorial,
        Benefits of Using Google Sheets with Odoo,
        Seamless Google Sheets Integration with Odoo,
        Google Sheets Workflow Sync for Odoo,
        Odoo Real-Time Google Sheets Connector,
        Google Sheets Sync Tool for Odoo,
        Odoo Google Sheets Integration Solutions,
        Odoo Sheets Sync,
        Google Sheets Integration Hub for Odoo,
        Google Sheets-Odoo Workflow Solutions,
        Google Sheets Integration in Odoo,
        Google Sheets Integration Solutions in Odoo,
        """,
    "license": "OPL-1",
    "version": "18.1",
    "description": """
    	The Odoo to Google Sheets Connector bridges Odoo and Google Sheets, enabling smooth data flow between 
    	the two platforms. With this tool, users can effortlessly push essential Odoo into Google Sheets for
    	quick analysis and team collaboration. The connector also allows updates in Google Sheets to sync
    	back to Odoo, ensuring all records are kept accurate and up-to-date.

        With this connector, Odoo records are mapped to Google Sheets. Users can choose to sync data 
        automatically at intervals or manually when needed, eliminating repetitive data entry and 
        speeding up reporting tasks. This connector empowers teams to analyze, report, and share data
        efficiently, providing better insights for decision-making and simplifying business operations.
        
        Logs are also generated in Odoo to track all sync actions and monitor the performance of data 
        transfers. These logs help users keep track of the connector’s operations, including any successful
        updates or errors, providing transparency and aiding in troubleshooting. The logging system ensures 
        that all records and sync activities are logged for future reference, enabling better audit trails
        and accountability.
        
        Google Sheets Sync for Odoo,
        Odoo Google Sheets Connector,
        Odoo Sheets Flow,
        Google Sheets Integration for Odoo,
        How to Set Up Google Sheets Data Export in Odoo,
        How to Integrate Odoo with Google Sheets for Data Syncing,
        Odoo Google Sheets Connector for Seamless Data Export,
        How to Import Data from Google Sheets to Odoo,
        How to Sync Records from Odoo to Google Sheets Automatically,
        Real-Time Data Integration Between Odoo and Google Sheets,
        How to Configure Google Sheets Export Settings in Odoo,
        Best Practices for Exporting Odoo Data to Google Sheets,
        How to Handle Data Schema Mismatches Between Odoo and Google Sheets,
        How to Automate Data Exports from Odoo to Google Sheets,
        Odoo Google Sheets Data Export Tool Setup Guide,
        How to Import Specific Tabs from Google Sheets into Odoo,
        How to Monitor Odoo-Google Sheets Data Sync Progress,
        Odoo Google Sheets Connector Installation Guide,
        What are the Best Tools for Odoo-Google Sheets Data Integration?,
        How to Schedule Odoo Data Exports to Google Sheets,
        How to Set Up Google Sheets Job Configurations in Odoo,
        Best Google Sheets Solution for Odoo,
        Odoo Google Sheets Integration Tutorial,
        Benefits of Using Google Sheets with Odoo,
        Seamless Google Sheets Integration with Odoo,
        Google Sheets Workflow Sync for Odoo,
        Odoo Real-Time Google Sheets Connector,
        Google Sheets Sync Tool for Odoo,
        Odoo Google Sheets Integration Solutions,
        Odoo Sheets Sync,
        Google Sheets Integration Hub for Odoo,
        Google Sheets-Odoo Workflow Solutions,
        Google Sheets Integration in Odoo,
        Google Sheets Integration Solutions in Odoo,
        """,
    "depends": ["base", 'web','mail',],
    'data': [
        'security/ir.model.access.csv',
        'views/sheet_configuration.xml',
        'views/logs.xml',
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png"],
    "price": "345",
    "currency": "USD",
}
