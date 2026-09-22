# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Smart Advanced Search Engine | Recent Search History | Advanced Search & Filters | List View Column Filters | Quick Saved Custom Filters",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_advance_search_more&version=18.0",
    "category": "Extra Tools",
    "summary": """
    Smart Advanced Search Engine enhances Odoo ERP search capabilities by introducing Search Bar OR/AND/NOT search modes, List View Column Filters, Recent Search History, and Quick Saved Custom Filters.

    Easily search multiple records simultaneously, filter data per column directly in list view headers, highlight search keywords across List & Kanban cards, access recent queries via 1-click history, and save custom filters for instant reuse.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Smart Advanced Search Engine for Odoo 19</h1>

    <p>This module expands Odoo search bar functionality by introducing Default, OR, AND, and NOT search modes, Recent Search History & Saved Custom Filters dropdown, and Many2one relational field multi-word search.</p>

    <h2>Hot Features</h2>
    <ul>
        <li>Provide 4 Search Options on Search Bar: Default, OR, AND, and NOT</li>
        <li>List View Column Header Inline Search & Filter Row (text, date range, selection dropdowns)</li>
        <li>Search Keyword Highlighting across List View rows & Kanban Cards</li>
        <li>Recent Search History Dropdown with 1-click re-runs per model</li>
        <li>Quick Saved Custom Filters (save up to 15 custom filters per model for 1-click reuse)</li>
        <li>Saved Custom Group By Dropdown with 1-click re-runs and inline label renaming</li>
        <li>1-Click Clear All Column Filters button to reset all search fields instantly</li>
        <li>Multi-word search on Many2one dropdown relational fields</li>
    </ul>

    <h2>Key Features</h2>
    <ul>
        <li>Match ANY word using OR mode search logic</li>
        <li>Match ALL words using AND mode search logic</li>
        <li>Exclude unwanted records using NOT mode search logic</li>
        <li>Interactive inline column filtering directly beneath list view headers</li>
        <li>Visual search keyword highlighting inside list rows and kanban cards</li>
        <li>1-click access to recent search queries via Search History clock icon</li>
        <li>Save custom domain filters and group-by settings for 1-click reuse</li>
        <li>Seamless integration with standard Odoo Control Panel</li>
    </ul>

    <h2>Benefits</h2>
    <ul>
        <li>Saves time when searching complex or out-of-order terms</li>
        <li>Re-run frequent search queries with 1 click using Search History</li>
        <li>Boosts user productivity across inventory, sales, purchase, and accounting</li>
        <li>Reduces manual domain filtering effort</li>
        <li>Increases search accuracy across large datasets</li>
    </ul>

    <h2>Why Choose This Module?</h2>
    <p>This module provides intuitive search flexibility without complex domain building, making finding records fast and accurate across your entire Odoo ERP.</p>

    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_smart_filters">Dynamic Customizable Filter & Group By</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_advanced_website_searchbar">Advanced Searchbar</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_pos_search_product_custom">Odoo POS Vendor Product Search</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_column_order_in_list">List View Manager</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_searchpanel_resize">Odoo Search Panel Resize</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_dynamic_report_studio">Dynamic Report Studio</a></li>
    </ul>

    <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
    <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
    <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>
    """,
    "depends": ["base", "web"],
    "data": [],
    "images": ["static/description/banner.png"],
    "assets": {
        "web.assets_backend": [
            "cr_advance_search_more/static/src/css/search_mode.css",
            "cr_advance_search_more/static/src/xml/search_bar.xml",
            "cr_advance_search_more/static/src/js/search_bar_patch.js",
            "cr_advance_search_more/static/src/js/search_model_patch.js",
            "cr_advance_search_more/static/src/js/list_renderer_patch.js",
            "cr_advance_search_more/static/src/js/kanban_renderer_patch.js",
        ],
    },
    "installable": True,
    "application": True,
    "price": 179,
    "currency": "USD",
}
