# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    "name": "BigQuery Odoo Integration | Odoo BigQuery Integration | Odoo BigQuery Connector | BigQueryOdoo Connector",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "summary": """
    	The BigQuery Odoo Connector streamlines data management by enabling seamless data synchronization
    	between Odoo and Google BigQuery. This integration allows businesses to export data from Odoo, 
    	such as sales records, customer information, and inventory details, directly into BigQuery for
    	advanced analytics and reporting. Similarly, data from BigQuery can be imported back into Odoo,
    	keeping critical business information up-to-date.
        
        With this connector, Odoo records are mapped to BigQuery tables. real-time syncing options are available 
        for live data requirements. Each data export and import operation is logged within BigQuery, providing a 
        detailed history and status of data transfers. By  reducing manual data handling, and centralizing analytics
        within BigQuery, this connector empowers teams to make data-driven decisions, improve operational visibility,
        and streamline reporting, ultimately enhancing business efficiency.
        
        BigQuery Sync for Odoo,
        Odoo BigQuery Connector,
        Odoo BigQuery Flow,
        BigQuery Integration for Odoo,
        How to set up BigQuery data export in Odoo,
        How to integrate Odoo with Google BigQuery for data syncing,
        Odoo BigQuery Connector for seamless data export,
        How to import data from BigQuery to Odoo,
        How to sync records from Odoo to BigQuery automatically,
        Real-time data integration between Odoo and BigQuery,
        How to configure BigQuery export settings in Odoo,
        Best practices for exporting Odoo data to BigQuery,
        How to handle data schema mismatches between Odoo and BigQuery,
        How to automate data exports from Odoo to BigQuery,
        Odoo BigQuery data export tool setup guide,
        How to import specific tables from BigQuery into Odoo,
        How to monitor Odoo-BigQuery data sync progress,
        Odoo BigQuery Connector installation guide,
        What are the best tools for Odoo-BigQuery data integration?,
        How to schedule Odoo data exports to BigQuery,
        How to set up BigQuery job configurations in Odoo,
        Best BigQuery solution for Odoo,
        Odoo BigQuery integration tutorial,
        Benefits of using BigQuery with Odoo,
        Seamless BigQuery Integration with Odoo,
        BigQuery Workflow Sync for Odoo,
        Odoo Real-Time BigQuery Connector,
        BigQuery Sync Tool for Odoo,
        Odoo BigQuery Integration Solutions,
        Odoo BigQuery Sync,
        BigQuery Integration Hub for Odoo,
        BigQuery-Odoo Workflow Solutions,
        BigQuery Integration in odoo,
	    BigQuery Integration Solutions in odoo,
        """,
    "license": "OPL-1",
    "external_dependencies": {"python": ["google-cloud-bigquery", "google-auth"]},
    "version": "18.0.0.3",
    "description": """
    	 The BigQuery Odoo Connector streamlines data management by enabling seamless data synchronization
    	between Odoo and Google BigQuery. This integration allows businesses to export data from Odoo, 
    	such as sales records, customer information, and inventory details, directly into BigQuery for
    	advanced analytics and reporting. Similarly, data from BigQuery can be imported back into Odoo,
    	keeping critical business information up-to-date.
        
        With this connector, Odoo records are mapped to BigQuery tables. real-time syncing options are available 
        for live data requirements. Each data export and import operation is logged within BigQuery, providing a 
        detailed history and status of data transfers. By  reducing manual data handling, and centralizing analytics
        within BigQuery, this connector empowers teams to make data-driven decisions, improve operational visibility,
        and streamline reporting, ultimately enhancing business efficiency.
        
        BigQuery Sync for Odoo,
        Odoo BigQuery Connector,
        Odoo BigQuery Flow,
        BigQuery Integration for Odoo,
        How to set up BigQuery data export in Odoo,
        How to integrate Odoo with Google BigQuery for data syncing,
        Odoo BigQuery Connector for seamless data export,
        How to import data from BigQuery to Odoo,
        How to sync records from Odoo to BigQuery automatically,
        Real-time data integration between Odoo and BigQuery,
        How to configure BigQuery export settings in Odoo,
        Best practices for exporting Odoo data to BigQuery,
        How to handle data schema mismatches between Odoo and BigQuery,
        How to automate data exports from Odoo to BigQuery,
        Odoo BigQuery data export tool setup guide,
        How to import specific tables from BigQuery into Odoo,
        How to monitor Odoo-BigQuery data sync progress,
        Odoo BigQuery Connector installation guide,
        What are the best tools for Odoo-BigQuery data integration?,
        How to schedule Odoo data exports to BigQuery,
        How to set up BigQuery job configurations in Odoo,
        Best BigQuery solution for Odoo,
        Odoo BigQuery integration tutorial,
        Benefits of using BigQuery with Odoo,
        Seamless BigQuery Integration with Odoo,
        BigQuery Workflow Sync for Odoo,
        Odoo Real-Time BigQuery Connector,
        BigQuery Sync Tool for Odoo,
        Odoo BigQuery Integration Solutions,
        Odoo BigQuery Sync,
        BigQuery Integration Hub for Odoo,
        BigQuery-Odoo Workflow Solutions,
        BigQuery Integration in odoo,
	    BigQuery Integration Solutions in odoo,
        """,
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/bigquery_config_views.xml",
        "views/bigquery_export_views.xml",
        "views/bigquery_scheduler_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "images": ["static/description/banner.png"],
    "price": 425,
    "currency": "USD",
}
