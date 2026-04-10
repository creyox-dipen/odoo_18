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

        For **Google** recurring series:
          - (A) Deleting a non-base occurrence: Record EXDATE in ``google_exdates``
                and immediately re-push the series.
          - (B) Deleting the base occurrence: Rewrite EXDATE + UID on the next
                occurrence, re-push, and transfer the map.
          - (C) Deleting the last occurrence: Full CalDAV DELETE (falls through).

        For **Basic Auth** servers (Radicale, Baïkal, Nextcloud, etc.):
          - (A) Deleting a non-base occurrence: Re-push the series .ics. Odoo's own
                recurrence engine embeds EXDATE in the rrule before this hook runs,
                so the re-push delivers the updated EXDATE to the CalDAV server.
          - (B) Deleting the base/first occurrence: Transfer the map to the new
                Odoo-promoted base event and re-push the series from it.
          - (C) Deleting the last occurrence: Full CalDAV DELETE (falls through).

        For single (non-recurring) events on any server type:
          - Perform a standard CalDAV DELETE via the Universal Direct Delete section.
        """
        event_ids = self.ids
        _logger.info('[UNLINK] Triggered for event ids: %s', event_ids)

        # 1. Collect all map records for these events BEFORE the loop.
        # This prevents Odoo's ondelete='cascade' from unlinking the maps
        # before we can read their href/etag for the CalDAV DELETE request.
        all_maps = self.env['caldav.event.map'].sudo().search([
            ('event_id', 'in', event_ids),
        ])
        _logger.debug('[UNLINK] Found %s mapping records for these events.', len(all_maps))

        sync_svc = self.env['caldav.sync.service']

        # Track map IDs that were already handled by the recurring logic so the
        # "Universal Direct Delete" section below skips them.
        handled_map_ids = set()

        for event in self:
            if not event.recurrence_id:
                continue
            recurrence = event.recurrence_id
            base_event = recurrence.base_event_id

            if not base_event:
                continue

            start_iso = event.start.strftime('%Y%m%dT%H%M%SZ') if event.start else None

            # --- GOOGLE RECURRING SERIES LOGIC ---
            google_base_maps = self.env['caldav.event.map'].sudo().search([
                ('event_id', '=', base_event.id),
                ('account_id.server_type', '=', 'google'),
            ])

            for g_map in google_base_maps:
                handled_map_ids.add(g_map.id)
                if event.id == base_event.id:
                    # CASE B: Delete Base -> Promote next occurrence to base
                    _logger.info('[UNLINK] Scenario B (Google): Base Delete (id=%s)', event.id)
                    next_occ = self.env['calendar.event'].sudo().search([
                        ('recurrence_id', '=', recurrence.id),
                        ('active', '=', True),
                        ('id', 'not in', event_ids),
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
                            _logger.warning('[UNLINK] Scenario B (Google) push failed: %s', e)

                        # Transfer series mapping to the new base event
                        g_map.sudo().write({
                            'event_id': next_occ.id,
                            'last_odoo_write': next_occ.write_date if push_success else False,
                            'google_exdates': new_exdates,
                        })
                    else:
                        # CASE C: Last occurrence in series deleted -> handle via direct map DELETE below
                        handled_map_ids.discard(g_map.id)
                else:
                    # CASE A: Delete occurrence -> Add EXDATE to base map and re-push
                    _logger.info('[UNLINK] Scenario A (Google): Occurrence Delete (id=%s)', event.id)
                    ex_list = set(d for d in (g_map.google_exdates or '').split(',') if d)
                    if start_iso:
                        ex_list.add(start_iso)
                    new_exdates = ','.join(sorted(ex_list))

                    g_map.sudo().write({'google_exdates': new_exdates})
                    try:
                        sync_svc._push_single_event(g_map.account_id, base_event, g_map)
                    except Exception as e:
                        _logger.warning('[UNLINK] Scenario A (Google) push failed: %s', e)
                        g_map.sudo().write({'last_odoo_write': False})

            # --- BASIC AUTH (RADICALE/BAIKAL/NEXTCLOUD) RECURRING SERIES LOGIC ---
            # For standard CalDAV servers, EXDATE must be embedded in the .ics file.
            # Odoo does NOT natively add EXDATE to recurrence.rrule on deletion.
            # We track deleted occurrence dates in the map's google_exdates field
            # (reused for all server types) and inject them when building the iCal.
            basic_base_maps = self.env['caldav.event.map'].sudo().search([
                ('event_id', '=', base_event.id),
                ('account_id.server_type', '!=', 'google'),
            ])
            _logger.info(
                '[UNLINK] Basic Auth: found %s map(s) for base_event id=%s ("%s").',
                len(basic_base_maps), base_event.id, base_event.name,
            )

            for b_map in basic_base_maps:
                handled_map_ids.add(b_map.id)
                _logger.info(
                    '[UNLINK] Basic Auth: processing map id=%s, href=%s, account=%s.',
                    b_map.id, b_map.caldav_href, b_map.account_id.name,
                )
                if event.id == base_event.id:
                    # CASE B (Basic): Delete Base -> Promote next occurrence to base.
                    # Odoo promotes the next occurrence via _select_new_base_event automatically.
                    # We transfer the map to that new base, record the deleted base as
                    # an EXDATE, and re-push the series.
                    _logger.info('[UNLINK] Scenario B (Basic): Base Delete (id=%s, start=%s)', event.id, start_iso)
                    next_occ = self.env['calendar.event'].sudo().search([
                        ('recurrence_id', '=', recurrence.id),
                        ('active', '=', True),
                        ('id', 'not in', event_ids),
                    ], order='start asc', limit=1)

                    if next_occ:
                        # CRITICAL: Copy the original series UID to the new base so the
                        # UID inside the pushed iCal matches the href (e.g. /OCC1_UUID.ics).
                        # Without this, the file at OCC1_UUID.ics would contain OCC2's UID,
                        # causing a UID/href mismatch that confuses CalDAV clients.
                        if next_occ.caldav_uid != b_map.caldav_uid:
                            _logger.info(
                                '[UNLINK] Scenario B (Basic): Copying UID from map (%s) '
                                'to next_occ (id=%s, current uid=%s) so href and iCal UID match.',
                                b_map.caldav_uid, next_occ.id, next_occ.caldav_uid,
                            )
                            next_occ.sudo().write({'caldav_uid': b_map.caldav_uid})

                        # Record the deleted base's date as an EXDATE
                        ex_list = set(d.strip() for d in (b_map.google_exdates or '').split(',') if d.strip())
                        if start_iso:
                            ex_list.add(start_iso)
                        new_exdates = ','.join(sorted(ex_list))
                        _logger.info(
                            '[UNLINK] Scenario B (Basic): Accumulated EXDATEs for map id=%s: %s',
                            b_map.id, new_exdates,
                        )
                        # Transfer the map to the new base and write EXDATEs
                        b_map.sudo().write({
                            'event_id': next_occ.id,
                            'google_exdates': new_exdates,
                            'last_odoo_write': False,
                        })
                        try:
                            sync_svc._push_single_event(b_map.account_id, next_occ, b_map)
                            _logger.info(
                                '[UNLINK] Scenario B (Basic): Push successful. '
                                'Radicale should now have DTSTART=original + EXDATE=%s.',
                                start_iso,
                            )
                        except Exception as e:
                            _logger.warning('[UNLINK] Scenario B (Basic) push failed: %s', e)
                    else:
                        # CASE C (Basic): Last occurrence deleted -> allow full CalDAV DELETE below
                        _logger.info('[UNLINK] Scenario C (Basic): Last occurrence — will DELETE series.')
                        handled_map_ids.discard(b_map.id)
                else:
                    # CASE A (Basic): Non-base occurrence deleted.
                    # CRITICAL: Record the occurrence's start date as an EXDATE in the map.
                    # _odoo_event_to_ical will read this and inject it into the iCal.
                    # Odoo does NOT embed EXDATE in recurrence.rrule automatically.
                    ex_list = set(d.strip() for d in (b_map.google_exdates or '').split(',') if d.strip())
                    if start_iso:
                        ex_list.add(start_iso)
                    new_exdates = ','.join(sorted(ex_list))
                    _logger.info(
                        '[UNLINK] Scenario A (Basic): Occurrence Delete (id=%s, start=%s). '
                        'Accumulated EXDATEs for map id=%s: %s',
                        event.id, start_iso, b_map.id, new_exdates,
                    )
                    # Write accumulated EXDATEs to map BEFORE pushing so _odoo_event_to_ical picks them up
                    b_map.sudo().write({'google_exdates': new_exdates})
                    try:
                        sync_svc._push_single_event(b_map.account_id, base_event, b_map)
                        _logger.info(
                            '[UNLINK] Scenario A (Basic): Push successful. '
                            'Radicale should now have EXDATE=%s in the .ics.',
                            start_iso,
                        )
                    except Exception as e:
                        _logger.warning('[UNLINK] Scenario A (Basic) push failed: %s', e)
                        b_map.sudo().write({'last_odoo_write': False})

        # --- UNIVERSAL DIRECT DELETE (Single events and series final cleanup) ---
        for map_rec in all_maps:
            if not map_rec.exists():
                continue
            # Skip maps already handled by Google or Basic recurring logic above.
            if map_rec.id in handled_map_ids:
                _logger.debug(
                    '[UNLINK] Map id=%s already handled by recurring logic, skipping DELETE.',
                    map_rec.id,
                )
                continue
            # If the map was already transferred to a new base (Scenario B), keep it.
            if map_rec.event_id and map_rec.event_id.id not in event_ids:
                _logger.debug(
                    '[UNLINK] Map id=%s was promoted to next occurrence, skipping DELETE.',
                    map_rec.id,
                )
                continue

            try:
                _logger.info(
                    '[UNLINK] CalDAV DELETE: event "%s" (id=%s) via account %s at %s',
                    map_rec.event_id.name, map_rec.event_id.id,
                    map_rec.account_id.name, map_rec.caldav_href,
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