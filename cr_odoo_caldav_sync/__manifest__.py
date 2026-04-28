# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Odoo CalDAV Connector | Odoo CalDAV Calendar Integration | Smart CalDAV Sync for Odoo | Odoo CalDAV Event Integration",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_odoo_caldav_sync&version=19.0",
    "category": "Extra Tools",
    "summary": """
    Odoo CalDAV Calendar Synchronization enables seamless two-way syncing between Odoo and popular CalDAV services like Radicale, Google Calendar, iCloud, Nextcloud, and Zoho. It automatically keeps your calendar events updated across all platforms, ensuring consistency without any manual effort.

    The module supports recurring events, reminders, and privacy settings, along with secure per-user account configuration. With efficient change detection, only updated data is synced, providing a fast, reliable, and user-friendly calendar integration experience within Odoo.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Odoo CalDAV Connector – Professional iCloud, Synology & Nextcloud Sync</h1>
    <p>The Odoo CalDAV Connector provides a robust, bidirectional bridge between Odoo Calendar and external CalDAV servers. It enables businesses to centralize their scheduling, automate event synchronization, and ensure that every meeting is reflected accurately across all personal and professional devices.</p>
    
    <h2>Key Features</h2>
    <ul>
        <li>Full Bidirectional Sync between Odoo and CalDAV servers</li>
        <li>Support for iCloud, Google Calendar, Nextcloud, Zoho, and Radicale</li>
        <li>Sync complex Recurring Events (RRULE) and Allday events</li>
        <li>Manage Reminders and Alarms (VALARM) across platforms</li>
        <li>Respect Privacy settings (Public, Private, Confidential)</li>
        <li>Attendee synchronization with auto-contact creation</li>
        <li>Per-user Account configuration for personalized sync</li>
        <li>Real-time conflict resolution using ETag/CTag logic</li>
        <li>Manual and Automatic (Cron) synchronization options</li>
        <li>Email invitation control for imported events</li>
    </ul>
    
    <h2>Benefits</h2>
    <ul>
        <li>Eliminates manual entry and double-booking errors</li>
        <li>Keeps mobile and desktop calendars in perfect harmony</li>
        <li>Improves team coordination with up-to-date availability</li>
        <li>Ensures privacy and data security across services</li>
        <li>Streamlines meeting management within the Odoo ecosystem</li>
    </ul>
    
    <h2>Why Choose This Odoo CalDAV Integration?</h2>
    <p>This connector is engineered for reliability and performance, handling the technical complexities of the CalDAV protocol so you don't have to. It provides a complete scheduling automation system for businesses that rely on diverse calendar ecosystems, ensuring faster updates, fewer conflicts, and effortless management of your time—all within a single platform.</p>
    
    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_3cx_crm_connector">3CX CRM Connector</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_odoo_brevo_integration">Odoo Brevo Integration</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_basecamp_integration">Odoo Basecamp Integration</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_remove_powered_by">Remove Powered By Odoo</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_power_bi_desktop_connector">Odoo Power BI Desktop Connector</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_tiktok_shop_connector">Odoo TikTok Shop Connector</a></li>
    </ul>
    <p>For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a></p>
    <p>Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
    <p>Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a></p>

    """,
    "depends": ["base", "calendar"],
    "data": [
        "security/ir.model.access.csv",
        "views/groups.xml",
        "data/ir_cron.xml",
        "views/caldav_account_views.xml",
        "views/caldav_sync_log_views.xml",
        "views/res_config_settings_views.xml",
        "views/calendar_views.xml",
        "views/menu.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 179,
    "currency": "USD",
}
