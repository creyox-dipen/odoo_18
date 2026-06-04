# -*- coding: utf-8 -*-
# Part of Creyox Technologies
{
    "name": "Odoo Draw.io Integration | Draw.io Diagram Editor for Odoo | Odoo Flowchart & Diagram Builder | Interactive Odoo Diagrams with Draw.io",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_draw_io&version=18.0",
    "category": "Extra Tools",
    "summary": """
    Seamlessly integrate the powerful Draw.io (diagrams.net) editor directly into your Odoo environment to create, edit, and embed professional flowcharts and diagrams. Users can easily launch the editor in any HTML field using the intuitive '/drawio' command, providing a streamlined workflow for technical documentation and process mapping without leaving the platform.

    This module ensures full persistence of your drawings, allowing diagrams to be re-edited and updated directly within Odoo records. By bridging the gap between Odoo's native HTML editor and professional diagramming tools, it empowers teams to visualize complex data and processes with a native-feel integration that supports a wide range of flowcharting and diagramming needs.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Odoo Draw.io Integration – Professional Diagram & Flowchart Editor</h1>

    <p>The Odoo Draw.io Integration seamlessly connects the powerful Draw.io (diagrams.net) editor with your Odoo environment, enabling teams to build professional diagrams directly within Odoo fields. Using the simple "/drawio" command, users can launch a full-featured editor to create flowcharts, process maps, and technical drawings without ever leaving the platform.</p>

    <h2>Key Features of Odoo Draw.io Integration</h2>
    <ul>
        <li>Full integration with Odoo’s native HTML editor (Powerbox)</li>
        <li>Launch the editor instantly using the intuitive /drawio command</li>
        <li>Create and edit professional flowcharts and technical diagrams</li>
        <li>Seamlessly embed diagrams directly into any Odoo record</li>
        <li>Full persistence ensures all drawings are saved and re-editable</li>
        <li>Support for a wide range of diagrams.net shapes and tools</li>
        <li>Native-feel user interface for a smooth diagramming experience</li>
        <li>Works across all standard Odoo HTML and text fields</li>
    </ul>

    <h2>Benefits of using Odoo Draw.io Integration</h2>
    <ul>
        <li>Streamlines visual documentation and process mapping</li>
        <li>Improves team collaboration with integrated visual aids</li>
        <li>Eliminates the need for external diagramming software</li>
        <li>Enhances productivity by keeping workflows within Odoo</li>
        <li>Boosts data clarity with high-quality visual representations</li>
    </ul>

    <h2>Why Choose This Odoo Draw.io Integration?</h2>
    <p>This <strong>Odoo Draw.io Integration</strong> provides a complete visual communication system for businesses looking to centralize their documentation. It ensures accurate process tracking, faster diagram creation, and effortless management of technical drawings—all within a single, unified platform. By bridging the gap between Odoo and professional diagramming tools, it empowers your team to visualize complex data with ease.</p>

    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_bpmn_workflow_designer">Odoo BPMN Workflow Designer</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_picking_move_from_invoice">Stock Picking/Move From invoice</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_power_bi_desktop_connector">Power BI Odoo Connector</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_basecamp_integration">Basecamp Integration</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_3cx_crm_connector">Odoo 3CX CRM Connector</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_pos_network_printer">Odoo POS Network Printer</a></li>
    </ul>

    <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
    <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
    <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    "depends": ["web", "html_editor"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "cr_draw_io/static/src/drawio_dialog.xml",
            "cr_draw_io/static/src/drawio_dialog.js",
            "cr_draw_io/static/src/drawio_plugin.js",
            "cr_draw_io/static/src/drawio.css",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 250,
    "currency": "USD",
}
