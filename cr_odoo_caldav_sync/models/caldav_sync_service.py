# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import uuid
import pytz
from datetime import datetime, timedelta, timezone, date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import vobject
except ImportError:
    vobject = None
    _logger.warning('vobject is not available; CalDAV iCal parsing will be disabled.')


def _to_utc_naive(dt_obj):
    """Convert a timezone-aware or naive datetime to a UTC-naive datetime.

    :param datetime dt_obj: Input datetime (may be aware or naive).
    :return: UTC-naive datetime.
    :rtype: datetime
    """
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        if dt_obj.tzinfo is not None:
            return dt_obj.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_obj
    # date-only value → treat as all-day
    return datetime(dt_obj.year, dt_obj.month, dt_obj.day)


def _is_date_only(dt_obj):
    """Return True if dt_obj is a plain date (not datetime) — indicating an all-day event.

    :param dt_obj: date or datetime object.
    :rtype: bool
    """
    return isinstance(dt_obj, date) and not isinstance(dt_obj, datetime)


class CalDAVSyncService(models.AbstractModel):
    """Stateless service model that orchestrates CalDAV synchronisation.

    This model contains no persistent fields; it acts as a namespace for sync
    logic methods.  Methods are called from the cron job or from user-initiated
    actions on ``caldav.account`` records.

    The sync algorithm:
    1. Fetch server CTag.  If unchanged since ``last_ctag``, skip (fast path).
    2. If direction allows, push Odoo-side changes to the CalDAV server.
    3. If direction allows, pull CalDAV-side changes into Odoo.
    4. Archive Odoo events whose hrefs have disappeared from the server.
    5. Update ``last_ctag`` and ``last_sync``.
    """

    _name = 'caldav.sync.service'
    _description = 'CalDAV Sync Service'

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def _cron_sync_all(self):
        """Cron entry point: sync every active CalDAV account.

        Called automatically every 15 minutes by the scheduled cron job.
        Errors per account are caught and logged so that one broken account
        does not prevent others from syncing.
        """
        accounts = self.env['caldav.account'].search([('active', '=', True)])
        for account in accounts:
            try:
                self.sync_account(account)
            except Exception as e:
                _logger.error(
                    'CalDAV auto-sync failed for account %s (id=%s): %s',
                    account.name, account.id, e, exc_info=True,
                )

    # ------------------------------------------------------------------
    # Main sync orchestrator
    # ------------------------------------------------------------------

    @api.model
    def sync_account(self, account):
        """Perform a full incremental sync for one CalDAV account.

        :param caldav.account account: The account to sync.
        :return: Dict with counters: {'pushed': N, 'pulled': N, 'deleted': N}.
        :rtype: dict
        """
        stats = {'pushed': 0, 'pulled': 0, 'deleted': 0}

        # --- Phase 1: Pull from CalDAV ---
        # Always pull so we don't miss server-side changes.
        # Per-event ETag comparison inside _pull_caldav_changes skips unchanged events.
        pulled_event_ids = set()
        current_ctag = account._get_server_ctag()
        if account.sync_direction in ('bidirectional', 'caldav_to_odoo'):
            _logger.debug('Pulling changes from CalDAV for account %s.', account.name)
            pulled, deleted, pulled_ids = self._pull_caldav_changes(account)
            stats['pulled'] = pulled
            stats['deleted'] = deleted
            pulled_event_ids = set(pulled_ids)

        # --- Phase 2: Push to CalDAV ---
        if account.sync_direction in ('bidirectional', 'odoo_to_caldav'):
            _logger.debug('Pushing changes to CalDAV for account %s.', account.name)
            # Pass pulled_event_ids to skip re-pushing what we just pulled
            stats['pushed'] = self._push_odoo_changes(account, skip_ids=pulled_event_ids)

        # Update CTag and last_sync timestamp
        new_ctag = account._get_server_ctag() or current_ctag
        account.sudo().write({
            'last_ctag': new_ctag,
            'last_sync': fields.Datetime.now(),
        })
        return stats

    # ------------------------------------------------------------------
    # Push: Odoo → CalDAV
    # ------------------------------------------------------------------

    @api.model
    def _push_odoo_changes(self, account, skip_ids=None):
        """Push new, modified, and deleted Odoo events to the CalDAV server.

        Handles three cases:
        * **Deleted** events: archived Odoo events that still have a mapping are
          removed from the server via DELETE, then their mapping is cleaned up.
        * **New** events: events with no mapping are uploaded via PUT.
        * **Updated** events: events modified since the last push are re-uploaded.

        Recurring event occurrences are skipped — only the base event (with the
        RRULE) is pushed.

        :param caldav.account account: Target account.
        :param set skip_ids: Optional set of event IDs to skip (recently pulled).
        :return: Number of events pushed/deleted.
        :rtype: int
        """
        pushed = 0
        skip_ids = skip_ids or set()
        owner_partner = account.user_id.partner_id

        # --- Phase 2a: Push deletions ---
        # Find all mappings for this account whose Odoo event is now archived
        all_maps = self.env['caldav.event.map'].sudo().search([
            ('account_id', '=', account.id),
        ])
        for map_rec in all_maps:
            event = map_rec.event_id
            if not event:
                # Dangling map — clean up
                map_rec.sudo().unlink()
                continue
            if not event.active and event.id not in skip_ids:
                # Event was archived in Odoo → delete from server
                try:
                    _logger.info(
                        'Deleting CalDAV event for archived Odoo event "%s" (id=%s) at %s',
                        event.name, event.id, map_rec.caldav_href,
                    )
                    account._delete_event(map_rec.caldav_href, etag=map_rec.caldav_etag)
                    pushed += 1
                except Exception as e:
                    _logger.warning(
                        'Could not delete CalDAV event for "%s" (id=%s): %s',
                        event.name, event.id, e,
                    )
                finally:
                    # Always remove the local mapping so we don't retry forever
                    map_rec.sudo().unlink()

        # --- Phase 2b: Push creates and updates ---
        # Use sudo() to bypass record rules, then filter by partner in Python.
        owner_partner_id = owner_partner.id

        # Non-recurring events: recurrence_id is False
        non_recurring = self.env['calendar.event'].sudo().search([
            ('active', '=', True),
            ('recurrence_id', '=', False),
        ]).filtered(lambda e: owner_partner_id in e.partner_ids.ids)

        # Recurring events: each recurrence series has a base_event_id containing
        # the RRULE. We push ONE .ics per series (the base event).
        # Access is checked via attendee_ids, which is always populated.
        recurrences = self.env['calendar.recurrence'].sudo().search([])
        recurring_base_events = recurrences.mapped('base_event_id').filtered(
            lambda e: e.active and any(
                att.partner_id.id == owner_partner_id for att in e.attendee_ids
            )
        )

        events = non_recurring | recurring_base_events
        _logger.info(
            'Push candidates for account %s: %s event(s) — non-recurring=%s, recurring_base=%s',
            account.name, len(events), len(non_recurring), len(recurring_base_events),
        )

        existing_maps = {
            m.event_id.id: m
            for m in self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
                ('event_id', 'in', events.ids),
            ])
        }

        for event in events:
            if event.id in skip_ids:
                continue
            existing_map = existing_maps.get(event.id)
            # Determine if event is new to CalDAV or was modified since last push
            if existing_map:
                last_push = existing_map.last_odoo_write
                if last_push and event.write_date and event.write_date <= last_push:
                    continue  # unchanged since last push
            try:
                etag = self._push_single_event(account, event, existing_map)
                pushed += 1
                _logger.debug(
                    'Pushed event "%s" (id=%s) to %s; etag=%s',
                    event.name, event.id, account.url, etag,
                )
            except Exception as e:
                # Handle 412 Precondition Failed specifically as a conflict
                msg = str(e)
                if '412' in msg and existing_map:
                    _logger.warning(
                        'Conflict detected for event "%s" (id=%s): Server has a newer version. '
                        'Attempting auto-recovery pull.',
                        event.name, event.id
                    )
                    try:
                        # Self-healing: Pull the latest state of this specific event right now
                        new_etag, ical_text = account._fetch_ical_with_etag(existing_map.caldav_href)
                        self._upsert_from_ical(account, existing_map.caldav_href, new_etag, ical_text, existing_map)
                        _logger.info('Auto-recovery pull successful for event "%s".', event.name)
                    except Exception as re:
                        _logger.error('Auto-recovery pull failed for event "%s": %s', event.name, re)
                else:
                    _logger.error(
                        'Failed to push event "%s" (id=%s) to account %s: %s',
                        event.name, event.id, account.name, e, exc_info=True,
                    )
        return pushed

    @api.model
    def _push_single_event(self, account, event, existing_map=None):
        """Build the iCal string and PUT it to the CalDAV server.

        Creates or updates the ``caldav.event.map`` record to track the mapping.

        :param caldav.account account: Target account.
        :param calendar.event event: Odoo event to push.
        :param caldav.event.map|None existing_map: Existing map record if any.
        :return: ETag returned by the server.
        :rtype: str
        """
        uid = event.caldav_uid or str(uuid.uuid4())
        if not event.caldav_uid:
            event.sudo().write({'caldav_uid': uid})

        ical_str = self._odoo_event_to_ical(event, account)
        href = existing_map.caldav_href if existing_map else self._build_href(account, uid)
        old_etag = existing_map.caldav_etag if existing_map else None

        _logger.info('Pushing event "%s" (id=%s) to %s; If-Match ETag=%s', event.name, event.id, href, old_etag)
        new_etag = account._put_ical(href, ical_str, etag=old_etag)
        _logger.debug('Push successful; new ETag=%s', new_etag)

        map_vals = {
            'account_id': account.id,
            'event_id': event.id,
            'caldav_uid': uid,
            'caldav_href': href,
            'caldav_etag': new_etag,
            'last_odoo_write': event.write_date,
        }
        if existing_map:
            existing_map.sudo().write(map_vals)
        else:
            self.env['caldav.event.map'].sudo().create(map_vals)
        return new_etag

    @api.model
    def _build_href(self, account, uid):
        """Build the CalDAV resource URL for a new event.

        :param caldav.account account: The account providing the base URL.
        :param str uid: The CalDAV UID (UUID) for this event.
        :return: Absolute URL to the .ics resource.
        :rtype: str
        """
        base = account.url.rstrip('/')
        return f'{base}/{uid}.ics'

    # ------------------------------------------------------------------
    # Pull: CalDAV → Odoo
    # ------------------------------------------------------------------

    @api.model
    def _pull_caldav_changes(self, account):
        """Pull new and changed events from the CalDAV server into Odoo.

        :param caldav.account account: Source account.
        :return: Tuple (pulled_count, deleted_count, pulled_event_ids).
        :rtype: tuple[int, int, list]
        """
        pulled = 0
        deleted = 0
        pulled_ids = []

        raw_server_etags = account._get_server_etags()  # {href: etag}

        # Normalize HREFs to absolute URLs for reliable comparison with Odoo maps
        server_etags = {
            account._resolve_href(href): etag
            for href, etag in raw_server_etags.items()
        }
        _logger.debug('Normalized server HREFs for account %s: %s', account.name, list(server_etags.keys()))

        existing_maps = {
            m.caldav_href: m
            for m in self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
            ])
        }
        _logger.debug('Existing Odoo maps for account %s: %s', account.name, list(existing_maps.keys()))

        # Process new and changed events (only if server has events)
        for href, server_etag in server_etags.items():
            existing = existing_maps.get(href)
            if existing:
                _logger.debug('Comparing HREFs for %s: local_etag=%s, server_etag=%s', href, existing.caldav_etag, server_etag)
                # If the mapped Odoo event is archived, skip pulling it back.
                # The push phase will handle the server-side deletion.
                if existing.event_id and not existing.event_id.active:
                    _logger.debug(
                        'Skipping pull for archived Odoo event href %s — will be deleted in push phase.', href
                    )
                    continue
            if existing and existing.caldav_etag == server_etag:
                continue  # unchanged
            try:
                _logger.info('Pulling CalDAV event from %s (account %s)', href, account.name)
                ical_text = account._fetch_ical(href)
                event = self._upsert_from_ical(account, href, server_etag, ical_text, existing)
                if event:
                    pulled_ids.append(event.id)
                pulled += 1
            except Exception as e:
                _logger.error(
                    'Failed to pull CalDAV event from %s (account %s): %s',
                    href, account.name, e, exc_info=True,
                )

        # Archive events deleted on server
        server_hrefs = set(server_etags.keys())
        _logger.info(
            'Deletion check for account %s: server_hrefs=%s, map_hrefs=%s',
            account.name, sorted(server_hrefs), sorted(existing_maps.keys()),
        )
        for href, map_rec in list(existing_maps.items()):
            if href not in server_hrefs:
                try:
                    if map_rec.event_id:
                        event = map_rec.event_id
                        _logger.info(
                            'Archiving Odoo event "%s" (id=%s) — deleted from CalDAV server.',
                            event.name, event.id,
                        )
                        # Use sudo + with_context to bypass potential attendee restrictions
                        event.with_context(no_sync=True).sudo().write({'active': False})
                    map_rec.sudo().unlink()
                    deleted += 1
                except Exception as e:
                    _logger.warning(
                        'Could not archive Odoo event for deleted CalDAV href %s: %s', href, e
                    )

        return pulled, deleted, pulled_ids

    @api.model
    def _upsert_from_ical(self, account, href, server_etag, ical_text, existing_map=None):
        """Parse iCal text and create/update the corresponding Odoo calendar event.

        Handles both single events and recurring events (via RRULE).
        Invitation emails are suppressed or allowed based on account settings.

        :param caldav.account account: The source account.
        :param str href: CalDAV resource href.
        :param str server_etag: Current server ETag.
        :param str ical_text: Raw iCal text.
        :param caldav.event.map|None existing_map: Existing map record if any.
        """
        if vobject is None:
            _logger.warning('vobject not available; skipping iCal import.')
            return

        try:
            cal = vobject.readOne(ical_text)
        except Exception as e:
            _logger.warning('Failed to parse iCal from %s: %s', href, e)
            return

        vevent = None
        for component in cal.components():
            if component.name == 'VEVENT':
                vevent = component
                break
        if vevent is None:
            return

        uid = getattr(vevent, 'uid', None)
        uid_value = uid.value if uid else str(uuid.uuid4())

        vals = self._ical_to_odoo_vals(vevent, account)
        if not vals:
            return

        ctx_kwargs = {}
        if not account.send_invitation_emails:
            ctx_kwargs['dont_notify'] = True
            ctx_kwargs['no_mail_to_attendees'] = True

        CalEvent = self.env['calendar.event'].with_context(**ctx_kwargs).sudo()

        if existing_map and existing_map.event_id:
            event = existing_map.event_id
            # Preserve caldav_uid; don't let sync overwrite it
            vals.pop('caldav_uid', None)
            # For Odoo-owned recurring events, DON'T re-apply the RRULE from the
            # server. Doing so triggers `recurrence_update='all_events'` which:
            #   1. Regenerates occurrences (can create extra M4 when COUNT=3 + EXDATE)
            #   2. Updates write_date → push detects "changed" → push loop
            # Odoo is the master of the recurrence structure; only EXDATE
            # changes (individual deletions) are synced via the block below.
            if event.recurrence_id:
                vals.pop('rrule', None)
                vals.pop('recurrence_update', None)
            elif vals.get('rrule'):
                vals['recurrence_update'] = 'all_events'
            event.write(vals)
        else:
            vals['caldav_uid'] = uid_value
            event = CalEvent.create(vals)

        # Handle EXDATE — single occurrence deleted on the server side.
        # Thunderbird/CalDAV clients mark excluded dates with EXDATE instead of
        # deleting the whole .ics. We remove the matching Odoo occurrences.
        exdate_comp = getattr(vevent, 'exdate', None)
        if exdate_comp and event.recurrence_id:
            # exdate.value can be a list of datetimes or a single datetime
            raw_exdates = exdate_comp.value
            if not isinstance(raw_exdates, (list, tuple)):
                raw_exdates = [raw_exdates]
            excluded_dates = set()
            for ex in raw_exdates:
                try:
                    if hasattr(ex, 'date'):
                        excluded_dates.add(ex.date())
                    else:
                        from datetime import date as _date
                        excluded_dates.add(_date(ex.year, ex.month, ex.day))
                except Exception:
                    pass
            if excluded_dates:
                occurrences_to_delete = event.recurrence_id.calendar_event_ids.filtered(
                    lambda e: e.active and (
                        (e.allday and e.start_date in excluded_dates)
                        or (not e.allday and e.start and e.start.date() in excluded_dates)
                    )
                )
                for occ in occurrences_to_delete:
                    _logger.info(
                        'Removing excluded occurrence "%s" (id=%s, date=%s) via EXDATE.',
                        occ.name, occ.id, occ.start,
                    )
                    # Save refs BEFORE unlink (occ fields become invalid after).
                    occ_is_mapped_base = (
                        existing_map and existing_map.exists()
                        and occ.id == existing_map.event_id.id
                    )
                    occ_recurrence = occ.recurrence_id

                    # Unlink: Odoo's calendar.event.unlink() will automatically
                    # call _select_new_base_event, updating recurrence.base_event_id.
                    # Our ondelete='cascade' on the map's event_id will also
                    # cascade-delete the map if occ was the mapped base event.
                    occ.with_context(no_caldav_delete=True).sudo().unlink()

                    # If the map was cascade-deleted, recreate it pointing to the
                    # new base so the push phase doesn't treat it as a new event.
                    if occ_is_mapped_base and occ_recurrence.exists():
                        new_base = occ_recurrence.base_event_id
                        if new_base and new_base.exists():
                            _logger.info(
                                'Map was cascade-deleted; redirecting to new base (id=%s).',
                                new_base.id,
                            )
                            # Force creation of a new map for the new base in
                            # the map_vals block below.
                            event = new_base
                            existing_map = None

        map_vals = {
            'account_id': account.id,
            'event_id': event.id,
            'caldav_uid': uid_value,
            'caldav_href': href,
            'caldav_etag': server_etag,
            'last_odoo_write': event.write_date,
        }
        if existing_map:
            existing_map.sudo().write(map_vals)
        else:
            self.env['caldav.event.map'].sudo().create(map_vals)

        return event

    # ------------------------------------------------------------------
    # iCal generation (Odoo → iCal)
    # ------------------------------------------------------------------

    @api.model
    def _odoo_event_to_ical(self, event, account):
        """Convert an Odoo ``calendar.event`` to an iCal VCALENDAR string.

        Handles:
        * Single events and recurring events (RRULE on base event only)
        * All-day events (DATE vs DATE-TIME)
        * Location, description (without injecting Odoo attendee details)
        * Attendees (ORGANIZER + ATTENDEE) — only when the event has real attendees

        :param calendar.event event: The Odoo event to serialise.
        :param caldav.account account: The CalDAV account (provides owner context).
        :return: Full VCALENDAR iCal string.
        :rtype: str
        """
        if vobject is None:
            raise RuntimeError('vobject is required for iCal generation.')

        cal = vobject.iCalendar()
        cal.add('prodid').value = '-//Creyox Technologies//CalDAV Sync//EN'
        cal.add('version').value = '2.0'

        vevent = cal.add('vevent')

        # UID
        uid = event.caldav_uid or str(uuid.uuid4())
        vevent.add('uid').value = uid

        # DTSTAMP
        vevent.add('dtstamp').value = datetime.now(pytz.utc)

        # SUMMARY
        vevent.add('summary').value = event.name or ''

        # DTSTART / DTEND
        if event.allday:
            start_date = event.start_date or event.start.date()
            stop_date = event.stop_date or event.stop.date()
            dtstart = vevent.add('dtstart')
            dtstart.value = start_date
            dtend = vevent.add('dtend')
            # iCal convention: all-day end date is exclusive
            dtend.value = stop_date + timedelta(days=1)
        else:
            start_utc = _to_utc_naive(event.start) or datetime.utcnow()
            stop_utc = _to_utc_naive(event.stop) or (start_utc + timedelta(hours=1))
            dtstart = vevent.add('dtstart')
            dtstart.value = datetime(
                start_utc.year, start_utc.month, start_utc.day,
                start_utc.hour, start_utc.minute, start_utc.second,
                tzinfo=pytz.utc,
            )
            dtend = vevent.add('dtend')
            dtend.value = datetime(
                stop_utc.year, stop_utc.month, stop_utc.day,
                stop_utc.hour, stop_utc.minute, stop_utc.second,
                tzinfo=pytz.utc,
            )

        # LOCATION
        if event.location:
            vevent.add('location').value = event.location

        # DESCRIPTION (plain text, no Odoo attendee injection)
        if event.description:
            from odoo.tools import html2plaintext
            plain = html2plaintext(event.description or '').strip()
            if plain:
                vevent.add('description').value = plain

        # RRULE — include for any event that belongs to a recurring series.
        # Odoo's recurrence.rrule is stored as str(dateutil.rrule) which is a
        # multi-line string: "DTSTART:...\nRRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=3"
        # We must extract just the RRULE line and strip the RRULE: prefix for vobject.
        rrule_value = None
        if event.recurrence_id:
            raw = event.recurrence_id.rrule or ''
            for line in raw.splitlines():
                line = line.strip()
                if line.upper().startswith('RRULE:'):
                    rrule_value = line[len('RRULE:'):]
                    break
            if not rrule_value and raw and not raw.upper().startswith('DTSTART'):
                # Fallback: raw might already be just the params (no prefix)
                rrule_value = raw.strip('RRULE:') if raw.startswith('RRULE:') else raw
        if not rrule_value and hasattr(event, 'rrule') and event.rrule:
            raw = event.rrule
            for line in raw.splitlines():
                line = line.strip()
                if line.upper().startswith('RRULE:'):
                    rrule_value = line[len('RRULE:'):]
                    break
            if not rrule_value:
                rrule_value = raw.lstrip('RRULE:') if raw.startswith('RRULE:') else raw
        if rrule_value:
            _logger.info('Adding RRULE to iCal for event "%s": %s', event.name, rrule_value)
            vevent.add('rrule').value = rrule_value

        # ORGANIZER + ATTENDEE — only if there are real attendees (not just the owner)
        other_partners = event.partner_ids.filtered(
            lambda p: p != account.user_id.partner_id
        )
        if other_partners:
            owner = account.user_id.partner_id
            org = vevent.add('organizer')
            org.value = f'mailto:{owner.email or account.username}'
            org.params['CN'] = [owner.name or account.username]

            for partner in event.partner_ids:
                if not partner.email:
                    continue
                att = vevent.add('attendee')
                att.value = f'mailto:{partner.email}'
                att.params['CN'] = [partner.name or partner.email]
                att.params['PARTSTAT'] = ['ACCEPTED']

        return cal.serialize()

    # ------------------------------------------------------------------
    # iCal parsing (CalDAV → Odoo)
    # ------------------------------------------------------------------

    @api.model
    def _ical_to_odoo_vals(self, vevent, account):
        """Parse a vobject VEVENT component into Odoo calendar.event field values.

        Handles:
        * SUMMARY → name
        * DTSTART / DTEND → start, stop, allday
        * LOCATION → location
        * DESCRIPTION → description (as HTML)
        * RRULE → recurrency + recurrence fields via Odoo's own parser
        * ATTENDEE → partner_ids (look up by email, optionally create new contacts)

        :param vevent: vobject Component of type VEVENT.
        :param caldav.account account: Provides context for partner lookup.
        :return: Dict of Odoo field values, or empty dict on parse failure.
        :rtype: dict
        """
        try:
            vals = {}

            # SUMMARY
            summary = getattr(vevent, 'summary', None)
            vals['name'] = summary.value if summary else '(No Title)'

            # DTSTART / DTEND
            dtstart_comp = getattr(vevent, 'dtstart', None)
            dtend_comp = getattr(vevent, 'dtend', None)
            duration_comp = getattr(vevent, 'duration', None)

            if dtstart_comp is None:
                return {}

            dtstart_val = dtstart_comp.value
            allday = _is_date_only(dtstart_val)
            vals['allday'] = allday

            if allday:
                vals['start'] = datetime(
                    dtstart_val.year, dtstart_val.month, dtstart_val.day, 8, 0, 0
                )
                if dtend_comp and dtend_comp.value:
                    dtend_val = dtend_comp.value
                    if _is_date_only(dtend_val):
                        # all-day DTEND is exclusive → subtract 1 day
                        end_date = date(dtend_val.year, dtend_val.month, dtend_val.day) - timedelta(days=1)
                        vals['stop'] = datetime(end_date.year, end_date.month, end_date.day, 18, 0, 0)
                    else:
                        vals['stop'] = _to_utc_naive(dtend_val)
                else:
                    vals['stop'] = datetime(
                        dtstart_val.year, dtstart_val.month, dtstart_val.day, 18, 0, 0
                    )
            else:
                start_utc = _to_utc_naive(dtstart_val)
                if start_utc is None:
                    return {}
                vals['start'] = start_utc
                if dtend_comp and dtend_comp.value:
                    stop_val = _to_utc_naive(dtend_comp.value)
                    vals['stop'] = stop_val or (start_utc + timedelta(hours=1))
                elif duration_comp and duration_comp.value:
                    dur = duration_comp.value  # timedelta
                    vals['stop'] = start_utc + dur
                else:
                    vals['stop'] = start_utc + timedelta(hours=1)

            # LOCATION
            location_comp = getattr(vevent, 'location', None)
            if location_comp and location_comp.value:
                vals['location'] = location_comp.value

            # DESCRIPTION
            desc_comp = getattr(vevent, 'description', None)
            if desc_comp and desc_comp.value:
                # Store as simple HTML paragraph
                vals['description'] = f'<p>{desc_comp.value.replace(chr(10), "<br/>")}</p>'

            # RRULE — recurring event
            rrule_comp = getattr(vevent, 'rrule', None)
            if rrule_comp and rrule_comp.value:
                rrule_str = rrule_comp.value
                if isinstance(rrule_str, dict):
                    # vobject sometimes returns a dict representation
                    parts = []
                    for k, v in rrule_str.items():
                        if isinstance(v, list):
                            v = ','.join(str(x) for x in v)
                        parts.append(f'{k}={v}')
                    rrule_str = ';'.join(parts)
                try:
                    start_dt = vals.get('start') or datetime.utcnow()
                    recurrence_vals = self.env['calendar.recurrence']._rrule_parse(
                        f'FREQ={rrule_str}' if 'FREQ=' not in rrule_str else rrule_str,
                        start_dt,
                    )
                    vals['recurrency'] = True
                    vals.update(recurrence_vals)
                    vals['rrule'] = rrule_str
                except Exception as e:
                    _logger.warning('Could not parse RRULE "%s": %s', rrule_str, e)

            # ATTENDEES
            attendee_components = []
            try:
                attendee_components = list(vevent.attendee_list)
            except AttributeError:
                pass

            partner_ids = []
            # Always include the account owner
            partner_ids.append(account.user_id.partner_id.id)

            for att in attendee_components:
                email_val = att.value
                if email_val.lower().startswith('mailto:'):
                    email_val = email_val[7:]
                partner = self.env['res.partner'].sudo().search(
                    [('email', '=ilike', email_val)], limit=1
                )
                if not partner and account.auto_create_contacts and email_val:
                    cn = att.params.get('CN', [email_val])
                    cn = cn[0] if isinstance(cn, list) else cn
                    partner = self.env['res.partner'].sudo().create({
                        'name': cn or email_val,
                        'email': email_val,
                    })
                if partner:
                    partner_ids.append(partner.id)

            if partner_ids:
                vals['partner_ids'] = [(6, 0, list(set(partner_ids)))]

            # Set organizer to account owner
            vals['user_id'] = account.user_id.id

            return vals

        except Exception as e:
            _logger.warning('Failed to parse VEVENT: %s', e, exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # Manual sync from calendar view (current user)
    # ------------------------------------------------------------------

    @api.model
    def action_sync_current_user(self):
        """Sync all active CalDAV accounts for the current user.

        Called from the CalDAV Sync button in the calendar view header.

        :return: Client notification action with sync results.
        :rtype: dict
        """
        accounts = self.env['caldav.account'].search([
            ('user_id', '=', self.env.uid),
            ('active', '=', True),
        ])
        total_pushed = total_pulled = total_deleted = 0
        for account in accounts:
            try:
                stats = self.sync_account(account)
                total_pushed += stats.get('pushed', 0)
                total_pulled += stats.get('pulled', 0)
                total_deleted += stats.get('deleted', 0)
            except Exception as e:
                _logger.error('Sync error for account %s: %s', account.name, e, exc_info=True)

        if not accounts:
            message = 'No active CalDAV accounts configured. Go to Settings → Calendar to add one.'
            msg_type = 'warning'
        else:
            message = (
                f'CalDAV Sync complete — {total_pushed} pushed, '
                f'{total_pulled} pulled, {total_deleted} deleted.'
            )
            msg_type = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CalDAV Sync',
                'message': message,
                'type': msg_type,
                'sticky': False,
            },
        }
