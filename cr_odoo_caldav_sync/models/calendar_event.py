# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    """Extends the Odoo calendar.event model for CalDAV synchronisation.

    Adds a ``caldav_uid`` field that serves as the iCal UID for this event.
    The UID is auto-generated on creation and is used to correlate Odoo events
    with their CalDAV counterparts across sync runs.

    The ``write()`` override is intentionally minimal — actual sync logic lives
    in ``caldav.sync.service`` and is triggered by the cron or manual button.
    The only hook here is ensuring a UID exists before the event is saved.
    """

    _inherit = 'calendar.event'

    caldav_uid = fields.Char(
        string='CalDAV UID',
        copy=False,
        index=True,
        help='UUID used as the iCal UID for this event. Generated automatically.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign a CalDAV UID to every new event.

        :param list vals_list: List of field-value dicts for new events.
        :return: Newly created calendar event recordset.
        :rtype: recordset
        """
        for vals in vals_list:
            if not vals.get('caldav_uid'):
                vals['caldav_uid'] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, values):
        """Override write to auto-assign CalDAV UID if missing.

        Ensures events created before module installation also receive a UID
        on their next write operation.

        :param dict values: Field-value pairs to update.
        :return: True on success.
        :rtype: bool
        """
        for record in self:
            if not record.caldav_uid:
                values.setdefault('caldav_uid', str(uuid.uuid4()))
                break
        return super().write(values)

    def unlink(self):
        """Override unlink to push deletions to CalDAV servers before removing records.

        For every event being deleted, we look up all CalDAV event maps and
        issue a DELETE request to each account's server so the deletion is
        propagated. Maps are then cascade-deleted automatically via the FK.

        :return: True on success.
        :rtype: bool
        """
        maps = self.env['caldav.event.map'].search([
            ('event_id', 'in', self.ids),
        ])
        for map_rec in maps:
            try:
                map_rec.account_id._delete_event(map_rec.caldav_href, etag=map_rec.caldav_etag)
            except Exception as e:
                _logger.warning(
                    'CalDAV delete failed for event %s on account %s: %s',
                    map_rec.caldav_uid, map_rec.account_id.name, e,
                )
        return super().unlink()

    def caldav_sync_action(self):
        """Trigger a CalDAV sync for the current user from the calendar view button.

        Called when the user clicks the "CalDAV Sync" button in the calendar view
        control panel. Delegates to ``caldav.sync.service.action_sync_current_user``.

        :return: Client notification action.
        :rtype: dict
        """
        return self.env['caldav.sync.service'].action_sync_current_user()
