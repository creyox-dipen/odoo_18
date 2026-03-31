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
        """Intercept deletion to propagate CalDAV removals.

        For Google recurring series:
          - (A) Deleting a non-base occurrence: Record EXDATE and re-push base.
          - (B) Deleting the base occurrence: Promote the next occurrence to base
                and transfer the CalDAV mapping.
          - (C) Deleting the last occurrence: Permanent CalDAV DELETE.

        For all other scenarios (single Google events and all non-Google servers):
          - Perform a standard direct-map CalDAV DELETE.
        """
        _logger.info('CalDAV unlink() triggered for event ids: %s', self.ids)
        
        for event in self:
            # Step 1: Handle Google Recurring Logic
            # Map attached to the base_event controls the whole series.
            if event.recurrence_id:
                recurrence = event.recurrence_id
                base_event = recurrence.base_event_id
                if base_event:
                    google_base_maps = self.env['caldav.event.map'].sudo().search([
                        ('event_id', '=', base_event.id),
                        ('account_id.server_type', '=', 'google'),
                    ])
                    start_iso = event.start.strftime('%Y%m%dT%H%M%SZ') if event.start else None
                    sync_svc = self.env['caldav.sync.service']

                    for g_map in google_base_maps:
                        if event.id == base_event.id:
                            # CASE B: Delete Base -> Promote next occurrence to base
                            _logger.info('[UNLINK] CASE B: Google Base Delete (id=%s)', event.id)
                            next_occ = self.env['calendar.event'].sudo().search([
                                ('recurrence_id', '=', recurrence.id),
                                ('active', '=', True),
                                ('id', 'not in', self.ids),
                            ], order='start asc', limit=1)

                            if next_occ:
                                if next_occ.caldav_uid != g_map.caldav_uid:
                                    next_occ.sudo().write({'caldav_uid': g_map.caldav_uid})

                                ex_list = set(d for d in (g_map.google_exdates or '').split(',') if d)
                                if start_iso:
                                    ex_list.add(start_iso)
                                new_exdates = ','.join(sorted(ex_list))

                                g_map.sudo().write({'google_exdates': new_exdates})
                                push_success = False
                                try:
                                    sync_svc._push_single_event(g_map.account_id, event, g_map)
                                    push_success = True
                                except Exception as e:
                                    _logger.warning('[UNLINK] Scenario B push failed: %s', e)

                                # Transfer series mapping to the new base event
                                g_map.sudo().write({
                                    'event_id': next_occ.id,
                                    'last_odoo_write': next_occ.write_date if push_success else False,
                                    'google_exdates': new_exdates,
                                })
                            else:
                                # CASE C: Last occurrence in series deleted -> standard DELETE
                                try:
                                    g_map.account_id._delete_event(g_map.caldav_href, etag=g_map.caldav_etag)
                                except Exception:
                                    pass
                                g_map.unlink()
                        else:
                            # CASE A: Delete occurrence -> Add EXDATE to base map
                            _logger.info('[UNLINK] CASE A: Google Occurrence Delete (id=%s)', event.id)
                            ex_list = set(d for d in (g_map.google_exdates or '').split(',') if d)
                            if start_iso:
                                ex_list.add(start_iso)
                            new_exdates = ','.join(sorted(ex_list))
                            
                            g_map.sudo().write({'google_exdates': new_exdates})
                            try:
                                sync_svc._push_single_event(g_map.account_id, base_event, g_map)
                            except Exception as e:
                                _logger.warning('[UNLINK] Scenario A push failed: %s', e)
                                g_map.sudo().write({'last_odoo_write': False})

            # Step 2: Universal Direct DELETE
            # Handles non-recurring Google events and all events on other CalDAV servers.
            all_direct_maps = self.env['caldav.event.map'].sudo().search([
                ('event_id', '=', event.id),
            ])
            for map_rec in all_direct_maps.exists():
                try:
                    _logger.info(
                        '[UNLINK] Direct CalDAV DELETE for event "%s" (id=%s) via account %s',
                        map_rec.event_id.name, map_rec.event_id.id, map_rec.account_id.name
                    )
                    map_rec.account_id._delete_event(map_rec.caldav_href, etag=map_rec.caldav_etag)
                except Exception as ex:
                    _logger.warning('[UNLINK] Direct CalDAV DELETE failed: %s', ex)
                map_rec.unlink()

        return super().unlink()

    def caldav_sync_action(self):
        """Trigger a CalDAV sync for the current user from the calendar view button.

        Called when the user clicks the "CalDAV Sync" button in the calendar view
        control panel. Delegates to ``caldav.sync.service.action_sync_current_user``.

        :return: Client notification action.
        :rtype: dict
        """
        return self.env['caldav.sync.service'].action_sync_current_user()
