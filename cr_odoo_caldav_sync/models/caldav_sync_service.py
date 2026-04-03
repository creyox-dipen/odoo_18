# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import re
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
        :return: Dict with counters: {'pushed': N, 'pulled': N, 'deleted': N, 'failed': N}.
        :rtype: dict
        """
        stats_log = {
            'account_id': account.id,
            'sync_date': fields.Datetime.now(),
            'pulled': 0,
            'pushed': 0,
            'deleted': 0,
            'failed': 0,
            'details': '',
            'status': 'success',
        }

        try:
            # --- Phase 1: Pull from CalDAV ---
            pulled_event_ids = set()
            current_ctag = account._get_server_ctag()
            if account.sync_direction in ('bidirectional', 'caldav_to_odoo'):
                _logger.debug('Pulling changes from CalDAV for account %s.', account.name)
                pulled, deleted, pulled_ids, pull_failed, pull_details = self._pull_caldav_changes(account)
                stats_log['pulled'] = pulled
                stats_log['deleted'] = deleted
                stats_log['failed'] += pull_failed
                if pull_details:
                    stats_log['details'] += f"--- PULL ERRORS ---\n{pull_details}\n"
                pulled_event_ids = set(pulled_ids)

            # --- Phase 2: Push to CalDAV ---
            if account.sync_direction in ('bidirectional', 'odoo_to_caldav'):
                _logger.debug('Pushing changes to CalDAV for account %s.', account.name)
                pushed, push_failed, push_details = self._push_odoo_changes(account, skip_ids=pulled_event_ids)
                stats_log['pushed'] = pushed
                stats_log['failed'] += push_failed
                if push_details:
                    stats_log['details'] += f"--- PUSH ERRORS ---\n{push_details}\n"

            # Update CTag and last_sync timestamp
            new_ctag = account._get_server_ctag() or current_ctag
            account.sudo().write({
                'last_ctag': new_ctag,
                'last_sync': fields.Datetime.now(),
            })
            
            if stats_log['failed'] > 0:
                stats_log['status'] = 'partial'

        except Exception as e:
            _logger.error('Critical sync failure for account %s: %s', account.name, e, exc_info=True)
            stats_log['status'] = 'failed'
            stats_log['details'] += f"CRITICAL FAILURE: {str(e)}\n"
        finally:
            # Always create a log record to track progress/failures
            self.env['caldav.sync.log'].sudo().create(stats_log)

        return {
            'pushed': stats_log['pushed'],
            'pulled': stats_log['pulled'],
            'deleted': stats_log['deleted'],
            'failed': stats_log['failed'],
        }

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

        Special handling for Google: when a single occurrence is archived
        ("Only this event" deletion), its start date is recorded as an EXDATE
        on the base series map and the series is queued for re-push.

        :param caldav.account account: Target account.
        :param set skip_ids: Optional set of event IDs to skip (recently pulled).
        :return: Tuple (pushed_count, failed_count, error_details).
        :rtype: tuple[int, int, str]
        """
        pushed = 0
        failed = 0
        details = []
        skip_ids = skip_ids or set()
        owner_partner = account.user_id.partner_id

        # --- GOOGLE ONLY: Phase 2a-pre: detect archived occurrences ---
        # When the user deletes "Only this event" in Odoo, the occurrence is
        # ARCHIVED (active=False), not deleted. Our unlink() hook never fires.
        # We must detect these archived occurrences here and record their start
        # dates as EXDATEs on the base series map so the next push hides them.
        google_force_push_ids = set()  # Base event IDs that must be re-pushed regardless of write_date
        if account.server_type == 'google':
            google_force_push_ids = self._detect_google_archived_occurrences(account)

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
                # Event was archived in Odoo → delete from server.
                # For ANY recurring series: only DELETE if the ENTIRE series is gone
                # (no active occurrences remain). Otherwise the unlink() hook already
                # re-pushed a EXDATE-updated .ics, so we must NOT delete the file.
                if event.recurrence_id:
                    active_remaining = self.env['calendar.event'].sudo().search_count([
                        ('recurrence_id', '=', event.recurrence_id.id),
                        ('active', '=', True),
                    ])
                    if active_remaining > 0:
                        # Series still has active occurrences — EXDATE re-push handles it.
                        # Do NOT unlink the map here. The map's event_id was already
                        # transferred to the new base by the unlink() hook.
                        # Unlinking would cause Phase 2b to push as a brand-new event
                        # (new href/UID) leaving the old CalDAV resource orphaned.
                        _logger.info(
                            'Archived event "%s" (id=%s) still has %s active occurrences. '
                            'Skipping CalDAV DELETE (EXDATE re-push already handled in unlink).',
                            event.name, event.id, active_remaining,
                        )
                        continue  # Keep the map — unlink() re-push already handled this
                    # else: 0 active occurrences remain → fall through and DELETE the series
                try:
                    with self.env.cr.savepoint():
                        _logger.info(
                            'Deleting CalDAV event for archived Odoo event "%s" (id=%s) at %s',
                            event.name, event.id, map_rec.caldav_href,
                        )
                        account._delete_event(map_rec.caldav_href, etag=map_rec.caldav_etag)
                        pushed += 1
                except Exception as e:
                    failed += 1
                    error_msg = f'Delete failed for "{event.name}" (id={event.id}): {str(e)}'
                    _logger.warning(error_msg)
                    details.append(error_msg)
                finally:
                    try:
                        with self.env.cr.savepoint():
                            map_rec.sudo().unlink()
                    except Exception as ue:
                        _logger.warning('Could not unlink map for "%s": %s', event.name, ue)
                    continue

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

        # GOOGLE ONLY: Handle migration of sync mappings if a recurrence base event changed.
        if account.server_type == 'google':
            self._migrate_recurrence_mappings(account)
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
                _logger.debug('[PUSH] SKIP event id=%s "%s": in skip_ids (just pulled).', event.id, event.name)
                continue
            existing_map = existing_maps.get(event.id)
            # Determine if event is new to CalDAV or was modified since last push.
            # For Google: force-push if _detect_google_archived_occurrences flagged this
            # event (ORM cache may hold stale last_odoo_write).
            # NOTE: google_exdates is no longer used as a force-push signal — EXDATEs are
            # pushed immediately in unlink(), so the sync loop only needs to re-push when
            # the event itself has changed (write_date > last_odoo_write).
            if existing_map and event.id not in google_force_push_ids:
                last_push = existing_map.last_odoo_write
                if last_push and event.write_date and event.write_date <= last_push:
                    _logger.debug(
                        '[PUSH] SKIP event id=%s "%s": unchanged (write_date=%s <= last_push=%s).',
                        event.id, event.name, event.write_date, last_push,
                    )
                    continue  # unchanged since last push
            _logger.info('[PUSH] WILL PUSH event id=%s "%s".', event.id, event.name)
            try:
                with self.env.cr.savepoint():
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
                        with self.env.cr.savepoint():
                            new_etag, ical_text = account._fetch_ical_with_etag(existing_map.caldav_href)
                            self._upsert_from_ical(account, existing_map.caldav_href, new_etag, ical_text, existing_map)
                            _logger.info('Auto-recovery pull successful for event "%s".', event.name)
                    except Exception as re:
                        _logger.error('Auto-recovery pull failed for event "%s": %s', event.name, re)
                else:
                    failed += 1
                    error_msg = f'Push failed for "{event.name}" (id={event.id}): {str(e)}'
                    _logger.error(error_msg, exc_info=True)
                    details.append(error_msg)
        return pushed, failed, "\n".join(details)

    @api.model
    def _detect_google_archived_occurrences(self, account):
        """Detect archived recurring occurrences and record them as EXDATEs.

        Returns the set of **base event IDs** whose maps were updated so that
        the push loop can force-push them regardless of ``last_odoo_write``
        staleness in the ORM cache.

        :param caldav.account account: The Google CalDAV account being synced.
        :return: Set of base event IDs to force-push.
        :rtype: set
        """
        owner_partner_id = account.user_id.partner_id.id
        force_push_ids = set()  # Base event IDs whose google_exdates were updated

        # Find all recurrence series where the account owner is an attendee
        all_recurrences = self.env['calendar.recurrence'].sudo().search([])
        relevant_recurrences = all_recurrences.filtered(
            lambda r: r.base_event_id and r.base_event_id.active and any(
                att.partner_id.id == owner_partner_id
                for att in r.base_event_id.attendee_ids
            )
        )

        for recurrence in relevant_recurrences:
            base_event = recurrence.base_event_id  # Current active base (may be promoted)

            # Find the map for the current base event
            base_map = self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
                ('event_id', '=', base_event.id),
            ], limit=1)

            if not base_map:
                # --- Case B: Base was just promoted. Look for an orphaned map on an
                # archived event in this recurrence (the old base's map).
                all_recurrence_event_ids = self.env['calendar.event'].sudo().with_context(
                    active_test=False
                ).search([
                    ('recurrence_id', '=', recurrence.id),
                    ('active', '=', False),
                ]).ids

                if not all_recurrence_event_ids:
                    continue  # No archived events, series not yet synced or no issue

                orphaned_map = self.env['caldav.event.map'].sudo().search([
                    ('account_id', '=', account.id),
                    ('event_id', 'in', all_recurrence_event_ids),
                ], limit=1)

                if not orphaned_map:
                    continue  # Series not synced to Google yet

                old_base = orphaned_map.event_id
                old_base_start_iso = old_base.start.strftime('%Y%m%dT%H%M%SZ') if old_base.start else None

                # CRITICAL: Make the new base event use the SAME caldav_uid as the old
                # map. The CalDAV resource href contains the old UID in its path
                # (e.g. /events/OLD_UUID.ics). If the iCal inside uses a DIFFERENT UID
                # (Occ2's UUID), Google may reject the PUT or delete the old series.
                # By writing the old UID onto the new base event, _push_single_event
                # will generate the correct iCal UID that matches the href.
                if base_event.caldav_uid != orphaned_map.caldav_uid:
                    base_event.sudo().write({'caldav_uid': orphaned_map.caldav_uid})
                    _logger.info(
                        'Google Case B: Updated caldav_uid on new base (id=%s) to match '
                        'old map UID "%s" so href and iCal UID stay consistent.',
                        base_event.id, orphaned_map.caldav_uid,
                    )

                # Transfer the orphaned map to the new (current) base event
                existing_ex = orphaned_map.google_exdates or ''
                ex_list = set(d for d in existing_ex.split(',') if d)
                if old_base_start_iso:
                    ex_list.add(old_base_start_iso)

                orphaned_map.sudo().write({
                    'event_id': base_event.id,
                    'google_exdates': ','.join(sorted(ex_list)),
                    'last_odoo_write': False,  # Force re-push with EXDATE
                    # Clear stale ETag so PUT is unconditional (avoids 412 errors).
                    # The old ETag may be stale if Google updated its representation.
                    'caldav_etag': False,
                })
                _logger.info(
                    'Google Case B: Transferred map (id=%s, href=%s) from archived base '
                    '(id=%s, start=%s) to new base (id=%s) with EXDATE %s.',
                    orphaned_map.id, orphaned_map.caldav_href,
                    old_base.id, old_base_start_iso, base_event.id, old_base_start_iso,
                )
                force_push_ids.add(base_event.id)
                # base_map is now the transferred map; continue to Case A check below
                base_map = orphaned_map

            # --- Case A: Find archived non-base occurrences and record EXDATEs ---
            archived_occurrences = self.env['calendar.event'].sudo().with_context(
                active_test=False
            ).search([
                ('recurrence_id', '=', recurrence.id),
                ('active', '=', False),
                ('id', '!=', base_event.id),
            ])

            if not archived_occurrences:
                continue

            # Build the set of already-recorded EXDATEs to avoid duplicates
            existing_exdates = set(
                d.strip()
                for d in (base_map.google_exdates or '').split(',')
                if d.strip()
            )

            new_exdates = set()
            for occ in archived_occurrences:
                if not occ.start:
                    continue
                start_iso = occ.start.strftime('%Y%m%dT%H%M%SZ')
                if start_iso not in existing_exdates:
                    new_exdates.add(start_iso)
                    _logger.info(
                        'Google EXDATE detected: archived occurrence (id=%s, start=%s) '
                        'in series "%s" — will push EXDATE to Google.',
                        occ.id, start_iso, base_event.name,
                    )

            if new_exdates:
                all_exdates = existing_exdates | new_exdates
                base_map.sudo().write({
                    'google_exdates': ','.join(sorted(all_exdates)),
                    'last_odoo_write': False,
                })
                force_push_ids.add(base_event.id)
                _logger.info(
                    'Updated google_exdates on map (id=%s) for series "%s": %s',
                    base_map.id, base_event.name, ','.join(sorted(all_exdates)),
                )

        return force_push_ids

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

        ical_str = self._odoo_event_to_ical(event, account, existing_map=existing_map)
        href = existing_map.caldav_href if existing_map else self._build_href(account, uid)
        old_etag = existing_map.caldav_etag if existing_map else None

        _logger.info('Pushing event "%s" (id=%s) to %s; If-Match ETag=%s', event.name, event.id, href, old_etag)
        # Log the full iCal for Google — critical for debugging EXDATE/recurrence issues
        if account.server_type == 'google':
            _logger.info(
                'Google iCal payload for event "%s" (id=%s):\n%s',
                event.name, event.id, ical_str,
            )
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
            # NOTE: google_exdates is intentionally NOT cleared here.
            # It is a permanent accumulator of all excluded occurrence dates for
            # this Google series. Clearing it would cause previously-excluded
            # occurrences to reappear on Google when any subsequent push happens.
            # The field is managed exclusively by calendar_event.unlink().
            existing_map.sudo().write(map_vals)
        else:
            # Guard against a race condition (e.g. cron + manual sync running
            # simultaneously) where another transaction already created a map
            # record for this (account_id, caldav_uid) pair, which would
            # trigger a UniqueViolation on the DB constraint.
            existing = self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
                ('caldav_uid', '=', uid),
            ], limit=1)
            if existing:
                existing.write(map_vals)
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
        :return: Tuple (pulled_count, deleted_count, pulled_event_ids, failed_count, error_details).
        :rtype: tuple[int, int, list, int, str]
        """
        pulled = 0
        deleted = 0
        failed = 0
        details = []
        pulled_ids = []

        raw_server_etags = account._get_server_etags()  # {href: etag}

        # Normalize HREFs from server to unquoted absolute URLs
        server_etags = {
            account._resolve_href(href): etag
            for href, etag in raw_server_etags.items()
        }
        _logger.debug('Normalized server HREFs for account %s: %s', account.name, list(server_etags.keys()))

        from urllib.parse import unquote
        existing_maps = {
            unquote(m.caldav_href): m
            for m in self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
            ])
        }
        _logger.debug('Existing Odoo maps for account %s: %s', account.name, list(existing_maps.keys()))

        # Process new and changed events (only if server has events)
        base_url = account.url.rstrip('/')
        for href, server_etag in server_etags.items():
            if account.server_type == 'zoho':
                # Skip the collection folder itself if it appeared in the server candidate list
                norm_href = href.rstrip('/')
                if norm_href == base_url:
                    continue

            existing = existing_maps.get(href)
            if existing:
                _logger.debug('Comparing HREFs for %s: local_etag=%s, server_etag=%s', href, existing.caldav_etag, server_etag)
                if existing.caldav_etag == server_etag:
                    continue  # unchanged on server

                # If the mapped Odoo event is archived, skip pulling it back.
                # The push phase will handle the server-side deletion.
                if existing.event_id and not existing.event_id.active:
                    _logger.debug(
                        'Skipping pull for archived Odoo event href %s — will be deleted in push phase.', href
                    )
                    continue

                # Prioritize Odoo's local changes.
                # If Odoo has a local change that hasn't been pushed yet, skip pulling to avoid
                # overwriting the local change. The push phase will handle the push (and
                # auto-recovery if there's a real conflict on the server side).
                if existing.event_id:
                    last_push = existing.last_odoo_write
                    if last_push and existing.event_id.write_date and \
                       existing.event_id.write_date > last_push:
                        _logger.info(
                            'Skipping pull for %s because Odoo has a pending local change (write_date=%s, last_push=%s).',
                            href, existing.event_id.write_date, last_push
                        )
                        # We MUST update the ETag even if we skip the data pull,
                        # so that the subsequent push uses the latest server ETag for If-Match.
                        existing.sudo().write({'caldav_etag': server_etag})
                        continue
            try:
                _logger.info('Pulling CalDAV event from %s (account %s)', href, account.name)
                with self.env.cr.savepoint():
                    ical_text = account._fetch_ical(href)
                    event = self._upsert_from_ical(account, href, server_etag, ical_text, existing)
                    if event:
                        pulled_ids.append(event.id)
                    pulled += 1
            except Exception as e:
                failed += 1
                error_msg = f'Pull failed for href {href}: {str(e)}'
                _logger.error(error_msg, exc_info=True)
                details.append(error_msg)

        # Archive events deleted on server
        server_hrefs = set(server_etags.keys())
        _logger.info(
            'Deletion check for account %s: server_hrefs=%s, map_hrefs=%s',
            account.name, sorted(server_hrefs), sorted(existing_maps.keys()),
        )
        for href, map_rec in list(existing_maps.items()):
            if href not in server_hrefs:
                try:
                    with self.env.cr.savepoint():
                        if map_rec.event_id:
                            event = map_rec.event_id
                            _logger.info(
                                'Archiving Odoo event "%s" (id=%s) — deleted from CalDAV server.',
                                event.name, event.id,
                            )
                            event.with_context(no_sync=True).sudo().write({'active': False})
                        map_rec.sudo().unlink()
                        deleted += 1
                except Exception as e:
                    failed += 1
                    error_msg = f'Archival failed for {href}: {str(e)}'
                    _logger.warning(error_msg)
                    details.append(error_msg)

        return pulled, deleted, pulled_ids, failed, "\n".join(details)

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
        else:
            # To ensure Odoo handles invitations for ALL attendees (new and existing)
            # as if they were created manually, we must avoid passing ANY suppression
            # keys in the context. Even setting them to False can sometimes trigger
            # an "is present" check in internal Odoo logic.
            ctx_kwargs['mail_notify_force_send'] = True
            ctx_kwargs['force_send'] = True

        CalEvent = self.env['calendar.event'].with_context(**ctx_kwargs).sudo()
        event = None

        if not existing_map and account.server_type == 'zoho':
            # Zoho specific: Fallback if we don't have a map for this HREF.
            # Check if an Odoo event already has this UID (handles renamed HREFs).
            existing_event = CalEvent.search([('caldav_uid', '=', uid_value)], limit=1)
            if existing_event:
                event = existing_event
                # Find and update the existing mapping for this event to the current HREF
                map_rec = self.env['caldav.event.map'].sudo().search([
                    ('account_id', '=', account.id),
                    ('event_id', '=', event.id),
                ], limit=1)
                if map_rec:
                    map_rec.write({'caldav_href': href, 'caldav_etag': server_etag})
                    existing_map = map_rec
                else:
                    # Create missing map record for existing event
                    existing_map = self.env['caldav.event.map'].sudo().create({
                        'account_id': account.id,
                        'event_id': event.id,
                        'caldav_href': href,
                        'caldav_etag': server_etag,
                        'caldav_uid': uid_value,
                    })

        if existing_map and (existing_map.event_id or event):
            event = event or existing_map.event_id
            # Preserve caldav_uid; don't let sync overwrite it
            vals.pop('caldav_uid', None)
            # For Odoo-owned recurring events, DON'T re-apply the RRULE from the
            # server. Doing so triggers `recurrence_update='all_events'` which:
            #   1. Regenerates occurrences (can create extra MX when COUNT=3 + EXDATE)
            #   2. Updates write_date → push detects "changed" → push loop
            # Odoo is the master of the recurrence structure; only EXDATE
            # changes (individual deletions) are synced via the block below.
            if event.recurrence_id:
                vals.pop('rrule', None)
                vals.pop('recurrence_update', None)
            elif vals.get('rrule'):
                vals['recurrence_update'] = 'all_events'
            event.with_context(**ctx_kwargs).write(vals)
        else:
            vals['caldav_uid'] = uid_value
            event = CalEvent.create(vals)
            # Create the map record if it didn't exist (new server event)
            self.env['caldav.event.map'].sudo().create({
                'account_id': account.id,
                'event_id': event.id,
                'caldav_href': href,
                'caldav_etag': server_etag,
                'caldav_uid': uid_value,
            })

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

        # Fallback: Detect mapping by UID if HREF normalization was insufficient.
        # This prevents UniqueViolation on (account_id, caldav_uid) when server HREFs change format.
        if not existing_map:
            existing_map = self.env['caldav.event.map'].sudo().search([
                ('account_id', '=', account.id),
                ('caldav_uid', '=', uid_value),
            ], limit=1)

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
    def _odoo_event_to_ical(self, event, account, existing_map=None):
        """Convert an Odoo ``calendar.event`` to an iCal VCALENDAR string.

        Handles:
        * Single events and recurring events (RRULE on base event only)
        * All-day events (DATE vs DATE-TIME)
        * Location, description (without injecting Odoo attendee details)
        * Attendees (ORGANIZER + ATTENDEE) — only when the event has real attendees
        * Google only: EXDATE injection for deleted occurrences (from existing_map.google_exdates)

        :param calendar.event event: The Odoo event to serialise.
        :param caldav.account account: The CalDAV account (provides owner context).
        :param caldav.event.map|None existing_map: The existing map record, used to
            read persisted EXDATE data for Google recurring events.
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

        # SEQUENCE + LAST-MODIFIED (Zoho specific: signals a fresh modification to the server)
        if account.server_type == 'zoho':
            # Use Odoo's write_date as a monotonically increasing sequence
            # This ensures Zoho treats the update as a new revision and refreshes its UI.
            write_dt = event.write_date or datetime.utcnow()
            vevent.add('sequence').value = str(int(write_dt.timestamp()))
            vevent.add('last-modified').value = write_dt.replace(tzinfo=pytz.utc) if write_dt.tzinfo is None else write_dt

        # DTSTART / DTEND
        # When the first occurrence (base) is deleted, Odoo promotes the next one to "base".
        # If we push that new date as DTSTART, COUNT-based RRULEs shift forward, adding
        # phantom events at the end (applies to Google AND Radicale/Baïkal/Nextcloud).
        # We find the ORIGINAL series start date from stored EXDATEs and use it as DTSTART,
        # keeping the RRULE anchored to the original start while EXDATE hides occurrence 1.
        original_start = event.start
        if existing_map and existing_map.google_exdates:
            try:
                exdates = [
                    datetime.strptime(d.strip(), '%Y%m%dT%H%M%SZ')
                    for d in existing_map.google_exdates.split(',')
                    if d.strip()
                ]
                if exdates:
                    min_ex = min(exdates)
                    if min_ex < original_start:
                        _logger.info(
                            '[ICAL] Shifting DTSTART back to original series start %s '
                            '(current base start is %s) to preserve recurrence count. '
                            'Account: %s.',
                            min_ex, original_start, account.name,
                        )
                        original_start = min_ex
            except Exception as e:
                _logger.warning('Could not calculate original DTSTART from EXDATEs: %s', e)

        # Calculate duration based on the actual occurrence being pushed
        duration = event.stop - event.start
        original_stop = original_start + duration

        if event.allday:
            # For all-day events, use dates
            dtstart = vevent.add('dtstart')
            dtstart.value = original_start.date()
            dtend = vevent.add('dtend')
            dtend.value = original_stop.date() + timedelta(days=1)
        else:
            # For timed events, use UTC datetimes
            start_utc = _to_utc_naive(original_start) or datetime.utcnow()
            stop_utc = _to_utc_naive(original_stop) or (start_utc + timedelta(hours=1))
            
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
        
        # CLASS — privacy mapping
        _privacy_to_class = {'public': 'PUBLIC', 'private': 'PRIVATE', 'confidential': 'CONFIDENTIAL'}
        class_val = _privacy_to_class.get(event.privacy or 'public', 'PUBLIC')
        vevent.add('class').value = class_val

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
                # Include EXDATE properties from Odoo's native rrule field.
                # vobject requires .value to be a list of date/datetime objects,
                # NOT a raw string. Parse accordingly for all server types.
                elif line.upper().startswith('EXDATE:'):
                    exdate_value = line[len('EXDATE:'):].strip()
                    if event.allday:
                        # All-day events: EXDATE must be a plain date object
                        try:
                            ex_dt = datetime.strptime(exdate_value, '%Y%m%dT%H%M%SZ').date()
                            vevent.add('exdate').value = [ex_dt]
                        except ValueError:
                            try:
                                ex_dt = datetime.strptime(exdate_value, '%Y%m%d').date()
                                vevent.add('exdate').value = [ex_dt]
                            except ValueError:
                                _logger.warning('Could not parse EXDATE (all-day) "%s".', exdate_value)
                    else:
                        # Timed events: EXDATE must be a UTC-aware datetime object
                        try:
                            ex_dt = datetime.strptime(exdate_value, '%Y%m%dT%H%M%SZ').replace(tzinfo=pytz.utc)
                            vevent.add('exdate').value = [ex_dt]
                        except ValueError:
                            _logger.warning('Could not parse EXDATE (timed) "%s".', exdate_value)

            # Read persisted EXDATEs stored on the event map for ALL server types.
            # For Google: written by unlink()/detect_archived() into google_exdates.
            # For Basic Auth (Radicale/Baïkal): written by unlink() Case A/B above.
            # The field name 'google_exdates' is reused for all server types to avoid
            # a database migration — it now tracks per-server pending EXDATEs.
            if existing_map and existing_map.google_exdates:
                _logger.debug(
                    '[ICAL] Injecting stored EXDATEs for "%s" (account: %s): %s',
                    event.name, account.name, existing_map.google_exdates,
                )
                for iso_dt in existing_map.google_exdates.split(','):
                    iso_dt = iso_dt.strip()
                    if not iso_dt or iso_dt in raw:
                        continue  # Already in RRULE or empty
                    try:
                        ex_dt = datetime.strptime(iso_dt, '%Y%m%dT%H%M%SZ').replace(tzinfo=pytz.utc)
                        ex = vevent.add('exdate')
                        if event.allday:
                            ex.value = [ex_dt.date()]
                        else:
                            ex.value = [ex_dt]
                    except ValueError:
                        _logger.warning('Could not parse stored EXDATE: %s', iso_dt)

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

            if account.server_type == 'google':
                from urllib.parse import urlparse
                google_email = None
                try:
                    path_parts = urlparse(account.url).path.strip('/').split('/')
                    if len(path_parts) >= 3:
                        google_email = path_parts[2]
                except Exception:
                    pass
                org_email = google_email or owner.email or account.username
            elif account.server_type == 'zoho':
                # Zoho URL is an opaque token — use account.username (Zoho email)
                # as ORGANIZER, otherwise Zoho rejects the PUT with 409.
                org_email = account.username or owner.email
            else:
                org_email = owner.email or account.username

            org.value = f'mailto:{org_email}'
            org.params['CN'] = [owner.name or org_email]

            for partner in event.partner_ids:
                if not partner.email:
                    continue
                att = vevent.add('attendee')
                att.value = f'mailto:{partner.email}'
                att.params['CN'] = [partner.name or partner.email]
                att.params['PARTSTAT'] = ['ACCEPTED']

        # VALARM — one subcomponent per alarm/reminder
        for alarm in event.alarm_ids:
            """Add a VALARM for each reminder configured on the event."""
            valarm = vevent.add('valarm')
            # Zoho: RFC 5545 has no distinct "notification" ACTION (only EMAIL/DISPLAY/AUDIO).
            # Zoho maps DISPLAY → popup. Add X-ACTION:NOTIFICATION so Zoho shows it
            # as a notification instead. Other servers are unaffected.
            if account.server_type == 'zoho' and alarm.alarm_type == 'notification':
                valarm.add('action').value = 'DISPLAY'
                valarm.add('x-action').value = 'NOTIFICATION'
            else:
                action = 'EMAIL' if alarm.alarm_type == 'email' else 'DISPLAY'
                valarm.add('action').value = action
            valarm.add('description').value = alarm.name or 'Reminder'

            # Use timedelta for TRIGGER; vobject will serialize it to ISO 8601 duration
            # Negative means "before event start" (default for PTH, PTM etc.)
            minutes = alarm.duration_minutes or 0
            valarm.add('trigger').value = timedelta(minutes=-minutes)

        return cal.serialize()

    # ------------------------------------------------------------------
    # iCal parsing (CalDAV → Odoo)
    # ------------------------------------------------------------------

    @api.model
    def _migrate_recurrence_mappings(self, account):
        """Finds sync mappings for archived base events and transfers them to new active bases.

        In Odoo, if a base event of a recurrence is deleted, Odoo might assign a new
        base event to the recurrence record. We must ensure our CalDAV mapping follows
        the recurrence to the new base event instead of being lost.

        :param account: The caldav.account record being synced.
        """
        inactive_maps = self.env['caldav.event.map'].sudo().search([
            ('account_id', '=', account.id),
            ('event_id.active', '=', False),
        ])
        for map_rec in inactive_maps:
            old_event = map_rec.event_id
            # If the old event was part of a recurrence that still exists
            if old_event.recurrence_id:
                new_base = old_event.recurrence_id.base_event_id
                if new_base and new_base.active and new_base.id != old_event.id:
                    _logger.info(
                        'Migrating CalDAV mapping for recurrence %s: %s -> %s',
                        old_event.recurrence_id.id, old_event.id, new_base.id
                    )
                    map_rec.sudo().write({'event_id': new_base.id})

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

            # DESCRIPTION (Strip Google Meet metadata and extract link)
            desc_comp = getattr(vevent, 'description', None)
            if desc_comp and desc_comp.value:
                description = desc_comp.value
                
                # Check if it's a Google account to apply specific stripping.
                # This ensures zero impact on other servers like Radicale or Nextcloud.
                if account.server_type == 'google':
                    # 1. Extract the Meet URL if it exists anywhere in the description.
                    url_search = re.search(r'https://meet\.google\.com/[a-z0-9\-]+', description)
                    if url_search:
                        vals['videocall_location'] = url_search.group(0)
                        _logger.debug('Extracted Google Meet URL: %s', vals['videocall_location'])
                    
                    # 2. Look for the start of the Google-injected metadata block.
                    # It usually starts with "Join with Google Meet" or the separator "-::~".
                    # We remove everything from the first marker found to the end of the string.
                    markers = ['Join with Google Meet', '-::~']
                    first_idx = len(description)
                    found = False
                    for marker in markers:
                        idx = description.find(marker)
                        if idx != -1:
                            first_idx = min(first_idx, idx)
                            found = True
                    
                    if found:
                        description = description[:first_idx].strip()
                
                # Store as simple HTML paragraph
                if description:
                    vals['description'] = f'<p>{description.replace(chr(10), "<br/>")}</p>'
                else:
                    vals['description'] = False
                
                # Store as simple HTML paragraph
                if description:
                    vals['description'] = f'<p>{description.replace(chr(10), "<br/>")}</p>'
                else:
                    vals['description'] = False

            # CLASS — iCal privacy mapping
            _class_to_privacy = {'PUBLIC': 'public', 'PRIVATE': 'private', 'CONFIDENTIAL': 'confidential'}
            class_comp = getattr(vevent, 'class', None)
            if class_comp and class_comp.value:
                privacy = _class_to_privacy.get(class_comp.value.upper(), 'public')
                vals['privacy'] = privacy

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

            # VALARM — parse reminders from CalDAV and map to Odoo alarm_ids
            alarm_ids = []
            try:
                for component in vevent.components():
                    if component.name != 'VALARM':
                        continue
                    trigger_comp = getattr(component, 'trigger', None)
                    action_comp = getattr(component, 'action', None)
                    if not trigger_comp:
                        continue
                    trigger_val = trigger_comp.value
                    # trigger_val is a timedelta (negative = before event)
                    if hasattr(trigger_val, 'total_seconds'):
                        total_secs = abs(trigger_val.total_seconds())
                        trigger_minutes = int(total_secs // 60)
                    else:
                        continue
                    action_str = (action_comp.value if action_comp else 'DISPLAY').upper()
                    alarm_type = 'email' if action_str == 'EMAIL' else 'notification'
                    # Find the best matching alarm in Odoo
                    alarm = self.env['calendar.alarm'].sudo().search([
                        ('alarm_type', '=', alarm_type),
                        ('duration_minutes', '=', trigger_minutes),
                    ], limit=1)
                    if not alarm:
                        # Fallback: closest match by duration regardless of type
                        alarm = self.env['calendar.alarm'].sudo().search(
                            [('duration_minutes', '=', trigger_minutes)], limit=1
                        )
                    if not alarm and trigger_minutes > 0:
                        # Fallback: find closest alarm by duration
                        all_alarms = self.env['calendar.alarm'].sudo().search([])
                        alarm = min(
                            all_alarms,
                            key=lambda a: abs(a.duration_minutes - trigger_minutes),
                            default=None,
                        )
                    if alarm:
                        alarm_ids.append(alarm.id)
            except Exception as ex:
                _logger.warning('Could not parse VALARM: %s', ex)
            if alarm_ids:
                vals['alarm_ids'] = [(6, 0, list(set(alarm_ids)))]

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
