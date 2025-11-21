# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'Daily Attendance Email',
    'author': 'Creyox Technologies',
    "website": "https://www.creyox.com",
    'support': 'support@creyox.com',
    'category': 'Human Resources',
    'summary': """
    Daily Attendance Email
    """,
    "license": "OPL-1",
    "version": "18.0.0.0",
    'description': """
    Daily Attendance Email
    """,
    'depends': ['base', 'hr_attendance', 'mail'],
    'data': [
        'views/email_cron.xml',
        'views/user_group.xml'
    ],
    # 'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    "price": 100,
    'currency': 'USD'
}
