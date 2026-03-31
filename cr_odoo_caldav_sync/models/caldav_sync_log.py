# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class CalDAVSyncLog(models.Model):
    """Stores the results of individual CalDAV synchronisation runs.
    
    This model tracks how many events were pushed, pulled, and deleted
    during each sync, and captures any error details if the sync failed.
    """
    _name = 'caldav.sync.log'
    _description = 'CalDAV Sync Log'
    _order = 'sync_date desc'

    account_id = fields.Many2one(
        'caldav.account',
        string='CalDAV Account',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sync_date = fields.Datetime(
        string='Sync Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    pushed = fields.Integer(
        string='Events Pushed',
        readonly=True,
        help='Number of successfully pushed Odoo events to the CalDAV server.',
    )
    pulled = fields.Integer(
        string='Events Pulled',
        readonly=True,
        help='Number of successfully pulled events from the CalDAV server.',
    )
    deleted = fields.Integer(
        string='Events Deleted',
        readonly=True,
        help='Number of successfully deleted events (server-side).',
    )
    failed = fields.Integer(
        string='Failures',
        readonly=True,
        help='Number of events that failed to sync during this run.',
    )
    status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('partial', 'Partial Failure'),
            ('failed', 'Critical Failure'),
        ],
        string='Status',
        required=True,
        readonly=True,
        default='success',
    )
    details = fields.Text(
        string='Log Details',
        readonly=True,
        help='Summary of errors or specific event failure messages.',
    )
