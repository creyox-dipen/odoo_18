# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class CalDAVEventMap(models.Model):
    """Maps between Odoo calendar events and their CalDAV counterparts.

    This model acts as a junction table that tracks the relationship between a
    ``calendar.event`` record and its corresponding resource on a CalDAV server.
    It stores the CalDAV UID, the resource href, and the last-known ETag so the
    sync service can detect changes efficiently without fetching every event.
    """

    _name = 'caldav.event.map'
    _description = 'CalDAV ↔ Odoo Event Mapping'
    _order = 'account_id, caldav_uid'

    account_id = fields.Many2one(
        'caldav.account',
        string='CalDAV Account',
        required=True,
        ondelete='cascade',
        index=True,
    )
    event_id = fields.Many2one(
        'calendar.event',
        string='Odoo Event',
        ondelete='cascade',
        index=True,
        help='The Odoo calendar event linked to this CalDAV resource.',
    )
    caldav_uid = fields.Char(
        string='CalDAV UID',
        required=True,
        index=True,
        help='The globally-unique UID from the iCal VEVENT (UID property).',
    )
    caldav_href = fields.Char(
        string='CalDAV Href',
        required=True,
        help='Absolute or server-relative URL path to the .ics resource.',
    )
    caldav_etag = fields.Char(
        string='ETag',
        help='The ETag returned by the server on the last successful GET/PUT. '
             'Used for optimistic locking and incremental change detection.',
    )
    last_odoo_write = fields.Datetime(
        string='Last Odoo Write',
        help='The write_date of the linked Odoo event at the time of the last '
             'push to the CalDAV server. Used to detect events modified in Odoo '
             'since the previous sync.',
    )

    _sql_constraints = [
        (
            'unique_account_uid',
            'UNIQUE(account_id, caldav_uid)',
            'A UID can only appear once per CalDAV account.',
        ),
    ]
