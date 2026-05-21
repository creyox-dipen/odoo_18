# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Smart ZKTeco Attendance System | ZKTeco Biometric Integration | Live Attendance Tracker for ZKTeco | ZKTeco ADMS Sync",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "https://www.creyox.com/helpdesk",
    "live_test_url": "https://www.creyox.com/helpdesk?module_tech_name=cr_zkteco_biometric_integration&version=18.0",
    "category": "Extra Tools",
    "summary": """
    Experience seamless ZKTeco biometric integration with Odoo through our advanced ADMS live synchronization system.
    This module automates the fetching of attendance logs in real-time, ensuring employee movements are captured accurately.
    It supports effortless device management, allowing User to configure settings and monitor connectivity from Odoo.
    Handle device commands and synchronize employee data effortlessly to maintain a consistent attendance record system.

    The module features a dynamic dashboard for visual analytics and a suite of reports for daily summaries and absence tracking.
    Efficiently manage your staff with remote user enrollment and seamless user transfers between various biometric machines.
    Integrated attendance calculation logic precisely tracks late arrivals and early departures to ensure payroll accuracy.
    Robust automation through cron jobs ensures your biometric data is always up-to-date with minimal administrative effort.
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    "description": """
    <h1>Smart ZKTeco Attendance System – Odoo Biometric & ADMS Live Sync Integration</h1>
    <p>
        The Smart ZKTeco Attendance System seamlessly integrates ZKTeco biometric devices with Odoo, providing a live ADMS synchronization for real-time attendance tracking. By automating the fetching of attendance logs, this system eliminates manual data entry, reduces errors, and ensures your HR records are always accurate and up-to-date.
    </p>
    
    <h2>Key Features</h2>
    <ul>
        <li>Real-time ADMS live synchronization for ZKTeco devices</li>
        <li>Automated fetching and processing of attendance logs</li>
        <li>Dynamic dashboard for monitoring devices and attendance data</li>
        <li>Remote employee enrollment and user transfer between machines</li>
        <li>Detailed daily summary, absence, and attendance reports</li>
        <li>Integrated logic for calculating late arrivals and early departures</li>
        <li>Automatic synchronization through scheduled Odoo cron jobs</li>
        <li>Complete compatibility with Odoo HR Attendance module</li>
        <li>Monitor device connectivity and status directly from Odoo</li>
        <li>Secure storage of biometric data as Odoo attachments</li>
    </ul>
    
    <h2>Benefits</h2>
    <ul>
        <li>Streamlines attendance tracking with automated biometric sync</li>
        <li>Improves payroll accuracy with precise time-log calculations</li>
        <li>Eliminates manual entry for daily attendance logs</li>
        <li>Enhances staff productivity by reducing administrative overhead</li>
        <li>Boosts workforce management with real-time visibility into employee movements</li>
    </ul>
    
    <h2>Why Choose This Smart ZKTeco Attendance System?</h2>
    <p>
        This integration provides a complete biometric automation system for businesses using ZKTeco devices and Odoo. It ensures accurate log tracking, faster attendance processing, reliable reporting, and effortless management of devices and employees—all within a single, secure platform.
    </p>

    <h2>Related Apps</h2>
    <ul>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_restrict_mobile_attendance">Advanced Attendance Device Restriction Pro</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_loan_management">Loan Managment System</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_employee_performance_evaluation">Advanced Employee Performance Evaluation</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_fleet_fuel_monitoring">Advanced Fleet Fuel Management Pro</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_okta_login">Okta Single Sign-On (SSO) for Odoo</a></li>
        <li><a href="https://apps.odoo.com/apps/modules/18.0/cr_barcode_multi_user">Advanced Barcode Multi User Pro</a></li>
    </ul>

    <p>
        For custom Odoo integrations and CRM enhancements, visit <a href="https://creyox.com">Creyox Technologies</a>
    </p>
    <p>
        Watch the youtube video, visit <a href="https://www.youtube.com/@CreyoxTechnologies">Creyox Technologies YouTube Videos</a></p>
    <p>
        Read our blog post, visit <a href="https://www.creyox.com/blog">Creyox Technologies Blogs</a>
    </p>
    """,
    "depends": ["base", "mail", "hr_attendance"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/biometric_device_config.xml",
        "views/biometric_attendance_log.xml",
        "views/hr_employee.xml",
        "views/biometric_dashboard_view.xml",
        "views/menu.xml",
        "views/res_users_view.xml",
        "wizard/biometric_enroll_wizard_view.xml",
        "wizard/biometric_user_transfer_wizard_view.xml",
        "wizard/biometric_attendance_report_wizard_view.xml",
        "wizard/calculate_attendance_wizard_view.xml",
        "wizard/daily_summary_report_wizard_view.xml",
        "wizard/absence_report_wizard_view.xml",
        "wizard/daily_attendance_report_wizard_view.xml",
        "report/attendance_reports.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cr_zkteco_biometric_integration/static/src/xml/biometric_dashboard.xml",
            "cr_zkteco_biometric_integration/static/src/scss/biometric_dashboard.scss",
            "cr_zkteco_biometric_integration/static/src/js/biometric_dashboard.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 175,
    "currency": "USD",
}
