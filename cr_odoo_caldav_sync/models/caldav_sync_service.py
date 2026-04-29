# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import hashlib
import logging
import re
import uuid
import pytz
from datetime import datetime, timedelta, timezone, date
from odoo.tools import html2plaintext
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    import vobject
except ImportError:
    vobject = None
    _logger.warning("vobject is not available; CalDAV iCal parsing will be disabled.")


def _to_utc_naive(dt_obj):
    """Convert a timezone-aware or naive datetime to a UTC-naive datetime."""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        if dt_obj.tzinfo is not None:
            return dt_obj.astimezone(timezone.utc).replace(tzinfo=None)
        return dt_obj
    return datetime(dt_obj.year, dt_obj.month, dt_obj.day)


def _is_date_only(dt_obj):
    """Return True if dt_obj is a plain date (not datetime) — indicating an all-day event."""
    return isinstance(dt_obj, date) and not isinstance(dt_obj, datetime)


class CalDAVSyncService(models.AbstractModel):
    """Stateless service model that orchestrates CalDAV synchronisation."""

    _name = "caldav.sync.service"
    _description = "CalDAV Sync Service"

    @api.model
    def _build_google_ical_with_overrides(
        self, current_ical, base_event, all_occs, account
    ):
        """Build an iCal string containing the base VEVENT plus Google RECURRENCE-ID overrides."""
        if vobject is None:
            raise RuntimeError("vobject required.")

        cal = vobject.readOne(current_ical)

        server_base = None
        for comp in cal.components():
            if comp.name == "VEVENT" and not hasattr(comp, "recurrence_id"):
                server_base = comp
                break

        server_tz = pytz.utc
        if server_base:
            dts_val = server_base.dtstart.value
            if (
                not _is_date_only(dts_val)
                and hasattr(dts_val, "tzinfo")
                and dts_val.tzinfo
            ):
                try:
                    server_tz = dts_val.tzinfo
                except Exception:
                    server_tz = pytz.utc

        seq = 1
        if server_base:
            if hasattr(server_base, "sequence"):
                try:
                    seq = int(server_base.sequence.value) + 1
                    server_base.sequence.value = str(seq)
                except Exception:
                    seq = 1
                    server_base.sequence.value = "1"
            else:
                server_base.add("sequence").value = "1"
                seq = 1

        push_dtstamp = datetime.now(pytz.utc)
        if server_base:
            if hasattr(server_base, "dtstamp"):
                server_base.dtstamp.value = push_dtstamp
            else:
                server_base.add("dtstamp").value = push_dtstamp

        # CRITICAL: If upgrading from single to recurring, server_base might lack RRULE.
        # We must ensure the master VEVENT has the RRULE so RECURRENCE-ID overrides are valid.
        if server_base and base_event.recurrence_id:
            raw_rrule = base_event.recurrence_id.rrule or ""
            rrule_val = None
            for line in raw_rrule.splitlines():
                if line.upper().startswith("RRULE:"):
                    rrule_val = line[6:].strip()
                    break
            if not rrule_val and raw_rrule:
                rrule_val = raw_rrule.lstrip("RRULE:").strip()

            if rrule_val:
                if hasattr(server_base, "rrule"):
                    server_base.rrule.value = rrule_val
                else:
                    server_base.add("rrule").value = rrule_val

        # Build set of starts being replaced so we can drop stale server overrides
        updating_starts_utc = set()
        for occ, _ in all_occs:
            if occ.allday:
                orig_dt = occ.caldav_original_start or occ.start
                updating_starts_utc.add(orig_dt.date())
            else:
                updating_starts_utc.add(
                    _to_utc_naive(occ.caldav_original_start or occ.start)
                )

        # Inject EXDATEs from the map if any
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("event_id", "=", base_event.id),
                    ("caldav_uid", "=", base_event.caldav_uid),
                ],
                limit=1,
            )
        )
        if base_map and base_map.google_exdates:
            for iso_dt in base_map.google_exdates.split(","):
                iso_dt = iso_dt.strip()
                if not iso_dt:
                    continue
                try:
                    ex_dt_naive = datetime.strptime(iso_dt, "%Y%m%dT%H%M%SZ")
                    ex_dt = pytz.utc.localize(ex_dt_naive)
                    if base_event.allday:
                        ex_val = ex_dt.date()
                    else:
                        ex_val = ex_dt

                    if ex_val in updating_starts_utc:
                        # If we are pushing an override for this date, do NOT also exdate it!
                        continue

                    if hasattr(server_base, "exdate"):
                        if ex_val not in server_base.exdate.value:
                            server_base.exdate.value.append(ex_val)
                    else:
                        server_base.add("exdate").value = [ex_val]
                except Exception:
                    pass

        if "vevent" in cal.contents:
            new_vevents = []
            for ve in cal.contents["vevent"]:
                if hasattr(ve, "recurrence_id"):
                    rid_val = ve.recurrence_id.value
                    if _is_date_only(rid_val):
                        rid_key = rid_val
                    elif hasattr(rid_val, "tzinfo") and rid_val.tzinfo:
                        rid_key = rid_val.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        rid_key = (
                            rid_val.replace(tzinfo=None)
                            if hasattr(rid_val, "replace")
                            else rid_val
                        )

                    if rid_key in updating_starts_utc:
                        continue
                new_vevents.append(ve)
            cal.contents["vevent"] = new_vevents

        uid = base_event.caldav_uid
        for occ, _ in all_occs:
            ovr = vobject.newFromBehavior("vevent")
            ovr.add("uid").value = uid
            ovr.add("dtstamp").value = datetime.now(pytz.utc)
            ovr.add("sequence").value = str(seq)
            ovr.add("summary").value = occ.name or ""

            if occ.allday:
                ovr.add("recurrence-id").value = (
                    occ.caldav_original_start or occ.start
                ).date()
                ovr.add("dtstart").value = occ.start.date()
                ovr.add("dtend").value = occ.stop.date() + timedelta(days=1)
            else:
                occ_start_orig = _to_utc_naive(occ.caldav_original_start or occ.start)
                occ_start_utc = _to_utc_naive(occ.start)
                occ_stop_utc = _to_utc_naive(occ.stop)

                try:
                    occ_start_srv = pytz.utc.localize(occ_start_utc).astimezone(
                        server_tz
                    )
                    occ_stop_srv = pytz.utc.localize(occ_stop_utc).astimezone(server_tz)
                    occ_rid_srv = pytz.utc.localize(occ_start_orig).astimezone(
                        server_tz
                    )
                except Exception:
                    occ_start_srv = occ_start_utc.replace(tzinfo=pytz.utc)
                    occ_stop_srv = occ_stop_utc.replace(tzinfo=pytz.utc)
                    occ_rid_srv = occ_start_orig.replace(tzinfo=pytz.utc)

                _logger.info(
                    '[GOOGLE] occ id=%s "%s": RECURRENCE-ID=%s DTSTART=%s caldav_original_start=%s occ.start=%s',
                    occ.id,
                    occ.name,
                    occ_rid_srv,
                    occ_start_srv,
                    occ.caldav_original_start,
                    occ.start,
                )
                ovr.add("recurrence-id").value = occ_rid_srv
                ovr.add("dtstart").value = occ_start_srv
                ovr.add("dtend").value = occ_stop_srv

            if occ.location:
                ovr.add("location").value = occ.location

            if occ.description:
                plain = html2plaintext(occ.description).strip()
                if plain:
                    ovr.add("description").value = plain

            cal.add(ovr)
            _logger.info(
                '[GOOGLE] Built RECURRENCE-ID override for occ "%s" (id=%s)',
                occ.name,
                occ.id,
            )

        return cal.serialize()

    @api.model
    def _build_zoho_ical_with_overrides(
        self, current_ical, base_event, all_occs, account
    ):
        """Build an iCal string containing base series + RECURRENCE-ID overrides for Zoho."""
        if vobject is None:
            raise RuntimeError("vobject required.")

        cal = vobject.readOne(current_ical)

        server_base = None
        for comp in cal.components():
            if comp.name == "VEVENT" and not hasattr(comp, "recurrence_id"):
                server_base = comp
                break

        # Ensure RRULE exists for Zoho series validation
        if server_base and base_event.recurrence_id:
            raw_rrule = base_event.recurrence_id.rrule or ""
            rrule_val = None
            for line in raw_rrule.splitlines():
                if line.upper().startswith("RRULE:"):
                    rrule_val = line[6:].strip()
                    break
            if not rrule_val and raw_rrule:
                rrule_val = raw_rrule.lstrip("RRULE:").strip()

            if rrule_val:
                if hasattr(server_base, "rrule"):
                    server_base.rrule.value = rrule_val
                else:
                    server_base.add("rrule").value = rrule_val

        # Use a high sequence number (timestamp) to ensure it's always increasing
        seq = int(datetime.utcnow().timestamp())

        if server_base:
            if hasattr(server_base, "sequence"):
                server_base.sequence.value = str(seq)
            else:
                server_base.add("sequence").value = str(seq)

            # Zoho specific last-modified timestamp
            if hasattr(server_base, "last_modified"):
                server_base.last_modified.value = datetime.now(pytz.utc)
            else:
                server_base.add("last-modified").value = datetime.now(pytz.utc)

            # Update base VEVENT content fields from Odoo base event
            if hasattr(server_base, "summary"):
                server_base.summary.value = base_event.name or ""
            else:
                server_base.add("summary").value = base_event.name or ""

            if base_event.location:
                if hasattr(server_base, "location"):
                    server_base.location.value = base_event.location
                else:
                    server_base.add("location").value = base_event.location

            if base_event.description:
                plain = html2plaintext(base_event.description).strip()
                if plain:
                    if hasattr(server_base, "description"):
                        server_base.description.value = plain
                    else:
                        server_base.add("description").value = plain

        updating_starts_utc = set()
        for occ, _ in all_occs:
            if occ.allday:
                updating_starts_utc.add((occ.caldav_original_start or occ.start).date())
            else:
                updating_starts_utc.add(
                    _to_utc_naive(occ.caldav_original_start or occ.start)
                )

        # Inject EXDATEs from the map if any
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("event_id", "=", base_event.id),
                    ("caldav_uid", "=", base_event.caldav_uid),
                ],
                limit=1,
            )
        )
        if base_map and base_map.google_exdates:
            for iso_dt in base_map.google_exdates.split(","):
                iso_dt = iso_dt.strip()
                if not iso_dt:
                    continue
                try:
                    ex_dt_naive = datetime.strptime(iso_dt, "%Y%m%dT%H%M%SZ")
                    ex_dt = pytz.utc.localize(ex_dt_naive)
                    if base_event.allday:
                        ex_val = ex_dt.date()
                    else:
                        ex_val = ex_dt

                    if ex_val in updating_starts_utc:
                        # If we are pushing an override for this date, do NOT also exdate it!
                        continue

                    if hasattr(server_base, "exdate"):
                        if ex_val not in server_base.exdate.value:
                            server_base.exdate.value.append(ex_val)
                    else:
                        server_base.add("exdate").value = [ex_val]
                except Exception:
                    pass

        # Build set of EXDATEd dates to also purge stale server-side overrides
        exdated_dates = set()
        if server_base and hasattr(server_base, "rrule"):
            raw_rrule = (
                base_event.recurrence_id.rrule if base_event.recurrence_id else ""
            )
            for line in (raw_rrule or "").splitlines():
                if line.strip().upper().startswith("EXDATE:"):
                    exdate_val = line.strip()[len("EXDATE:") :]
                    try:
                        from datetime import date as _date

                        ex_d = datetime.strptime(
                            exdate_val.strip(), "%Y%m%dT%H%M%SZ"
                        ).date()
                        exdated_dates.add(ex_d)
                    except Exception:
                        try:
                            ex_d = datetime.strptime(
                                exdate_val.strip(), "%Y%m%d"
                            ).date()
                            exdated_dates.add(ex_d)
                        except Exception:
                            pass

        # Also collect from Odoo archived occurrences directly
        if base_event.recurrence_id:
            archived_occs = (
                self.env["calendar.event"]
                .sudo()
                .with_context(active_test=False)
                .search(
                    [
                        ("recurrence_id", "=", base_event.recurrence_id.id),
                        ("active", "=", False),
                        ("id", "!=", base_event.id),
                    ]
                )
            )
            for arch_occ in archived_occs:
                orig = arch_occ.caldav_original_start or arch_occ.start
                if orig:
                    exdated_dates.add(orig.date() if hasattr(orig, "date") else orig)

        if "vevent" in cal.contents:
            new_vevents = []
            for ve in cal.contents["vevent"]:
                if hasattr(ve, "recurrence_id"):
                    rid_val = ve.recurrence_id.value
                    # Normalize rid_key for date comparison
                    if _is_date_only(rid_val):
                        rid_key = rid_val
                        rid_date = rid_val
                    else:
                        rid_key = (
                            rid_val.astimezone(timezone.utc).replace(tzinfo=None)
                            if hasattr(rid_val, "astimezone")
                            else rid_val
                        )
                        rid_date = rid_key.date() if hasattr(rid_key, "date") else None
                    # Drop if we're replacing it with a new override
                    if rid_key in updating_starts_utc:
                        continue
                    # Drop if this date is now EXDATEd (occurrence was deleted)
                    if rid_date and rid_date in exdated_dates:
                        _logger.info(
                            "[ZOHO] Removing stale server RECURRENCE-ID override for EXDATEd date %s",
                            rid_date,
                        )
                        continue
                new_vevents.append(ve)
            cal.contents["vevent"] = new_vevents

        uid = base_event.caldav_uid
        for occ, _ in all_occs:
            if occ.id == base_event.id:
                # The master VEVENT already contains the latest base event data.
                continue

            ovr = vobject.newFromBehavior("vevent")
            ovr.add("uid").value = uid
            ovr.add("dtstamp").value = datetime.now(pytz.utc)
            ovr.add("sequence").value = str(seq)
            ovr.add("summary").value = occ.name or ""
            ovr.add("class").value = "PUBLIC"
            ovr.add("status").value = "CONFIRMED"
            ovr.add("transp").value = "OPAQUE"
            if occ.allday:
                ovr.add("recurrence-id").value = (
                    occ.caldav_original_start or occ.start
                ).date()
                ovr.add("dtstart").value = occ.start.date()
                ovr.add("dtend").value = occ.stop.date() + timedelta(days=1)
            else:
                orig_start = _to_utc_naive(occ.caldav_original_start or occ.start)
                ovr.add("recurrence-id").value = orig_start.replace(tzinfo=pytz.utc)
                ovr.add("dtstart").value = _to_utc_naive(occ.start).replace(
                    tzinfo=pytz.utc
                )
                ovr.add("dtend").value = _to_utc_naive(occ.stop).replace(
                    tzinfo=pytz.utc
                )

            if occ.location:
                ovr.add("location").value = occ.location
            if occ.description:
                plain = html2plaintext(occ.description).strip()
                if plain:
                    ovr.add("description").value = plain

            cal.add(ovr)

        return cal.serialize()

    @api.model
    def _build_google_base_edit(self, current_ical, base_event, account):
        """Edit base VEVENT of Google recurring series in-place. ."""
        if vobject is None:
            raise RuntimeError("vobject required.")

        cal = vobject.readOne(current_ical)

        server_base = None
        for comp in cal.components():
            if comp.name == "VEVENT" and not hasattr(comp, "recurrence_id"):
                server_base = comp
                break

        if not server_base:
            raise RuntimeError("No base VEVENT found in Google iCal.")

        # Inject EXDATEs from the map if any
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("event_id", "=", base_event.id),
                    ("caldav_uid", "=", base_event.caldav_uid),
                ],
                limit=1,
            )
        )
        if base_map and base_map.google_exdates:
            for iso_dt in base_map.google_exdates.split(","):
                iso_dt = iso_dt.strip()
                if not iso_dt:
                    continue
                try:
                    ex_dt_naive = datetime.strptime(iso_dt, "%Y%m%dT%H%M%SZ")
                    ex_dt = pytz.utc.localize(ex_dt_naive)
                    ex_val = ex_dt.date() if base_event.allday else ex_dt

                    if hasattr(server_base, "exdate"):
                        if ex_val not in server_base.exdate.value:
                            server_base.exdate.value.append(ex_val)
                    else:
                        server_base.add("exdate").value = [ex_val]
                except Exception:
                    pass

        orig_dtstart = server_base.dtstart.value
        orig_naive = (
            datetime(orig_dtstart.year, orig_dtstart.month, orig_dtstart.day)
            if _is_date_only(orig_dtstart)
            else _to_utc_naive(orig_dtstart)
        )
        base_start_naive = _to_utc_naive(base_event.start)
        base_stop_naive = _to_utc_naive(base_event.stop)

        server_tz = pytz.utc
        if (
            not _is_date_only(orig_dtstart)
            and hasattr(orig_dtstart, "tzinfo")
            and orig_dtstart.tzinfo
        ):
            try:
                server_tz = orig_dtstart.tzinfo
            except Exception:
                pass
        if hasattr(server_base, "sequence"):
            try:
                server_base.sequence.value = str(int(server_base.sequence.value) + 1)
            except:
                server_base.sequence.value = "1"
        else:
            server_base.add("sequence").value = "1"
        if hasattr(server_base, "summary"):
            server_base.summary.value = base_event.name or ""
        else:
            server_base.add("summary").value = base_event.name or ""

        if base_event.location:
            if hasattr(server_base, "location"):
                server_base.location.value = base_event.location
            else:
                server_base.add("location").value = base_event.location

        if base_event.description:
            plain = html2plaintext(base_event.description).strip()
            if plain:
                if hasattr(server_base, "description"):
                    server_base.description.value = plain
                else:
                    server_base.add("description").value = plain

        if orig_naive != base_start_naive:
            if _is_date_only(orig_dtstart):
                server_base.dtstart.value = base_event.start.date()
                if hasattr(server_base, "dtend"):
                    server_base.dtend.value = base_event.stop.date() + timedelta(days=1)
            else:
                try:
                    new_dtstart = pytz.utc.localize(base_start_naive).astimezone(
                        server_tz
                    )
                    new_dtend = pytz.utc.localize(base_stop_naive).astimezone(server_tz)
                except Exception:
                    new_dtstart = datetime(
                        base_start_naive.year,
                        base_start_naive.month,
                        base_start_naive.day,
                        base_start_naive.hour,
                        base_start_naive.minute,
                        base_start_naive.second,
                        tzinfo=pytz.utc,
                    )
                    new_dtend = datetime(
                        base_stop_naive.year,
                        base_stop_naive.month,
                        base_stop_naive.day,
                        base_stop_naive.hour,
                        base_stop_naive.minute,
                        base_stop_naive.second,
                        tzinfo=pytz.utc,
                    )
                server_base.dtstart.value = new_dtstart
                if hasattr(server_base, "dtend"):
                    server_base.dtend.value = new_dtend
                elif hasattr(server_base, "duration"):
                    server_base.duration.value = base_event.stop - base_event.start

            if "vevent" in cal.contents:
                cal.contents["vevent"] = [
                    ve
                    for ve in cal.contents["vevent"]
                    if not hasattr(ve, "recurrence_id")
                ]

        return cal.serialize()

    @api.model
    def _cron_sync_all(self):
        """Cron entry point: sync every active CalDAV account."""
        accounts = self.env["caldav.account"].search([("active", "=", True)])
        for account in accounts:
            try:
                self.sync_account(account)
            except Exception as e:
                _logger.error(
                    "CalDAV auto-sync failed for account %s (id=%s): %s",
                    account.name,
                    account.id,
                    e,
                    exc_info=True,
                )

    @api.model
    def sync_account(self, account):
        """Perform a full incremental sync for one CalDAV account."""
        _logger.info("Starting sync for account: %s (id=%s)", account.name, account.id)
        stats_log = {
            "account_id": account.id,
            "sync_date": fields.Datetime.now(),
            "pulled": 0,
            "pushed": 0,
            "deleted": 0,
            "failed": 0,
            "details": "",
            "status": "success",
        }

        try:
            pulled_event_ids = set()
            current_ctag = account._get_server_ctag()
            _logger.debug("Current server CTag: %s", current_ctag)
            if account.sync_direction in ("bidirectional", "caldav_to_odoo"):
                _logger.debug(
                    "Pulling changes from CalDAV for account %s.", account.name
                )
                pulled, deleted, pulled_ids, pull_failed, pull_details = (
                    self._pull_caldav_changes(account)
                )
                stats_log["pulled"] = pulled
                stats_log["deleted"] = deleted
                stats_log["failed"] += pull_failed
                if pull_details:
                    stats_log["details"] += f"--- PULL ERRORS ---\n{pull_details}\n"
                pulled_event_ids = set(pulled_ids)

            if account.sync_direction in ("bidirectional", "odoo_to_caldav"):
                _logger.debug("Pushing changes to CalDAV for account %s.", account.name)
                pushed, push_failed, push_details = self._push_odoo_changes(
                    account, skip_ids=pulled_event_ids
                )
                stats_log["pushed"] += pushed
                stats_log["failed"] += push_failed
                if push_details:
                    stats_log["details"] += f"--- PUSH ERRORS ---\n{push_details}\n"

            new_ctag = account._get_server_ctag() or current_ctag
            account.sudo().write(
                {
                    "last_ctag": new_ctag,
                    "last_sync": fields.Datetime.now(),
                }
            )

            if stats_log["failed"] > 0:
                stats_log["status"] = "partial"

        except Exception as e:
            _logger.error(
                "Critical sync failure for account %s: %s",
                account.name,
                e,
                exc_info=True,
            )
            stats_log["status"] = "failed"
            stats_log["details"] += f"CRITICAL FAILURE: {str(e)}\n"
        finally:
            self.env["caldav.sync.log"].sudo().create(stats_log)

        return {
            "pushed": stats_log["pushed"],
            "pulled": stats_log["pulled"],
            "deleted": stats_log["deleted"],
            "failed": stats_log["failed"],
        }

    @api.model
    def _pull_caldav_changes(self, account):
        """Pull new and changed events from the CalDAV server into Odoo."""
        pulled = 0
        deleted = 0
        failed = 0
        details = []
        pulled_ids = []

        raw_server_etags = account._get_server_etags()
        server_etags = {
            account._resolve_href(href): etag for href, etag in raw_server_etags.items()
        }

        from urllib.parse import unquote

        all_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                ]
            )
        )
        existing_maps = {}
        for m in all_maps:
            href_key = unquote(m.caldav_href)
            if account.server_type in ("zoho", "google") and "__occ_" in (
                m.caldav_uid or ""
            ):
                continue
            if href_key not in existing_maps:
                existing_maps[href_key] = m

        base_url = account.url.rstrip("/")
        for href, server_etag in server_etags.items():
            norm_href = href.rstrip("/")
            if norm_href == base_url:
                continue

            if account.server_type == "icloud" and not href.endswith(".ics"):
                continue

            existing = existing_maps.get(href)

            if account.server_type == "zoho":
                try:
                    zoho_ical_text = account._fetch_ical(href)
                    _prefixes = (
                        "SUMMARY",
                        "DTSTART",
                        "DTEND",
                        "RRULE",
                        "RECURRENCE-ID",
                        "EXDATE",
                        "LOCATION",
                        "DESCRIPTION",
                        "STATUS",
                    )
                    normalized = "\n".join(
                        line.strip()
                        for line in zoho_ical_text.splitlines()
                        if any(line.strip().startswith(p) for p in _prefixes)
                    )
                    content_hash = (
                        "zoho_hash:" + hashlib.sha256(normalized.encode()).hexdigest()
                    )

                    if existing and existing.caldav_etag == content_hash:
                        continue

                    if existing and existing.event_id:
                        # Check for structural changes: if Zoho is now recurring but Odoo is not,
                        # we MUST pull regardless of write_date to avoid overwriting the series.
                        is_zoho_recurring = "RRULE" in (zoho_ical_text or "")
                        odoo_is_recurring = existing.event_id.recurrency

                        force_pull = is_zoho_recurring and not odoo_is_recurring

                        if not force_pull:
                            has_pending = not existing.last_odoo_write or (
                                existing.event_id.write_date
                                and existing.event_id.write_date
                                > existing.last_odoo_write
                            )
                            if not has_pending and existing.event_id.recurrence_id:
                                self.env.cr.execute(
                                    """
                                    SELECT 1 FROM calendar_event occ
                                    LEFT JOIN caldav_event_map map ON map.event_id = occ.id AND map.account_id = %s
                                    WHERE occ.recurrence_id = %s AND occ.active = true
                                      AND (
                                          (map.id IS NOT NULL AND occ.write_date > map.last_odoo_write + interval '2 seconds')
                                          OR
                                          (map.id IS NULL AND occ.write_date > %s + interval '2 seconds')
                                      )
                                    LIMIT 1
                                """,
                                    (
                                        account.id,
                                        existing.event_id.recurrence_id.id,
                                        existing.last_odoo_write,
                                    ),
                                )
                                if self.env.cr.fetchone():
                                    has_pending = True
                            if has_pending:
                                _logger.info(
                                    "[ZOHO] Skipping pull for %s: Pending Odoo change detected (Base or Occurrence).",
                                    href,
                                )
                                existing.sudo().write({"caldav_etag": content_hash})
                                continue

                    with self.env.cr.savepoint():
                        event = self._upsert_from_ical(
                            account, href, content_hash, zoho_ical_text, existing
                        )
                        if event:
                            pulled_ids.append(event.id)
                        pulled += 1
                    continue
                except Exception as e:
                    _logger.error("[ZOHO] Pull failed for %s: %s", href, e)
                    failed += 1
                    continue
            if existing:
                if existing.caldav_etag == server_etag:
                    continue

                if existing.event_id and not existing.event_id.active:
                    continue
                if existing.event_id:
                    if not existing.last_odoo_write:
                        has_pending = True
                    else:
                        has_pending = (
                            existing.event_id.write_date - existing.last_odoo_write
                        ).total_seconds() > 2

                        if not has_pending and existing.event_id.recurrence_id:
                            # Find if any occurrence in this series is pending push
                            # (It is pending if its write_date is newer than its own map's last_odoo_write,
                            #  or if it has no map but its write_date is newer than the base's last_odoo_write)
                            self.env.cr.execute(
                                """
                                SELECT 1 FROM calendar_event occ
                                LEFT JOIN caldav_event_map map ON map.event_id = occ.id AND map.account_id = %s
                                WHERE occ.recurrence_id = %s AND occ.active = true
                                  AND (
                                      (map.id IS NOT NULL AND occ.write_date > map.last_odoo_write + interval '2 seconds')
                                      OR
                                      (map.id IS NULL AND occ.write_date > %s + interval '2 seconds')
                                  )
                                LIMIT 1
                            """,
                                (
                                    account.id,
                                    existing.event_id.recurrence_id.id,
                                    existing.last_odoo_write,
                                ),
                            )
                            if self.env.cr.fetchone():
                                has_pending = True

                    if has_pending:
                        _logger.info(
                            "Skipping pull for %s: Pending Odoo change detected (Base or Occurrence).",
                            href,
                        )
                        existing.sudo().write({"caldav_etag": server_etag})
                        continue

            try:
                _logger.info("Pulling CalDAV event from %s", href)
                with self.env.cr.savepoint():
                    ical_text = account._fetch_ical(href)
                    event = self._upsert_from_ical(
                        account, href, server_etag, ical_text, existing
                    )
                    if event:
                        pulled_ids.append(event.id)
                    pulled += 1
            except Exception as e:
                error_str = str(e)
                if account.server_type == "google" and "404" in error_str:
                    _logger.info(
                        "[GOOGLE] Skipping 404 for href %s — stale/inaccessible entry in REPORT. Cleaning up map.",
                        href,
                    )
                    if existing and existing.exists():
                        try:
                            with self.env.cr.savepoint():
                                existing.sudo().unlink()
                        except Exception as _ce:
                            _logger.debug(
                                "[GOOGLE] Could not clean up stale map for %s: %s",
                                href,
                                _ce,
                            )
                    continue
                failed += 1
                error_msg = f"Pull failed for href {href}: {str(e)}"
                _logger.error(error_msg, exc_info=True)
                details.append(error_msg)

        server_hrefs = set(server_etags.keys())
        for href, map_rec in list(existing_maps.items()):
            if href not in server_hrefs:
                try:
                    with self.env.cr.savepoint():
                        if map_rec.event_id:
                            map_rec.event_id.with_context(no_sync=True).sudo().write(
                                {"active": False}
                            )
                        map_rec.sudo().unlink()
                        deleted += 1
                except Exception as e:
                    failed += 1
                    details.append(f"Archival failed for {href}: {str(e)}")

        return pulled, deleted, pulled_ids, failed, "\n".join(details)

    @api.model
    def _push_odoo_changes(self, account, skip_ids=None):
        """Push new, modified, and deleted Odoo events to the CalDAV server."""
        pushed = 0
        failed = 0
        details = []
        skip_ids = skip_ids or set()
        owner_partner = account.user_id.partner_id

        google_force_push_ids = set()
        if account.server_type == "google":
            google_force_push_ids = self._detect_google_archived_occurrences(account)
            pending_exdate_maps = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("last_odoo_write", "=", False),
                        ("event_id.active", "=", True),
                    ]
                )
            )
            for _m in pending_exdate_maps:
                if _m.event_id:
                    google_force_push_ids.add(_m.event_id.id)
                    _logger.info(
                        '[GOOGLE][PUSH] Force-push flagged for event "%s" (id=%s): '
                        "map has last_odoo_write=False (EXDATE pending).",
                        _m.event_id.name,
                        _m.event_id.id,
                    )
        all_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                ]
            )
        )
        for map_rec in all_maps:
            event = map_rec.event_id
            if not event:
                map_rec.sudo().unlink()
                continue
            if not event.active and event.id not in skip_ids:
                # ← INSERT HERE (Zoho only)
                if account.server_type == "zoho" and "__occ_" in (
                    map_rec.caldav_uid or ""
                ):
                    _logger.info(
                        "[ZOHO] Skipping CalDAV DELETE for archived occurrence-override map "
                        "(event_id=%s, uid=%s) — cleaning up local map only.",
                        event.id,
                        map_rec.caldav_uid,
                    )
                    try:
                        with self.env.cr.savepoint():
                            map_rec.sudo().unlink()
                    except Exception as _ue:
                        _logger.warning(
                            "[ZOHO] Could not unlink occurrence-override map: %s", _ue
                        )
                    continue
                # ← existing code continues below
                if event.recurrence_id:
                    active_remaining = (
                        self.env["calendar.event"]
                        .sudo()
                        .search_count(
                            [
                                ("recurrence_id", "=", event.recurrence_id.id),
                                ("active", "=", True),
                            ]
                        )
                    )
                    if active_remaining > 0:
                        _logger.info(
                            'Archived event "%s" (id=%s) still has %s active occurrences. '
                            "Skipping CalDAV DELETE (EXDATE re-push already handled in unlink).",
                            event.name,
                            event.id,
                            active_remaining,
                        )
                        continue
                try:
                    with self.env.cr.savepoint():
                        _logger.info(
                            'Deleting CalDAV event for archived Odoo event "%s" (id=%s) at %s',
                            event.name,
                            event.id,
                            map_rec.caldav_href,
                        )
                        account._delete_event(
                            map_rec.caldav_href, etag=map_rec.caldav_etag
                        )
                        pushed += 1
                except Exception as e:
                    failed += 1
                    error_msg = (
                        f'Delete failed for "{event.name}" (id={event.id}): {str(e)}'
                    )
                    _logger.warning(error_msg)
                    details.append(error_msg)
                finally:
                    try:
                        with self.env.cr.savepoint():
                            map_rec.sudo().unlink()
                    except Exception as ue:
                        _logger.warning(
                            'Could not unlink map for "%s": %s', event.name, ue
                        )
                    continue
        owner_partner_id = owner_partner.id

        non_recurring = (
            self.env["calendar.event"]
            .sudo()
            .search(
                [
                    ("active", "=", True),
                    ("recurrence_id", "=", False),
                ]
            )
            .filtered(lambda e: owner_partner_id in e.partner_ids.ids)
        )
        recurrences = self.env["calendar.recurrence"].sudo().search([])
        recurring_base_events = recurrences.mapped("base_event_id").filtered(
            lambda e: e.active
            and any(att.partner_id.id == owner_partner_id for att in e.attendee_ids)
        )

        events = non_recurring | recurring_base_events

        if account.server_type == "google":
            self._migrate_recurrence_mappings(account)
        if account.server_type == "icloud":
            try:
                with self.env.cr.savepoint():
                    self._push_icloud_occurrence_overrides(account, skip_ids=skip_ids)
            except Exception as e:
                _logger.warning(
                    "[iCLOUD] Occurrence override push failed: %s", e, exc_info=True
                )

        if account.server_type == "zoho":
            try:
                with self.env.cr.savepoint():
                    zoho_pushed = self._push_zoho_occurrence_overrides(
                        account, skip_ids=skip_ids
                    )
                    pushed += zoho_pushed or 0
            except Exception as e:
                _logger.warning(
                    "[ZOHO] Occurrence override push failed: %s", e, exc_info=True
                )

        if account.server_type == "google":
            try:
                with self.env.cr.savepoint():
                    google_pushed = self._push_google_occurrence_overrides(
                        account, skip_ids=skip_ids
                    )
                    pushed += google_pushed or 0
            except Exception as e:
                _logger.warning(
                    "[GOOGLE] Occurrence override push failed: %s", e, exc_info=True
                )

        # --- Radicale / Generic CalDAV: detect modified non-base occurrences ---
        # For iCloud/Zoho/Google there are dedicated occurrence override push methods.
        # For Radicale, modified non-base occurrences don't change the base event's
        # write_date, so the normal `write_date <= last_push` check skips the push.
        # Fix: scan all occurrences; if any was written after the base map's
        # last_odoo_write, add the base event ID to a radicale_force_push set so
        # the base event gets re-pushed (which will include RECURRENCE-ID overrides
        # for any occurrence that differs from the base, via _odoo_event_to_ical).
        radicale_force_push_ids = set()
        if account.server_type not in ("google", "zoho", "icloud"):
            try:
                all_recurrences = self.env["calendar.recurrence"].sudo().search([])
                for recurrence in all_recurrences:
                    base_event = recurrence.base_event_id
                    if not base_event or not base_event.active:
                        continue
                    if not any(
                        att.partner_id.id == owner_partner_id
                        for att in base_event.attendee_ids
                    ):
                        continue
                    base_map = (
                        self.env["caldav.event.map"]
                        .sudo()
                        .search(
                            [
                                ("account_id", "=", account.id),
                                ("event_id", "=", base_event.id),
                            ],
                            limit=1,
                        )
                    )
                    if not base_map:
                        continue  # new series not yet pushed — normal push will handle it
                    last_sync = base_map.last_odoo_write
                    if not last_sync:
                        continue  # already flagged for push
                    # Check all non-base occurrences for modifications
                    other_occs = (
                        self.env["calendar.event"]
                        .sudo()
                        .search(
                            [
                                ("recurrence_id", "=", recurrence.id),
                                ("active", "=", True),
                                ("id", "!=", base_event.id),
                            ]
                        )
                    )
                    for occ in other_occs:
                        if occ.id in skip_ids:
                            continue
                        if occ.write_date and occ.write_date > last_sync:
                            _logger.info(
                                '[RADICALE][PUSH] Occurrence "%s" (id=%s, write=%s) of '
                                'series "%s" was modified after last sync (%s). '
                                "Force-pushing base event id=%s to re-build RECURRENCE-ID overrides.",
                                occ.name,
                                occ.id,
                                occ.write_date,
                                base_event.name,
                                last_sync,
                                base_event.id,
                            )
                            radicale_force_push_ids.add(base_event.id)
                            break  # one modified occurrence is enough to trigger push
            except Exception as _re:
                _logger.warning(
                    "[RADICALE] Occurrence change detection failed: %s",
                    _re,
                    exc_info=True,
                )

        _logger.info(
            "Push candidates for account %s: %s event(s) — non-recurring=%s, recurring_base=%s",
            account.name,
            len(events),
            len(non_recurring),
            len(recurring_base_events),
        )

        existing_maps = {
            m.event_id.id: m
            for m in self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("event_id", "in", events.ids),
                ]
            )
        }

        for event in events:
            if event.id in skip_ids:
                _logger.debug(
                    '[PUSH] SKIP event id=%s "%s": in skip_ids (just pulled).',
                    event.id,
                    event.name,
                )
                continue
            existing_map = existing_maps.get(event.id)
            if (
                account.server_type in ("icloud", "zoho")
                and event.recurrence_id
                and existing_map
            ):
                continue
            if account.server_type == "google" and event.recurrence_id and existing_map:
                if event.id not in google_force_push_ids:
                    continue
            if (
                existing_map
                and event.id not in google_force_push_ids
                and event.id not in radicale_force_push_ids
            ):
                last_push = existing_map.last_odoo_write
                if last_push and event.write_date and event.write_date <= last_push:
                    _logger.debug(
                        '[PUSH] SKIP event id=%s "%s": unchanged (write_date=%s <= last_push=%s).',
                        event.id,
                        event.name,
                        event.write_date,
                        last_push,
                    )
                    continue
            _logger.info('[PUSH] WILL PUSH event id=%s "%s".', event.id, event.name)
            try:
                with self.env.cr.savepoint():
                    etag = self._push_single_event(account, event, existing_map)
                    pushed += 1
                    _logger.debug(
                        'Pushed event "%s" (id=%s) to %s; etag=%s',
                        event.name,
                        event.id,
                        account.url,
                        etag,
                    )
            # FIXED CODE:
            except Exception as e:
                msg = str(e)
                if "412" in msg and existing_map:
                    _logger.warning(
                        'Conflict detected for event "%s" (id=%s): Server has a newer version. '
                        "Attempting auto-recovery pull.",
                        event.name,
                        event.id,
                    )
                    try:
                        with self.env.cr.savepoint():
                            new_etag, ical_text = account._fetch_ical_with_etag(
                                existing_map.caldav_href
                            )
                            self._upsert_from_ical(
                                account,
                                existing_map.caldav_href,
                                new_etag,
                                ical_text,
                                existing_map,
                            )
                            _logger.info(
                                'Auto-recovery pull successful for event "%s".',
                                event.name,
                            )
                    except Exception as re:
                        _logger.error(
                            'Auto-recovery pull failed for event "%s": %s',
                            event.name,
                            re,
                        )

                elif "409" in msg and existing_map and account.server_type == "google":
                    _logger.warning(
                        '[GOOGLE] 409 Conflict for event "%s" (id=%s) at %s — '
                        "attempting to reconcile by fetching current server state.",
                        event.name,
                        event.id,
                        existing_map.caldav_href,
                    )
                    try:
                        with self.env.cr.savepoint():
                            new_etag, ical_text = account._fetch_ical_with_etag(
                                existing_map.caldav_href
                            )

                            # Before pulling, snapshot the user's intended values
                            intended_start = event.start
                            intended_stop = event.stop
                            intended_allday = event.allday
                            intended_name = event.name

                            # Pull server state into Odoo to re-align the map
                            self._upsert_from_ical(
                                account,
                                existing_map.caldav_href,
                                new_etag,
                                ical_text,
                                existing_map,
                            )
                            _logger.info(
                                '[GOOGLE] 409 recovery pull done for "%s". '
                                "Re-applying user intended values and retrying push.",
                                event.name,
                            )

                            # Re-apply the user's intended change on top of the pulled state
                            event.with_context(no_sync=True).sudo().write(
                                {
                                    "name": intended_name,
                                    "start": intended_start,
                                    "stop": intended_stop,
                                    "allday": intended_allday,
                                }
                            )

                            # Invalidate the map's last_odoo_write so next sync pushes
                            existing_map_refreshed = (
                                self.env["caldav.event.map"]
                                .sudo()
                                .search(
                                    [
                                        ("account_id", "=", account.id),
                                        ("event_id", "=", event.id),
                                    ],
                                    limit=1,
                                )
                            )
                            if existing_map_refreshed:
                                existing_map_refreshed.sudo().write(
                                    {"last_odoo_write": False}
                                )

                            _logger.info(
                                '[GOOGLE] 409 recovery: re-applied user change for "%s". '
                                "Will be pushed on next sync.",
                                event.name,
                            )
                    except Exception as fetch_err:
                        fetch_msg = str(fetch_err)
                        if "404" in fetch_msg or "410" in fetch_msg:
                            _logger.warning(
                                '[GOOGLE] 409 recovery: event "%s" not found on server (404/410). '
                                "Wiping stale map so next sync re-creates it.",
                                event.name,
                            )
                            try:
                                with self.env.cr.savepoint():
                                    event.sudo().write({"caldav_uid": False})
                                    existing_map.sudo().unlink()
                            except Exception as wipe_err:
                                _logger.error(
                                    '[GOOGLE] Could not wipe stale map for "%s": %s',
                                    event.name,
                                    wipe_err,
                                )
                        else:
                            failed += 1
                            error_msg = (
                                f'Push failed for "{event.name}" (id={event.id}) '
                                f"with 409, and recovery fetch also failed: {fetch_err}"
                            )
                            _logger.error(error_msg)
                            details.append(error_msg)

        return pushed, failed, "\n".join(details)

    @api.model
    def _detect_google_archived_occurrences(self, account):
        """Detect archived recurring occurrences and record them as EXDATEs."""
        owner_partner_id = account.user_id.partner_id.id
        force_push_ids = set()

        _logger.debug(
            "[GOOGLE][PUSH] Detecting archived occurrences for account %s...",
            account.name,
        )

        all_recurrences = self.env["calendar.recurrence"].sudo().search([])
        relevant_recurrences = all_recurrences.filtered(
            lambda r: r.base_event_id
            and r.base_event_id.active
            and any(
                att.partner_id.id == owner_partner_id
                for att in r.base_event_id.attendee_ids
            )
        )

        for recurrence in relevant_recurrences:
            base_event = recurrence.base_event_id

            base_map = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("event_id", "=", base_event.id),
                    ],
                    limit=1,
                )
            )

            if not base_map:

                all_recurrence_event_ids = (
                    self.env["calendar.event"]
                    .sudo()
                    .with_context(active_test=False)
                    .search(
                        [
                            ("recurrence_id", "=", recurrence.id),
                            ("active", "=", False),
                        ]
                    )
                    .ids
                )

                if not all_recurrence_event_ids:
                    continue

                orphaned_map = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "in", all_recurrence_event_ids),
                        ],
                        limit=1,
                    )
                )

                if not orphaned_map:
                    continue

                old_base = orphaned_map.event_id
                old_base_start_iso = (
                    old_base.start.strftime("%Y%m%dT%H%M%SZ")
                    if old_base.start
                    else None
                )

                if base_event.caldav_uid != orphaned_map.caldav_uid:
                    base_event.sudo().write({"caldav_uid": orphaned_map.caldav_uid})
                    _logger.info(
                        "Google Case B: Updated caldav_uid on new base (id=%s) to match "
                        'old map UID "%s" so href and iCal UID stay consistent.',
                        base_event.id,
                        orphaned_map.caldav_uid,
                    )

                existing_occ_map = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "=", base_event.id),
                            ("id", "!=", orphaned_map.id),
                        ]
                    )
                )
                if existing_occ_map:
                    existing_occ_map.sudo().unlink()

                existing_ex = orphaned_map.google_exdates or ""
                ex_list = set(d for d in existing_ex.split(",") if d)
                if old_base_start_iso:
                    ex_list.add(old_base_start_iso)

                orphaned_map.sudo().write(
                    {
                        "event_id": base_event.id,
                        "google_exdates": ",".join(sorted(ex_list)),
                        "last_odoo_write": False,
                    }
                )
                _logger.info(
                    "Google Case B: Transferred map (id=%s, href=%s) from archived base "
                    "(id=%s, start=%s) to new base (id=%s) with EXDATE %s.",
                    orphaned_map.id,
                    orphaned_map.caldav_href,
                    old_base.id,
                    old_base_start_iso,
                    base_event.id,
                    old_base_start_iso,
                )
                force_push_ids.add(base_event.id)

                base_map = orphaned_map

            archived_occurrences = (
                self.env["calendar.event"]
                .sudo()
                .with_context(active_test=False)
                .search(
                    [
                        ("recurrence_id", "=", recurrence.id),
                        ("active", "=", False),
                        ("id", "!=", base_event.id),
                    ]
                )
            )

            if not archived_occurrences:
                continue

            existing_exdates = set(
                d.strip()
                for d in (base_map.google_exdates or "").split(",")
                if d.strip()
            )

            new_exdates = set()
            for occ in archived_occurrences:
                if not occ.start:
                    continue
                original_start = occ.caldav_original_start or occ.start
                start_iso = original_start.strftime("%Y%m%dT%H%M%SZ")
                if start_iso not in existing_exdates:
                    new_exdates.add(start_iso)
                    _logger.info(
                        "Google EXDATE detected: archived occurrence (id=%s, start=%s) "
                        'in series "%s" — will push EXDATE to Google.',
                        occ.id,
                        start_iso,
                        base_event.name,
                    )

            if new_exdates:
                all_exdates = existing_exdates | new_exdates
                base_map.sudo().write(
                    {
                        "google_exdates": ",".join(sorted(all_exdates)),
                        "last_odoo_write": False,
                    }
                )
                force_push_ids.add(base_event.id)
                _logger.info(
                    'Updated google_exdates on map (id=%s) for series "%s": %s',
                    base_map.id,
                    base_event.name,
                    ",".join(sorted(all_exdates)),
                )

        return force_push_ids

    @api.model
    def _build_href(self, account, uid):
        """Build the CalDAV resource URL for a new event."""
        base = account.url.rstrip("/")
        return f"{base}/{uid}.ics"

    @api.model
    def _push_single_event(self, account, event, existing_map=None):
        """Build the iCal string and PUT it to the CalDAV server."""
        uid = event.caldav_uid or str(uuid.uuid4())
        if not event.caldav_uid:
            event.sudo().write({"caldav_uid": uid})

        ical_str = self._odoo_event_to_ical(event, account, existing_map=existing_map)
        href = (
            existing_map.caldav_href if existing_map else self._build_href(account, uid)
        )
        old_etag = existing_map.caldav_etag if existing_map else None

        _logger.info(
            'Pushing event "%s" (id=%s) to %s; If-Match ETag=%s',
            event.name,
            event.id,
            href,
            old_etag,
        )
        _logger.info(
            'Outgoing iCal payload (Going to Server) for event "%s" (id=%s):\n%s',
            event.name,
            event.id,
            ical_str,
        )
        new_etag = account._put_ical(href, ical_str, etag=old_etag)
        _logger.debug("Push successful; new ETag=%s", new_etag)
        if account.server_type == "google":
            try:
                fresh_etag, _ = account._fetch_ical_with_etag(href)
                if fresh_etag:
                    _logger.debug(
                        '[GOOGLE] Reconciling ETag after push for "%s": PUT returned %r, '
                        "server REPORT will return %r — storing fresh ETag.",
                        event.name,
                        new_etag,
                        fresh_etag,
                    )
                    new_etag = fresh_etag
            except Exception as _fe:
                _logger.debug(
                    '[GOOGLE] Could not fetch fresh ETag after push for "%s": %s',
                    event.name,
                    _fe,
                )
        if account.server_type == "zoho":
            _meaningful_prefixes = (
                "SUMMARY",
                "DTSTART",
                "DTEND",
                "RRULE",
                "RECURRENCE-ID",
                "EXDATE",
                "LOCATION",
                "DESCRIPTION",
                "STATUS",
            )
            normalized_push = "\n".join(
                line.strip()
                for line in ical_str.splitlines()
                if any(line.strip().startswith(p) for p in _meaningful_prefixes)
            )
            etag_to_store = (
                "zoho_hash:" + hashlib.sha256(normalized_push.encode()).hexdigest()
            )
            _logger.info(
                "[ZOHO][PUSH] Storing content hash as caldav_etag for href=%s: %s",
                href,
                etag_to_store,
            )
        else:
            etag_to_store = new_etag

        map_vals = {
            "account_id": account.id,
            "event_id": event.id,
            "caldav_uid": uid,
            "caldav_href": href,
            "caldav_etag": etag_to_store,
            # Store the push timestamp (now) instead of event.write_date so that
            # non-base occurrence write_dates (which may be newer than the base event's
            # write_date) don't trigger a false-positive re-push on every subsequent sync.
            "last_odoo_write": fields.Datetime.now(),
        }

        if existing_map:
            existing_map.sudo().write(map_vals)
        else:
            existing = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("caldav_uid", "=", uid),
                    ],
                    limit=1,
                )
            )
            if existing:
                existing.write(map_vals)
            else:
                self.env["caldav.event.map"].sudo().create(map_vals)
        return new_etag

    @api.model
    def _apply_icloud_occurrence_overrides(
        self, recurrence_id_vevents, uid_value, account, href, server_etag
    ):
        """Apply RECURRENCE-ID overrides from iCloud into the corresponding Odoo occurrences."""
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("caldav_uid", "=", uid_value),
                ],
                limit=1,
            )
        )
        if not base_map or not base_map.event_id:
            return
        base_event = base_map.event_id
        if not base_event.recurrence_id:
            return

        ctx_kwargs = {"dont_notify": True, "no_mail_to_attendees": True}
        if account.send_invitation_emails:
            ctx_kwargs = {"mail_notify_force_send": True, "force_send": True}

        for override_vevent in recurrence_id_vevents:
            rid_comp = getattr(override_vevent, "recurrence_id", None)
            if not rid_comp:
                continue
            rid_val = rid_comp.value
            if isinstance(rid_val, datetime):
                if rid_val.tzinfo is not None:
                    rid_dt = rid_val.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    rid_dt = rid_val
            else:
                rid_dt = datetime(rid_val.year, rid_val.month, rid_val.day, 0, 0, 0)

            from datetime import timedelta as _td

            # For all-day RID (date-only), widen window to full day so Odoo's
            # 08:00 all-day start time is captured.
            if not isinstance(rid_val, datetime):
                window_start = rid_dt
                window_end = datetime(
                    rid_val.year, rid_val.month, rid_val.day, 23, 59, 59
                )
            else:
                window_start = rid_dt - _td(minutes=1)
                window_end = rid_dt + _td(minutes=1)
            occurrence = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", base_event.recurrence_id.id),
                        ("active", "=", True),
                        "|",
                        "&",
                        ("caldav_original_start", ">=", window_start),
                        ("caldav_original_start", "<=", window_end),
                        "&",
                        ("caldav_original_start", "=", False),
                        "&",
                        ("start", ">=", window_start),
                        ("start", "<=", window_end),
                    ],
                    limit=1,
                )
            )

            if not occurrence:
                _logger.warning(
                    '[iCLOUD] No Odoo occurrence found for RECURRENCE-ID %s (original or current) in series "%s".',
                    rid_dt,
                    base_event.name,
                )
                continue

            vals = self._ical_to_odoo_vals(override_vevent, account)
            if not vals:
                continue
            vals.pop("rrule", None)
            vals.pop("recurrence_update", None)
            vals.pop("caldav_uid", None)

            if not occurrence.caldav_original_start:
                vals["caldav_original_start"] = rid_dt

            occurrence.with_context(**ctx_kwargs).sudo().write(vals)
            _logger.info(
                '[iCLOUD] Applied RECURRENCE-ID override to occurrence "%s" (id=%s, start=%s).',
                occurrence.name,
                occurrence.id,
                occurrence.start,
            )

        base_map.sudo().write(
            {
                "caldav_etag": server_etag,
                "last_odoo_write": base_event.write_date,
            }
        )

    @api.model
    def _apply_zoho_occurrence_overrides(
        self, recurrence_id_vevents, uid_value, account, href, server_etag
    ):
        """Apply RECURRENCE-ID overrides pulled from Zoho into the corresponding Odoo occurrences."""
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("caldav_uid", "=", uid_value),
                ],
                limit=1,
            )
        )
        if not base_map or not base_map.event_id:
            _logger.warning(
                "[ZOHO] No base map found for UID %s; cannot apply RECURRENCE-ID overrides.",
                uid_value,
            )
            return
        base_event = base_map.event_id
        if not base_event.recurrence_id:
            _logger.warning(
                '[ZOHO] Base event "%s" (id=%s) has no recurrence_id; skipping RECURRENCE-ID override application.',
                base_event.name,
                base_event.id,
            )
            return

        ctx_kwargs = {"dont_notify": True, "no_mail_to_attendees": True}
        if account.send_invitation_emails:
            ctx_kwargs = {"mail_notify_force_send": True, "force_send": True}

        for override_vevent in recurrence_id_vevents:
            rid_comp = getattr(override_vevent, "recurrence_id", None)
            if not rid_comp:
                continue
            rid_val = rid_comp.value

            is_allday_rid = not isinstance(rid_val, datetime)
            if isinstance(rid_val, datetime):
                if rid_val.tzinfo is not None:
                    rid_dt = rid_val.astimezone(pytz.utc).replace(tzinfo=None)
                else:
                    rid_dt = rid_val
            else:
                rid_dt = datetime(rid_val.year, rid_val.month, rid_val.day, 0, 0, 0)

            if is_allday_rid:
                # For all-day events, match by the exact date.
                rid_date = rid_dt.date()
                rid_dt_end = rid_dt + timedelta(days=1)
                domain = [
                    ("recurrence_id", "=", base_event.recurrence_id.id),
                    ("active", "=", True),
                    "|",
                    "&",
                    ("caldav_original_start", ">=", rid_dt),
                    ("caldav_original_start", "<", rid_dt_end),
                    "&",
                    ("caldav_original_start", "=", False),
                    "|",
                    ("start_date", "=", rid_date),
                    "&",
                    ("start", ">=", rid_dt),
                    ("start", "<", rid_dt_end),
                ]
            else:
                window_start = rid_dt - timedelta(minutes=1)
                window_end = rid_dt + timedelta(minutes=1)
                domain = [
                    ("recurrence_id", "=", base_event.recurrence_id.id),
                    ("active", "=", True),
                    "|",
                    "&",
                    ("caldav_original_start", ">=", window_start),
                    ("caldav_original_start", "<=", window_end),
                    "&",
                    ("caldav_original_start", "=", False),
                    "&",
                    ("start", ">=", window_start),
                    ("start", "<=", window_end),
                ]

            occurrence = self.env["calendar.event"].sudo().search(domain, limit=1)

            if not occurrence:
                _logger.warning(
                    '[ZOHO] No Odoo occurrence found for RECURRENCE-ID %s (original or current) in series "%s" (uid=%s).',
                    rid_dt,
                    base_event.name,
                    uid_value,
                )
                continue

            vals = self._ical_to_odoo_vals(override_vevent, account)
            if not vals:
                continue
            vals.pop("rrule", None)
            vals.pop("recurrence_update", None)
            vals.pop("caldav_uid", None)

            if not occurrence.caldav_original_start:
                vals["caldav_original_start"] = rid_dt

            occurrence.with_context(**ctx_kwargs).sudo().write(vals)
            _logger.info(
                '[ZOHO] Applied RECURRENCE-ID override to occurrence "%s" (id=%s, start=%s).',
                occurrence.name,
                occurrence.id,
                occurrence.start,
            )
            occ_map_rec = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("event_id", "=", occurrence.id),
                        ("caldav_uid", "like", "%__occ_%"),
                    ],
                    limit=1,
                )
            )
            if occ_map_rec:
                occ_map_rec.sudo().write({"last_odoo_write": occurrence.write_date})
        base_map.sudo().write(
            {
                "caldav_etag": server_etag,
                "last_odoo_write": base_event.write_date,
            }
        )

    @api.model
    def _push_icloud_occurrence_overrides(self, account, skip_ids=None):
        """Push modified individual occurrences to iCloud as RECURRENCE-ID overrides."""
        skip_ids = skip_ids or set()
        owner_partner_id = account.user_id.partner_id.id

        all_recurrences = self.env["calendar.recurrence"].sudo().search([])
        for recurrence in all_recurrences:
            base_event = recurrence.base_event_id
            if not base_event or not base_event.active:
                continue
            if not any(
                att.partner_id.id == owner_partner_id for att in base_event.attendee_ids
            ):
                continue
            base_map = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("event_id", "=", base_event.id),
                    ],
                    limit=1,
                )
            )
            if not base_map:
                continue
            occurrences = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", recurrence.id),
                        ("active", "=", True),
                        ("id", "!=", base_event.id),
                    ]
                )
            )

            modified_occs = []
            for occ in occurrences:
                if occ.id in skip_ids:
                    continue
                occ_map = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "=", occ.id),
                        ],
                        limit=1,
                    )
                )
                if occ_map:
                    if (
                        occ_map.last_odoo_write
                        and occ.write_date
                        and occ.write_date <= occ_map.last_odoo_write
                    ):
                        if not self._occurrence_differs_from_base(occ, base_event):
                            continue
                else:
                    if (
                        base_map.last_odoo_write
                        and occ.write_date
                        and occ.write_date <= base_map.last_odoo_write
                    ):
                        if not self._occurrence_differs_from_base(occ, base_event):
                            continue
                modified_occs.append((occ, occ_map))
            if (
                base_map.last_odoo_write
                and base_event.write_date
                and base_event.write_date > base_map.last_odoo_write
            ):
                modified_occs.append((base_event, base_map))

            if not modified_occs:
                continue
            try:
                with self.env.cr.savepoint():
                    current_etag, current_ical = account._fetch_ical_with_etag(
                        base_map.caldav_href
                    )

                    updated_ical = self._build_icloud_ical_with_overrides(
                        current_ical, base_event, modified_occs, account
                    )
                    _logger.info(
                        '[iCLOUD][PUSH-OVERRIDE] Outgoing iCal payload (Going to Server) for series "%s":\n%s',
                        base_event.name,
                        updated_ical,
                    )

                    new_etag = account._put_ical(
                        base_map.caldav_href, updated_ical, etag=current_etag
                    )
                    base_map.sudo().write({"caldav_etag": new_etag or current_etag})
                    _logger.info(
                        '[iCLOUD] Pushed RECURRENCE-ID overrides for series "%s".',
                        base_event.name,
                    )
            except Exception as e:
                _logger.warning(
                    '[iCLOUD] Override push failed for series "%s": %s',
                    base_event.name,
                    e,
                    exc_info=True,
                )

    @api.model
    def _occurrence_differs_from_base(self, occ, base_event):
        """Check if an occurrence deviates from the base series in any meaningful field."""

        name_diff = (occ.name or "").strip() != (base_event.name or "").strip()
        loc_diff = (occ.location or "").strip() != (base_event.location or "").strip()

        desc_occ = html2plaintext(occ.description or "").strip()
        desc_base = html2plaintext(base_event.description or "").strip()
        desc_diff = desc_occ != desc_base

        if name_diff or loc_diff or desc_diff:
            _logger.info(
                "[DIFF-CHECK] Occurrence %s (id=%s) differs in metadata: name_diff=%s, loc_diff=%s, desc_diff=%s",
                occ.start,
                occ.id,
                name_diff,
                loc_diff,
                desc_diff,
            )
            return True

        expected_start = occ.caldav_original_start or occ.start
        if not expected_start:
            return False

        start_diff_seconds = abs((occ.start - expected_start).total_seconds())
        if start_diff_seconds > 60:
            _logger.info(
                "[DIFF-CHECK] Occurrence %s (id=%s) differs in START: current=%s, expected=%s (diff=%s sec)",
                occ.start,
                occ.id,
                occ.start,
                expected_start,
                start_diff_seconds,
            )
            return True

        occ_duration = (occ.stop - occ.start).total_seconds()
        base_duration = (base_event.stop - base_event.start).total_seconds()
        if abs(occ_duration - base_duration) > 60:
            _logger.info(
                "[DIFF-CHECK] Occurrence %s (id=%s) differs in DURATION: occ_dur=%s, base_dur=%s",
                occ.start,
                occ.id,
                occ_duration,
                base_duration,
            )
            return True

        return False

    @api.model
    def _push_zoho_occurrence_overrides(self, account, skip_ids=None):
        """Push modified individual occurrences to Zoho as RECURRENCE-ID overrides."""
        skip_ids = skip_ids or set()
        pushed_count = 0
        owner_partner_id = account.user_id.partner_id.id

        all_recurrences = self.env["calendar.recurrence"].sudo().search([])
        for recurrence in all_recurrences:
            base_event = recurrence.base_event_id
            if not base_event or not base_event.active:
                continue

            if not any(
                att.partner_id.id == owner_partner_id for att in base_event.attendee_ids
            ):
                continue

            base_map = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("event_id", "=", base_event.id),
                    ],
                    limit=1,
                )
            )
            if not base_map:
                continue
            occurrences = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", recurrence.id),
                        ("active", "=", True),
                        ("id", "!=", base_event.id),
                    ]
                )
            )

            # Determine if base event needs a push
            base_needs_push = (base_event.id not in skip_ids) and (
                not base_map.last_odoo_write
                or (
                    base_event.write_date
                    and base_event.write_date > base_map.last_odoo_write
                )
            )

            modified_occs = []
            for occ in occurrences:
                if occ.id in skip_ids:
                    continue

                occ_map = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "=", occ.id),
                        ],
                        limit=1,
                    )
                )

                is_deletion = occ_map and occ_map.last_odoo_write is False
                differs = self._occurrence_differs_from_base(occ, base_event)

                last_sync = (
                    occ_map.last_odoo_write if occ_map else base_map.last_odoo_write
                )
                modified = not last_sync or (
                    occ.write_date and occ.write_date > last_sync
                )

                # If base is pushing, we MUST include all deviating occurrences or they might revert on server
                if is_deletion or (differs and (modified or base_needs_push)):
                    modified_occs.append((occ, occ_map))

            if base_needs_push:
                _logger.info(
                    '[ZOHO] Base event "%s" (id=%s) will be pushed — including all %s deviating/modified overrides.',
                    base_event.name,
                    base_event.id,
                    len(modified_occs),
                )
                modified_occs.append((base_event, base_map))

            if not modified_occs and base_map.last_odoo_write:
                continue

            try:
                with self.env.cr.savepoint():

                    current_etag, current_ical = account._fetch_ical_with_etag(
                        base_map.caldav_href
                    )

                    updated_ical = self._build_zoho_ical_with_overrides(
                        current_ical, base_event, modified_occs, account
                    )
                    _logger.info(
                        '[ZOHO][PUSH-OVERRIDE] Outgoing iCal payload (Going to Server) for series "%s":\n%s',
                        base_event.name,
                        updated_ical,
                    )

                    new_etag = account._put_ical(
                        base_map.caldav_href, updated_ical, etag=current_etag
                    )

                    _meaningful_prefixes = (
                        "SUMMARY",
                        "DTSTART",
                        "DTEND",
                        "RRULE",
                        "RECURRENCE-ID",
                        "EXDATE",
                        "LOCATION",
                        "DESCRIPTION",
                        "STATUS",
                    )
                    normalized_push = "\n".join(
                        line.strip()
                        for line in updated_ical.splitlines()
                        if any(line.strip().startswith(p) for p in _meaningful_prefixes)
                    )
                    etag_to_store = (
                        "zoho_hash:"
                        + hashlib.sha256(normalized_push.encode()).hexdigest()
                    )

                    _logger.info(
                        '[ZOHO][PUSH-OVERRIDE] Storing content hash for series "%s" (href=%s): %s',
                        base_event.name,
                        base_map.caldav_href,
                        etag_to_store,
                    )

                    base_map.sudo().write(
                        {
                            "caldav_etag": etag_to_store,
                            "last_odoo_write": fields.Datetime.now(),
                        }
                    )
                    _logger.info(
                        '[ZOHO] Pushed RECURRENCE-ID overrides for series "%s".',
                        base_event.name,
                    )
                    pushed_count += 1
                    for occ, occ_map in modified_occs:
                        if occ_map:
                            occ_map.sudo().write({"last_odoo_write": occ.write_date})
                        else:

                            existing_occ_map = (
                                self.env["caldav.event.map"]
                                .sudo()
                                .search(
                                    [
                                        ("account_id", "=", account.id),
                                        ("event_id", "=", occ.id),
                                    ],
                                    limit=1,
                                )
                            )
                            if existing_occ_map:
                                existing_occ_map.sudo().write(
                                    {"last_odoo_write": occ.write_date}
                                )
                            else:

                                self.env["caldav.event.map"].sudo().create(
                                    {
                                        "account_id": account.id,
                                        "event_id": occ.id,
                                        "caldav_uid": f"{base_event.caldav_uid}__occ_{occ.id}",
                                        "caldav_href": base_map.caldav_href,
                                        "caldav_etag": etag_to_store,
                                        "last_odoo_write": occ.write_date,
                                    }
                                )
            except Exception as e:
                _logger.warning(
                    '[ZOHO] Override push failed for series "%s": %s',
                    base_event.name,
                    e,
                    exc_info=True,
                )
        return pushed_count

    @api.model
    def _apply_google_occurrence_overrides(
        self, recurrence_id_vevents, uid_value, account, href, server_etag
    ):
        """Apply RECURRENCE-ID overrides from Google Calendar into Odoo occurrences."""
        base_map = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("caldav_uid", "=", uid_value),
                ],
                limit=1,
            )
        )
        if not base_map or not base_map.event_id:
            return
        base_event = base_map.event_id
        if not base_event.recurrence_id:
            return

        ctx_kwargs = {"dont_notify": True, "no_mail_to_attendees": True}
        if account.send_invitation_emails:
            ctx_kwargs = {"mail_notify_force_send": True, "force_send": True}

        for override_vevent in recurrence_id_vevents:
            rid_comp = getattr(override_vevent, "recurrence_id", None)
            if not rid_comp:
                continue
            rid_val = rid_comp.value

            is_date_only = _is_date_only(rid_val)

            if is_date_only:
                window_start = datetime(
                    rid_val.year, rid_val.month, rid_val.day, 0, 0, 0
                )
                window_end = datetime(
                    rid_val.year, rid_val.month, rid_val.day, 23, 59, 59
                )
                rid_dt = window_start  # used only for logging
            else:
                rid_dt_aware = (
                    rid_val.astimezone(timezone.utc).replace(tzinfo=None)
                    if rid_val.tzinfo
                    else rid_val
                )
                rid_dt = rid_dt_aware
                window_start = rid_dt - timedelta(minutes=1)
                window_end = rid_dt + timedelta(minutes=1)

            _logger.info(
                "[GOOGLE][PULL] Matching RECURRENCE-ID %s (all-day=%s) with window [%s, %s]",
                rid_val,
                is_date_only,
                window_start,
                window_end,
            )

            occurrence = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", base_event.recurrence_id.id),
                        ("active", "=", True),
                        "|",
                        "&",
                        ("caldav_original_start", ">=", window_start),
                        ("caldav_original_start", "<=", window_end),
                        "&",
                        ("caldav_original_start", "=", False),
                        "&",
                        ("start", ">=", window_start),
                        ("start", "<=", window_end),
                    ],
                    limit=1,
                )
            )

            if not occurrence:
                # Check if RECURRENCE-ID targets the base event itself
                # (Google sends this when the user edits the first occurrence)
                base_start = base_event.start
                base_in_window = (
                    (
                        base_start
                        and window_start
                        <= base_start.replace(tzinfo=None)
                        <= window_end
                    )
                    if base_start
                    else False
                )
                if base_in_window:
                    occurrence = base_event
                    _logger.info(
                        '[GOOGLE][PULL] RECURRENCE-ID %s matches the BASE event "%s" (id=%s). '
                        "Applying override to base event.",
                        rid_dt,
                        base_event.name,
                        base_event.id,
                    )
                else:
                    _logger.warning(
                        "[GOOGLE] No Odoo occurrence found for RECURRENCE-ID %s (window=[%s, %s]) "
                        'in series "%s". This can happen if the occurrence was deleted in Odoo '
                        "but still exists on Google.",
                        rid_dt,
                        window_start,
                        window_end,
                        base_event.name,
                    )
                    continue

            _logger.info(
                '[GOOGLE][PULL] Found matching Odoo occurrence "%s" (id=%s) for RECURRENCE-ID %s. Applying changes...',
                occurrence.name,
                occurrence.id,
                rid_dt,
            )

            vals = self._ical_to_odoo_vals(override_vevent, account)
            if not vals:
                continue
            vals.pop("rrule", None)
            vals.pop("recurrence_update", None)
            vals.pop("caldav_uid", None)

            if not occurrence.caldav_original_start:
                vals["caldav_original_start"] = window_start

            occurrence.with_context(**ctx_kwargs, no_sync=True).sudo().write(vals)
            _logger.info(
                '[GOOGLE][PULL] Updated occurrence "%s" (id=%s).',
                occurrence.name,
                occurrence.id,
            )

        base_map.sudo().write(
            {
                "caldav_etag": server_etag,
                "last_odoo_write": fields.Datetime.now(),
            }
        )

    @api.model
    def _push_google_occurrence_overrides(self, account, skip_ids=None):
        """Push modified occurrences to Google as RECURRENCE-ID overrides."""
        skip_ids = skip_ids or set()
        owner_partner_id = account.user_id.partner_id.id
        pushed_count = 0
        all_recurrences = self.env["calendar.recurrence"].sudo().search([])

        for recurrence in all_recurrences:
            base_event = recurrence.base_event_id
            if not base_event or not base_event.active:
                continue
            if not any(
                att.partner_id.id == owner_partner_id for att in base_event.attendee_ids
            ):
                continue
            base_map = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("account_id", "=", account.id),
                        ("event_id", "=", base_event.id),
                    ],
                    limit=1,
                )
            )
            if not base_map:
                continue

            occurrences = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", recurrence.id),
                        ("active", "=", True),
                        ("id", "!=", base_event.id),
                    ]
                )
            )

            base_needs_direct_push = False
            if base_event.id not in skip_ids:
                if not base_map.last_odoo_write:
                    # last_odoo_write=False/None means unlink() flagged this series
                    # for a forced re-push (e.g. an occurrence was deleted → EXDATE needed).
                    base_needs_direct_push = True
                elif (
                    base_event.write_date
                    and base_event.write_date > base_map.last_odoo_write
                ):
                    base_needs_direct_push = True

            modified_occs = []  # Occurrences the user explicitly changed
            pinned_occs = (
                []
            )  # Occurrences NOT changed but need pinning when base changes

            for occ in occurrences:
                if occ.id in skip_ids:
                    continue

                occ_map = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "=", occ.id),
                        ],
                        limit=1,
                    )
                )

                last_sync = (
                    occ_map.last_odoo_write if occ_map else base_map.last_odoo_write
                )
                user_modified = (
                    not last_sync or not occ.write_date or occ.write_date > last_sync
                ) and self._occurrence_differs_from_base(occ, base_event)

                if user_modified:
                    _logger.info(
                        '[GOOGLE][PUSH] Occurrence id=%s "%s" is user-modified — adding as override.',
                        occ.id,
                        occ.name,
                    )
                    modified_occs.append((occ, occ_map))
                elif base_needs_direct_push:
                    pinned_occs.append((occ, occ_map))
                    _logger.info(
                        '[GOOGLE][PUSH] Occurrence id=%s "%s" is unchanged — pinning '
                        "as RECURRENCE-ID to protect from base propagation.",
                        occ.id,
                        occ.name,
                    )

            if not modified_occs and not base_needs_direct_push:
                continue

            try:
                with self.env.cr.savepoint():
                    current_etag, current_ical = account._fetch_ical_with_etag(
                        base_map.caldav_href
                    )

                    if base_needs_direct_push and pinned_occs:
                        step1_ical = self._build_google_base_edit(
                            current_ical, base_event, account
                        )
                        if modified_occs:
                            step1_ical = self._build_google_ical_with_overrides(
                                step1_ical, base_event, modified_occs, account
                            )
                        _logger.info(
                            '[GOOGLE][PUSH-STEP1] Pushing master change for "%s" '
                            "(%s user-modified overrides). Pinned occs deferred to step 2.",
                            base_event.name,
                            len(modified_occs),
                        )
                        account._put_ical(base_map.caldav_href, step1_ical, etag=None)

                        _, refreshed_ical = account._fetch_ical_with_etag(
                            base_map.caldav_href
                        )
                        step2_ical = self._build_google_ical_with_overrides(
                            refreshed_ical, base_event, pinned_occs, account
                        )
                        _logger.info(
                            "[GOOGLE][PUSH-STEP2] Pushing %s pinned RECURRENCE-ID override(s) "
                            'for series "%s":\n%s',
                            len(pinned_occs),
                            base_event.name,
                            step2_ical,
                        )
                        new_etag = account._put_ical(
                            base_map.caldav_href, step2_ical, etag=None
                        )
                        all_occs_to_push = modified_occs + pinned_occs

                    elif base_needs_direct_push:
                        # Base changed, no unchanged occurrences to protect.
                        ical = self._build_google_base_edit(
                            current_ical, base_event, account
                        )
                        if modified_occs:
                            ical = self._build_google_ical_with_overrides(
                                ical, base_event, modified_occs, account
                            )
                        _logger.info(
                            '[GOOGLE][PUSH-OVERRIDE] Outgoing iCal payload for series "%s" '
                            "(%s user-modified, no pinned):\n%s",
                            base_event.name,
                            len(modified_occs),
                            ical,
                        )
                        new_etag = account._put_ical(
                            base_map.caldav_href, ical, etag=None
                        )
                        all_occs_to_push = modified_occs

                    else:
                        # Only user-modified overrides, base unchanged.
                        ical = self._build_google_ical_with_overrides(
                            current_ical, base_event, modified_occs, account
                        )
                        _logger.info(
                            '[GOOGLE][PUSH-OVERRIDE] Outgoing iCal payload for series "%s" '
                            "(%s user-modified overrides, base unchanged):\n%s",
                            base_event.name,
                            len(modified_occs),
                            ical,
                        )
                        new_etag = account._put_ical(
                            base_map.caldav_href, ical, etag=None
                        )
                        all_occs_to_push = modified_occs

                    if account.server_type == "google":
                        try:
                            fresh_etag, _ = account._fetch_ical_with_etag(
                                base_map.caldav_href
                            )
                            if fresh_etag:
                                new_etag = fresh_etag
                        except Exception:
                            pass

                    base_map.sudo().write(
                        {
                            "caldav_etag": new_etag or current_etag,
                            "last_odoo_write": fields.Datetime.now(),
                        }
                    )
                    pushed_count += 1

                    for occ, occ_map in all_occs_to_push:
                        timestamp = fields.Datetime.now()
                        if occ_map:
                            occ_map.sudo().write({"last_odoo_write": timestamp})
                        else:
                            self.env["caldav.event.map"].sudo().create(
                                {
                                    "account_id": account.id,
                                    "event_id": occ.id,
                                    "caldav_uid": f"{base_event.caldav_uid}__occ_{occ.id}",
                                    "caldav_href": base_map.caldav_href,
                                    "caldav_etag": new_etag or current_etag,
                                    "last_odoo_write": timestamp,
                                }
                            )
            except Exception as e:
                _logger.warning(
                    '[GOOGLE] Override push failed for series "%s": %s',
                    base_event.name,
                    e,
                )
        return pushed_count

    @api.model
    def _upsert_from_ical(
        self, account, href, server_etag, ical_text, existing_map=None
    ):
        """Parse iCal text and create/update the corresponding Odoo calendar event."""
        if vobject is None:
            _logger.warning("vobject not available; skipping iCal import.")
            return

        try:
            _logger.info(
                "[PULL] Incoming iCal content (Coming from Server) for href %s:\n%s",
                href,
                ical_text,
            )
            if not ical_text or not ical_text.strip():
                if existing_map and existing_map.event_id:
                    _logger.info(
                        "[PULL] iCal content is empty for existing event %s (id=%s). Treating as server deletion.",
                        href,
                        existing_map.event_id.id,
                    )
                    existing_map.event_id.with_context(
                        no_caldav_delete=True
                    ).sudo().unlink()
                    return
                else:
                    _logger.warning(
                        "[PULL] iCal content is empty for href %s and no local mapping exists. Skipping.",
                        href,
                    )
                    return

            cal = vobject.readOne(ical_text)
        except Exception as e:
            _logger.warning("Failed to parse iCal from %s: %s", href, e)
            return

        vevent = None
        recurrence_id_vevents = []
        for component in cal.components():
            if component.name == "VEVENT":
                if hasattr(component, "recurrence_id"):
                    recurrence_id_vevents.append(component)
                elif vevent is None:
                    vevent = component
        if vevent is None:
            return

        uid = getattr(vevent, "uid", None)
        uid_value = uid.value if uid else str(uuid.uuid4())

        # Processing of RECURRENCE-ID overrides moved to end of method to ensure series is fully promoted first.

        vals = self._ical_to_odoo_vals(vevent, account)
        if not vals:
            return

        ctx_kwargs = {}
        if not account.send_invitation_emails:
            ctx_kwargs["dont_notify"] = True
            ctx_kwargs["no_mail_to_attendees"] = True
        else:
            ctx_kwargs["mail_notify_force_send"] = True
            ctx_kwargs["force_send"] = True

        CalEvent = self.env["calendar.event"].with_context(**ctx_kwargs).sudo()
        event = None

        if not existing_map and account.server_type == "zoho":
            existing_event = CalEvent.search([("caldav_uid", "=", uid_value)], limit=1)
            if existing_event:
                event = existing_event
                map_rec = (
                    self.env["caldav.event.map"]
                    .sudo()
                    .search(
                        [
                            ("account_id", "=", account.id),
                            ("event_id", "=", event.id),
                        ],
                        limit=1,
                    )
                )
                if map_rec:
                    map_rec.write({"caldav_href": href, "caldav_etag": server_etag})
                    existing_map = map_rec
                else:
                    existing_map = (
                        self.env["caldav.event.map"]
                        .sudo()
                        .create(
                            {
                                "account_id": account.id,
                                "event_id": event.id,
                                "caldav_href": href,
                                "caldav_etag": server_etag,
                                "caldav_uid": uid_value,
                            }
                        )
                    )

        if existing_map and (existing_map.event_id or event):
            event = event or existing_map.event_id
            vals.pop("caldav_uid", None)

            if event.recurrence_id:
                if account.server_type not in ("zoho", "google", "icloud") and vals.get(
                    "rrule"
                ):
                    # --- Radicale / Generic CalDAV: re-apply RRULE if it changed ---
                    # This handles the case where the user upgrades a single event to
                    # a recurring series (or changes COUNT/INTERVAL) on the CalDAV
                    # server side (e.g. Radicale). Without this, the new RRULE is
                    # silently dropped and Odoo keeps only 1 occurrence.
                    incoming_rrule = (vals.get("rrule") or "").strip().upper()
                    # Odoo stores the full rrule string in recurrence.rrule which may
                    # include a DTSTART prefix line; extract only the RRULE: part.
                    raw_current = (event.recurrence_id.rrule or "").strip()
                    current_rrule = ""
                    for _line in raw_current.splitlines():
                        _line = _line.strip().upper()
                        if _line.startswith("RRULE:"):
                            current_rrule = _line[len("RRULE:") :]
                            break
                    if not current_rrule:
                        current_rrule = raw_current.upper()

                    if incoming_rrule and incoming_rrule != current_rrule:
                        _logger.info(
                            '[RADICALE][PULL] RRULE changed for event "%s" (id=%s): '
                            '"%s" -> "%s". Re-applying recurrence to all events.',
                            event.name,
                            event.id,
                            current_rrule,
                            incoming_rrule,
                        )
                        vals["recurrence_update"] = "all_events"
                        event.with_context(**ctx_kwargs).write(vals)
                        # ← INSERT HERE
                        stale_occ_maps = (
                            self.env["caldav.event.map"]
                            .sudo()
                            .search(
                                [
                                    ("account_id", "=", account.id),
                                    ("caldav_href", "=", href),
                                    ("caldav_uid", "like", "%__occ_%"),
                                ]
                            )
                        )
                        if stale_occ_maps:
                            _logger.info(
                                "[ZOHO][PULL] Cleaning up %s stale occurrence map(s) after "
                                'RRULE re-apply for "%s".',
                                len(stale_occ_maps),
                                event.name,
                            )
                            stale_occ_maps.sudo().unlink()
                    else:
                        # RRULE unchanged — only update scalar fields
                        vals.pop("rrule", None)
                        vals.pop("recurrence_update", None)
                        event.with_context(**ctx_kwargs).write(vals)

                elif account.server_type == "zoho" and vals.get("rrule"):

                    def _strip_defaults(r):
                        return ";".join(
                            p
                            for p in r.strip().upper().split(";")
                            if p not in ("INTERVAL=1", "WKST=SU", "WKST=MO")
                        )

                    incoming_rrule = _strip_defaults(vals.get("rrule") or "")
                    current_rrule = _strip_defaults(event.recurrence_id.rrule or "")
                    if incoming_rrule and incoming_rrule != current_rrule:
                        _weekday_remap = {
                            "mo": "mon",
                            "tu": "tue",
                            "we": "wed",
                            "th": "thu",
                            "fr": "fri",
                            "sa": "sat",
                            "su": "sun",
                        }
                        _odoo_weekday_fields = set(_weekday_remap.values())
                        update_vals = {}
                        for _k, _v in vals.items():
                            if _k != "rrule":
                                update_vals[_weekday_remap.get(_k, _k)] = _v
                        for _day_field in _odoo_weekday_fields:
                            update_vals[_day_field] = False

                        import re as _re

                        _byday_to_field = {
                            "MO": "mon",
                            "TU": "tue",
                            "WE": "wed",
                            "TH": "thu",
                            "FR": "fri",
                            "SA": "sat",
                            "SU": "sun",
                        }
                        _byday_match = _re.search(
                            r"BYDAY=([^;]+)", incoming_rrule, _re.IGNORECASE
                        )
                        if _byday_match:
                            for _day_token in _byday_match.group(1).split(","):
                                _day_code = _day_token.strip().upper()[-2:]
                                if _day_code in _byday_to_field:
                                    update_vals[_byday_to_field[_day_code]] = True
                        update_vals["recurrence_update"] = "all_events"
                        event.with_context(**ctx_kwargs).write(update_vals)
                    else:
                        vals.pop("rrule", None)
                        vals.pop("recurrence_update", None)
                        event.with_context(**ctx_kwargs).write(vals)
                elif vals.get("rrule") and account.server_type == "google":
                    # Google: existing recurring event with RRULE change.
                    # Only re-apply if the RRULE actually changed to avoid
                    # spurious recurrence resets on every sync.
                    incoming_rrule = (vals.get("rrule") or "").strip().upper()
                    raw_current = (event.recurrence_id.rrule or "").strip()
                    current_rrule = ""
                    for _line in raw_current.splitlines():
                        _line = _line.strip().upper()
                        if _line.startswith("RRULE:"):
                            current_rrule = _line[len("RRULE:"):]
                            break
                    if not current_rrule:
                        current_rrule = raw_current.upper()

                    if incoming_rrule and incoming_rrule != current_rrule:
                        _weekday_remap = {
                            "mo": "mon", "tu": "tue", "we": "wed",
                            "th": "thu", "fr": "fri", "sa": "sat", "su": "sun",
                        }
                        _odoo_weekday_fields = set(_weekday_remap.values())
                        write_vals = {}
                        # Reset all weekday booleans so stale flags don't corrupt the new series.
                        for _day_field in _odoo_weekday_fields:
                            write_vals[_day_field] = False
                        for _k, _v in vals.items():
                            if _k != "rrule":
                                write_vals[_weekday_remap.get(_k, _k)] = _v
                        write_vals["recurrence_update"] = "all_events"
                        _logger.info(
                            '[GOOGLE][PULL] RRULE changed for existing series "%s" (id=%s): '
                            '"%s" -> "%s". Re-applying recurrence.',
                            event.name, event.id, current_rrule, incoming_rrule,
                        )
                        event.with_context(**ctx_kwargs).write(write_vals)
                    else:
                        # RRULE unchanged — only update scalar fields (name, time, etc.)
                        vals.pop("rrule", None)
                        vals.pop("recurrence_update", None)
                        _logger.info(
                            '[GOOGLE][PULL] RRULE unchanged for series "%s" (id=%s). '
                            'Updating scalar fields only.',
                            event.name, event.id,
                        )
                        event.with_context(**ctx_kwargs).write(vals)
                    event.invalidate_recordset()

                    if event.recurrence_id:
                        new_base = event.recurrence_id.base_event_id
                        if new_base and new_base.exists() and new_base.id != event.id:
                            if not new_base.caldav_uid:
                                new_base.sudo().write({"caldav_uid": uid_value})
                            if existing_map:
                                existing_map.sudo().write({"event_id": new_base.id})
                            event = new_base

                        all_occs = (
                            self.env["calendar.event"]
                            .sudo()
                            .search(
                                [
                                    ("recurrence_id", "=", event.recurrence_id.id),
                                    ("active", "=", True),
                                ]
                            )
                        )
                        locked_count = 0
                        for occ in all_occs:
                            if not occ.caldav_original_start:
                                # Stamp original start to anchor the occurrence.
                                # Use no_sync=True to avoid Odoo ORM side-effects.
                                occ.with_context(no_sync=True).sudo().write(
                                    {
                                        "caldav_original_start": occ.start,
                                    }
                                )
                                locked_count += 1

                        if locked_count:
                            _logger.info(
                                '[GOOGLE][PULL] Locked %s occurrence(s) after promotion to series "%s".',
                                locked_count,
                                event.name,
                            )

                        # Clean up stale __occ_ maps from previous pinned pushes.
                        # recurrence_update='all_events' replaces all occurrence IDs;
                        # old maps now point to archived events and trigger spurious
                        # CalDAV DELETEs in the push phase.
                        stale_occ_maps = (
                            self.env["caldav.event.map"]
                            .sudo()
                            .search(
                                [
                                    ("account_id", "=", account.id),
                                    ("caldav_href", "=", href),
                                    ("caldav_uid", "like", "%__occ_%"),
                                ]
                            )
                        )
                        if stale_occ_maps:
                            _logger.info(
                                "[GOOGLE][PULL] Cleaning up %s stale occurrence map(s) "
                                'after series re-apply for "%s".',
                                len(stale_occ_maps),
                                event.name,
                            )
                            stale_occ_maps.sudo().unlink()

                else:
                    vals.pop("rrule", None)
                    vals.pop("recurrence_update", None)
                    # For Radicale/generic: if RECURRENCE-ID overrides are present,
                    # do NOT write occurrence-level fields (name, start, stop, location,
                    # description) from the base VEVENT here — that would propagate to
                    # all occurrences and overwrite individual overrides before
                    # _apply_icloud_occurrence_overrides runs below.
                    # Only write fields safe to apply globally (privacy, alarms, etc.).
                    if recurrence_id_vevents and account.server_type not in (
                        "google",
                        "zoho",
                        "icloud",
                    ):
                        safe_vals = {
                            k: v
                            for k, v in vals.items()
                            if k
                            not in (
                                "name",
                                "start",
                                "stop",
                                "allday",
                                "location",
                                "description",
                            )
                        }
                        if safe_vals:
                            event.with_context(**ctx_kwargs).write(safe_vals)
                    else:
                        event.with_context(**ctx_kwargs).write(vals)

            elif vals.get("rrule") and account.server_type == "zoho":
                _logger.info(
                    '[ZOHO][PULL] Promoting single event "%s" (id=%s) to recurring series.',
                    event.name,
                    event.id,
                )
                event.with_context(**ctx_kwargs).write(vals)

            elif vals.get("rrule") and account.server_type == "google":
                # CASE C: Single event being promoted to a recurring series for the first time.
                # event.recurrence_id was False, so we did NOT enter the upper if-block.
                #
                # IMPORTANT: Do NOT set recurrence_update='all_events' here.
                # recurrence_update is only meaningful for events that ALREADY belong
                # to a series. On a non-recurring event it causes Odoo to look for an
                # existing series, find none, and silently skip recurrence creation,
                # leaving the event non-recurring (or creating only 1 occurrence).
                # Just write the recurrence fields directly and Odoo will create the series.
                _weekday_remap = {
                    "mo": "mon",
                    "tu": "tue",
                    "we": "wed",
                    "th": "thu",
                    "fr": "fri",
                    "sa": "sat",
                    "su": "sun",
                }
                _odoo_weekday_fields = set(_weekday_remap.values())
                write_vals = {}
                # Reset all weekday booleans so stale flags don't corrupt the new series.
                for _day_field in _odoo_weekday_fields:
                    write_vals[_day_field] = False
                for _k, _v in vals.items():
                    if _k != "rrule":
                        write_vals[_weekday_remap.get(_k, _k)] = _v
                # Explicitly do NOT add recurrence_update here.
                _logger.info(
                    '[GOOGLE][PULL] CASE-C: Promoting single event "%s" (id=%s) to '
                    'recurring series. RRULE: %s  write_vals keys: %s',
                    event.name, event.id, vals.get("rrule"), list(write_vals.keys()),
                )
                event.with_context(**ctx_kwargs).write(write_vals)
                event.invalidate_recordset()

                if event.recurrence_id:
                    new_base = event.recurrence_id.base_event_id
                    if new_base and new_base.exists() and new_base.id != event.id:
                        if not new_base.caldav_uid:
                            new_base.sudo().write({"caldav_uid": uid_value})
                        if existing_map:
                            existing_map.sudo().write({"event_id": new_base.id})
                        event = new_base

                    all_occs = (
                        self.env["calendar.event"]
                        .sudo()
                        .search(
                            [
                                ("recurrence_id", "=", event.recurrence_id.id),
                                ("active", "=", True),
                            ]
                        )
                    )
                    locked_count = 0
                    for occ in all_occs:
                        if not occ.caldav_original_start:
                            occ.with_context(no_sync=True).sudo().write(
                                {
                                    "caldav_original_start": occ.start,
                                }
                            )
                            locked_count += 1
                    if locked_count:
                        _logger.info(
                            "[GOOGLE][PULL] CASE-C Locked %s occurrence(s) after "
                            'first-time promotion of "%s" to a recurring series.',
                            locked_count,
                            event.name,
                        )

                    # Same stale map cleanup as Location 1 — guards against
                    # spurious DELETEs if pinned occ maps existed before promotion.
                    stale_occ_maps = (
                        self.env["caldav.event.map"]
                        .sudo()
                        .search(
                            [
                                ("account_id", "=", account.id),
                                ("caldav_href", "=", href),
                                ("caldav_uid", "like", "%__occ_%"),
                            ]
                        )
                    )
                    if stale_occ_maps:
                        _logger.info(
                            "[GOOGLE][PULL] CASE-C Cleaning up %s stale occurrence map(s) "
                            'after first-time promotion of "%s".',
                            len(stale_occ_maps),
                            event.name,
                        )
                        stale_occ_maps.sudo().unlink()

            elif vals.get("rrule"):
                # --- Generic / Radicale: promote non-recurring event to recurring ---
                # Do NOT set recurrence_update='all_events' here.
                # recurrence_update is only meaningful for events that ALREADY belong
                # to a series. On a non-recurring event it causes Odoo to look for an
                # existing series, find none, and silently skip recurrence creation.
                # Just write the recurrence fields directly (recurrency=True + rrule_type
                # + end_type/count/until etc.) and Odoo will create the series.
                vals.pop("recurrence_update", None)
                _logger.info(
                    '[RADICALE][PULL] Promoting non-recurring event "%s" (id=%s) '
                    "to recurring series. RRULE: %s",
                    event.name,
                    event.id,
                    vals.get("rrule"),
                )
                event.with_context(**ctx_kwargs).write(vals)
                event.invalidate_recordset()
                _logger.info(
                    '[RADICALE][PULL] After promotion — event "%s" (id=%s) '
                    "recurrence_id=%s, recurrency=%s",
                    event.name,
                    event.id,
                    event.recurrence_id,
                    event.recurrency,
                )
            else:
                event.with_context(**ctx_kwargs).write(vals)
        else:
            vals["caldav_uid"] = uid_value
            event = CalEvent.create(vals)
            self.env["caldav.event.map"].sudo().create(
                {
                    "account_id": account.id,
                    "event_id": event.id,
                    "caldav_href": href,
                    "caldav_etag": server_etag,
                    "caldav_uid": uid_value,
                }
            )

        exdate_comps = getattr(vevent, "exdate_list", [])
        if not exdate_comps and getattr(vevent, "exdate", None):
            exdate_comps = [vevent.exdate]

        if exdate_comps and event.recurrence_id:
            excluded_dates = set()
            for comp in exdate_comps:
                raw_exdates = comp.value
                if not isinstance(raw_exdates, (list, tuple)):
                    raw_exdates = [raw_exdates]
                for ex in raw_exdates:
                    try:
                        if hasattr(ex, "date"):
                            excluded_dates.add(ex.date())
                        else:
                            from datetime import date as _date

                            excluded_dates.add(_date(ex.year, ex.month, ex.day))
                    except Exception:
                        pass

            override_starts = set()
            for override_vevent in recurrence_id_vevents:
                rid_comp = getattr(override_vevent, "recurrence_id", None)
                if rid_comp:
                    rid_val = rid_comp.value
                    try:
                        if hasattr(rid_val, "date"):
                            override_starts.add(rid_val.date())
                        else:
                            from datetime import date as _date

                            override_starts.add(
                                _date(rid_val.year, rid_val.month, rid_val.day)
                            )
                    except Exception:
                        pass

            if excluded_dates:
                if account.server_type == "zoho":
                    effective_exclusions = excluded_dates - override_starts
                else:
                    effective_exclusions = excluded_dates

                if effective_exclusions:
                    occurrences_to_delete = (
                        event.recurrence_id.calendar_event_ids.filtered(
                            lambda e: e.active
                            and (
                                (
                                    e.caldav_original_start.date()
                                    if e.caldav_original_start
                                    else (
                                        e.start_date
                                        if e.allday
                                        else (e.start.date() if e.start else None)
                                    )
                                )
                                in effective_exclusions
                            )
                        )
                    )
                    for occ in occurrences_to_delete:
                        occ_is_mapped_base = (
                            existing_map
                            and existing_map.exists()
                            and occ.id == existing_map.event_id.id
                        )
                        occ_recurrence = occ.recurrence_id
                        occ.with_context(no_caldav_delete=True).sudo().unlink()
                        if occ_is_mapped_base and occ_recurrence.exists():
                            new_base = occ_recurrence.base_event_id
                            if new_base and new_base.exists():
                                event = new_base
                                existing_map = None

        if not existing_map:
            existing_map = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [("account_id", "=", account.id), ("caldav_uid", "=", uid_value)],
                    limit=1,
                )
            )

        if recurrence_id_vevents:
            if account.server_type == "icloud":
                self._apply_icloud_occurrence_overrides(
                    recurrence_id_vevents, uid_value, account, href, server_etag
                )
            elif account.server_type == "zoho":
                self._apply_zoho_occurrence_overrides(
                    recurrence_id_vevents, uid_value, account, href, server_etag
                )
            elif account.server_type == "google":
                _logger.info(
                    '[GOOGLE][PULL] Applying %s RECURRENCE-ID override(s) to series "%s" (UID: %s).',
                    len(recurrence_id_vevents),
                    event.name,
                    uid_value,
                )
                self._apply_google_occurrence_overrides(
                    recurrence_id_vevents, uid_value, account, href, server_etag
                )
            else:
                # Generic / Radicale
                _logger.info(
                    '[RADICALE][PULL] Applying %s RECURRENCE-ID override(s) to series "%s" (UID: %s).',
                    len(recurrence_id_vevents),
                    event.name,
                    uid_value,
                )
                self._apply_icloud_occurrence_overrides(
                    recurrence_id_vevents, uid_value, account, href, server_etag
                )

        map_vals = {
            "account_id": account.id,
            "event_id": event.id,
            "caldav_uid": uid_value,
            "caldav_href": href,
            "caldav_etag": server_etag,
            "last_odoo_write": fields.Datetime.now(),
        }
        if existing_map:
            existing_map.sudo().write(map_vals)
        else:
            self.env["caldav.event.map"].sudo().create(map_vals)

        # --- Nextcloud / Generic CalDAV: send invitation emails to attendees ---
        # Google/Zoho/iCloud handle their own notification flows.
        # For generic CalDAV (Nextcloud/Radicale), Odoo's ORM does not automatically
        # trigger _send_mail_to_attendees() on pulled events, so we do it explicitly.
        if account.send_invitation_emails and account.server_type not in ("icloud"):
            try:
                attendees_to_notify = event.attendee_ids.filtered(
                    lambda a: a.state == "needsAction"
                    and a.partner_id
                    and a.partner_id.email
                    and a.partner_id.id != account.user_id.partner_id.id
                )
                if attendees_to_notify:
                    template = self.env.ref(
                        "calendar.calendar_template_meeting_invitation",
                        raise_if_not_found=False,
                    )
                    if template:
                        attendees_to_notify.sudo()._send_mail_to_attendees(template)
                        _logger.info(
                            '[NEXTCLOUD] Sent invitation emails to %s attendee(s) for event "%s".',
                            len(attendees_to_notify),
                            event.name,
                        )
            except Exception as _mail_err:
                _logger.warning(
                    '[NEXTCLOUD] Could not send invitation emails for event "%s": %s',
                    event.name,
                    _mail_err,
                )

        return event

    @api.model
    def _odoo_event_to_ical(self, event, account, existing_map=None):
        """Convert an Odoo ``calendar.event`` to an iCal VCALENDAR string."""
        if vobject is None:
            raise RuntimeError("vobject is required for iCal generation.")

        cal = vobject.iCalendar()
        cal.add("prodid").value = "-//Creyox Technologies//CalDAV Sync//EN"
        cal.add("version").value = "2.0"
        vevent = cal.add("vevent")
        uid = event.caldav_uid or str(uuid.uuid4())
        vevent.add("uid").value = uid
        vevent.add("dtstamp").value = datetime.now(pytz.utc)
        vevent.add("summary").value = event.name or ""

        if account.server_type in ("zoho", "google"):
            write_dt = event.write_date or datetime.utcnow()
            vevent.add("sequence").value = str(int(write_dt.timestamp()))
            vevent.add("last-modified").value = (
                write_dt.replace(tzinfo=pytz.utc)
                if write_dt.tzinfo is None
                else write_dt
            )

        original_start = event.start
        if existing_map and existing_map.google_exdates:
            try:
                exdates = [
                    datetime.strptime(d.strip(), "%Y%m%dT%H%M%SZ")
                    for d in existing_map.google_exdates.split(",")
                    if d.strip()
                ]
                if exdates:
                    min_ex = min(exdates)
                    current_start_naive = _to_utc_naive(original_start)
                    if min_ex < current_start_naive:
                        _logger.info(
                            "[ICAL] Shifting DTSTART back to %s "
                            "(earliest exdate precedes current base start %s). Account: %s.",
                            min_ex,
                            original_start,
                            account.name,
                        )
                        original_start = min_ex
            except Exception as e:
                _logger.warning(
                    "Could not calculate original DTSTART from EXDATEs: %s", e
                )

        duration = event.stop - event.start
        original_stop = original_start + duration

        if event.allday:
            dtstart = vevent.add("dtstart")
            dtstart.value = original_start.date()
            dtend = vevent.add("dtend")
            dtend.value = original_stop.date() + timedelta(days=1)
        else:
            start_utc = _to_utc_naive(original_start) or datetime.utcnow()
            stop_utc = _to_utc_naive(original_stop) or (start_utc + timedelta(hours=1))

            dtstart = vevent.add("dtstart")
            dtstart.value = datetime(
                start_utc.year,
                start_utc.month,
                start_utc.day,
                start_utc.hour,
                start_utc.minute,
                start_utc.second,
                tzinfo=pytz.utc,
            )
            dtend = vevent.add("dtend")
            dtend.value = datetime(
                stop_utc.year,
                stop_utc.month,
                stop_utc.day,
                stop_utc.hour,
                stop_utc.minute,
                stop_utc.second,
                tzinfo=pytz.utc,
            )

        if event.location:
            vevent.add("location").value = event.location

        # --- Apple (iCloud) & Zoho: map videocall_location → URL field on push ---
        # Only iCloud/Zoho use the iCal URL property for video call links.
        # We check both server_type and the URL string itself for 'icloud' to be extra safe.
        is_apple = account.server_type == "icloud" or (
            account.url and "icloud.com" in account.url
        )
        if (is_apple or account.server_type == "zoho") and event.videocall_location:
            _logger.info(
                "[PUSH] Setting iCal URL for %s: %s",
                account.name,
                event.videocall_location,
            )
            vevent.add("url").value = event.videocall_location

        _privacy_to_class = {
            "public": "PUBLIC",
            "private": "PRIVATE",
            "confidential": "CONFIDENTIAL",
        }
        class_val = _privacy_to_class.get(event.privacy or "public", "PUBLIC")
        vevent.add("class").value = class_val

        if event.description:
            plain = html2plaintext(event.description or "").strip()
            if plain:
                vevent.add("description").value = plain

        rrule_value = None
        if event.recurrence_id:
            raw = event.recurrence_id.rrule or ""
            for line in raw.splitlines():
                line = line.strip()
                if line.upper().startswith("RRULE:"):
                    rrule_value = line[len("RRULE:") :]
                elif line.upper().startswith("EXDATE:"):
                    exdate_value = line[len("EXDATE:") :].strip()
                    if event.allday:
                        try:
                            ex_dt = datetime.strptime(
                                exdate_value, "%Y%m%dT%H%M%SZ"
                            ).date()
                            vevent.add("exdate").value = [ex_dt]
                        except ValueError:
                            try:
                                ex_dt = datetime.strptime(exdate_value, "%Y%m%d").date()
                                vevent.add("exdate").value = [ex_dt]
                            except ValueError:
                                _logger.warning(
                                    'Could not parse EXDATE (all-day) "%s".',
                                    exdate_value,
                                )
                    else:
                        try:
                            ex_dt = datetime.strptime(
                                exdate_value, "%Y%m%dT%H%M%SZ"
                            ).replace(tzinfo=pytz.utc)
                            vevent.add("exdate").value = [ex_dt]
                        except ValueError:
                            _logger.warning(
                                'Could not parse EXDATE (timed) "%s".', exdate_value
                            )

            if existing_map and existing_map.google_exdates:
                _logger.debug(
                    '[ICAL] Injecting stored EXDATEs for "%s" (account: %s): %s',
                    event.name,
                    account.name,
                    existing_map.google_exdates,
                )
                for iso_dt in existing_map.google_exdates.split(","):
                    iso_dt = iso_dt.strip()
                    if not iso_dt or iso_dt in raw:
                        continue
                    try:
                        ex_dt = datetime.strptime(iso_dt, "%Y%m%dT%H%M%SZ").replace(
                            tzinfo=pytz.utc
                        )
                        # Skip EXDATEs that fall before DTSTART — already excluded by
                        # the shifted base start (adding them causes COUNT to expand extra occurrences on iCloud).
                        ex_dt_naive = ex_dt.replace(tzinfo=None)
                        orig_start_naive = _to_utc_naive(original_start)
                        if (
                            orig_start_naive
                            and ex_dt_naive.date() < orig_start_naive.date()
                        ):
                            _logger.debug(
                                "[ICAL] Skipping EXDATE %s: before DTSTART %s (already excluded by shift).",
                                iso_dt,
                                orig_start_naive.date(),
                            )
                            continue
                        ex = vevent.add("exdate")
                        if event.allday:
                            ex.value = [ex_dt.date()]
                        else:
                            ex.value = [ex_dt]
                    except ValueError:
                        _logger.warning("Could not parse stored EXDATE: %s", iso_dt)

            if not rrule_value and raw and not raw.upper().startswith("DTSTART"):
                rrule_value = raw.strip("RRULE:") if raw.startswith("RRULE:") else raw
        if not rrule_value and hasattr(event, "rrule") and event.rrule:
            raw = event.rrule
            for line in raw.splitlines():
                line = line.strip()
                if line.upper().startswith("RRULE:"):
                    rrule_value = line[len("RRULE:") :]
                    break
            if not rrule_value:
                rrule_value = raw.lstrip("RRULE:") if raw.startswith("RRULE:") else raw
        if rrule_value:
            _logger.info(
                'Adding RRULE to iCal for event "%s": %s', event.name, rrule_value
            )
            vevent.add("rrule").value = rrule_value

        if account.server_type == "google" and event.recurrence_id:
            uid = event.caldav_uid or str(uuid.uuid4())

            excluded_starts = set()
            if existing_map and existing_map.google_exdates:
                for iso_dt in existing_map.google_exdates.split(","):
                    iso_dt = iso_dt.strip()
                    if iso_dt:
                        try:
                            excluded_starts.add(
                                datetime.strptime(iso_dt, "%Y%m%dT%H%M%SZ")
                            )
                        except ValueError:
                            pass

            all_occurrences = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", event.recurrence_id.id),
                        ("active", "=", True),
                    ]
                )
            )
            for occ in all_occurrences:
                occ_start_naive = _to_utc_naive(occ.start)
                if occ_start_naive in excluded_starts:
                    continue
                original_start_naive = _to_utc_naive(original_start)
                event_start_naive = _to_utc_naive(event.start)
                original_was_shifted = original_start_naive != event_start_naive

                if not original_was_shifted and occ_start_naive == original_start_naive:
                    continue

                    # Only emit a RECURRENCE-ID override if this occurrence actually
                    # differs from the base. Unmodified occurrences are derived from
                    # the RRULE automatically by Google; no override needed.
                if not original_was_shifted and not self._occurrence_differs_from_base(
                    occ, event
                ):
                    continue

                ovr = cal.add("vevent")
                ovr.add("uid").value = uid
                ovr.add("dtstamp").value = datetime.now(pytz.utc)
                ovr.add("summary").value = occ.name or ""

                if occ.allday:
                    rid = ovr.add("recurrence-id")
                    rid.value = occ.start.date()
                else:
                    rid = ovr.add("recurrence-id")
                    rid.value = datetime(
                        occ_start_naive.year,
                        occ_start_naive.month,
                        occ_start_naive.day,
                        occ_start_naive.hour,
                        occ_start_naive.minute,
                        occ_start_naive.second,
                        tzinfo=pytz.utc,
                    )

                if occ.allday:
                    ovr.add("dtstart").value = occ.start.date()
                    ovr.add("dtend").value = occ.stop.date() + timedelta(days=1)
                else:
                    stop_naive = _to_utc_naive(occ.stop)
                    ovr.add("dtstart").value = datetime(
                        occ_start_naive.year,
                        occ_start_naive.month,
                        occ_start_naive.day,
                        occ_start_naive.hour,
                        occ_start_naive.minute,
                        occ_start_naive.second,
                        tzinfo=pytz.utc,
                    )
                    ovr.add("dtend").value = datetime(
                        stop_naive.year,
                        stop_naive.month,
                        stop_naive.day,
                        stop_naive.hour,
                        stop_naive.minute,
                        stop_naive.second,
                        tzinfo=pytz.utc,
                    )

                if occ.location:
                    ovr.add("location").value = occ.location
                if occ.description:
                    plain = html2plaintext(occ.description or "").strip()
                    if plain:
                        ovr.add("description").value = plain

        # --- Radicale / Generic CalDAV: RECURRENCE-ID occurrence overrides ---
        # When pushing a recurring series base to a generic CalDAV server, other
        # occurrences that differ from the base would be silently overwritten by the
        # base RRULE template. We must inject RECURRENCE-ID VEVENTs for any occurrence
        # whose name, time, location or description differs from the base event.
        #
        # Example: base="1st" (user changed first occ), occ2/3/4="test"
        #   → push base VEVENT (RRULE, SUMMARY=1st) alone → Radicale sets ALL to "1st"
        #   → with this fix  → occ2/3/4 each get a RECURRENCE-ID VEVENT (SUMMARY=test)
        #
        # STRICTLY guarded: only runs for generic/Radicale (not google/zoho/icloud).
        if (
            account.server_type not in ("google", "zoho", "icloud")
            and event.recurrence_id
        ):
            uid_for_overrides = event.caldav_uid or str(uuid.uuid4())
            base_start_naive = _to_utc_naive(event.start)

            all_occs = (
                self.env["calendar.event"]
                .sudo()
                .search(
                    [
                        ("recurrence_id", "=", event.recurrence_id.id),
                        ("active", "=", True),
                        ("id", "!=", event.id),  # exclude base event itself
                    ]
                )
            )

            for occ in all_occs:
                # Determine if this occurrence meaningfully differs from the base.
                # We compare: name, location, description, start/stop time.
                name_differs = (occ.name or "") != (event.name or "")
                loc_differs = (occ.location or "") != (event.location or "")
                desc_differs = (occ.description or "") != (event.description or "")
                occ_start_naive = _to_utc_naive(occ.start)
                # Duration may be the same even if absolute times differ (RRULE shift);
                # only flag if the TIME-OF-DAY itself differs (not just the date).
                time_differs = (
                    (
                        occ.start
                        and event.start
                        and occ.start.hour != event.start.hour
                        or occ.start.minute != event.start.minute
                    )
                    if occ.start and event.start
                    else False
                )

                if not (name_differs or loc_differs or desc_differs or time_differs):
                    continue  # occurrence matches base template — no override needed

                # Build RECURRENCE-ID VEVENT
                ovr = cal.add("vevent")
                ovr.add("uid").value = uid_for_overrides
                ovr.add("dtstamp").value = datetime.now(pytz.utc)
                ovr.add("summary").value = occ.name or ""

                # RECURRENCE-ID: use the ORIGINAL scheduled start of this occurrence
                # (caldav_original_start if available, else the current start)
                rid_start = _to_utc_naive(occ.caldav_original_start or occ.start)

                if occ.allday:
                    ovr.add("recurrence-id").value = (
                        (occ.caldav_original_start or occ.start).date()
                        if occ.caldav_original_start
                        else occ.start.date()
                    )
                    ovr.add("dtstart").value = occ.start.date()
                    ovr.add("dtend").value = occ.stop.date() + timedelta(days=1)
                else:
                    ovr.add("recurrence-id").value = datetime(
                        rid_start.year,
                        rid_start.month,
                        rid_start.day,
                        rid_start.hour,
                        rid_start.minute,
                        rid_start.second,
                        tzinfo=pytz.utc,
                    )
                    ovr.add("dtstart").value = datetime(
                        occ_start_naive.year,
                        occ_start_naive.month,
                        occ_start_naive.day,
                        occ_start_naive.hour,
                        occ_start_naive.minute,
                        occ_start_naive.second,
                        tzinfo=pytz.utc,
                    )
                    stop_naive = _to_utc_naive(occ.stop)
                    ovr.add("dtend").value = datetime(
                        stop_naive.year,
                        stop_naive.month,
                        stop_naive.day,
                        stop_naive.hour,
                        stop_naive.minute,
                        stop_naive.second,
                        tzinfo=pytz.utc,
                    )

                if occ.location:
                    ovr.add("location").value = occ.location
                if occ.description:
                    from odoo.tools import html2plaintext as _h2p

                    _plain = _h2p(occ.description or "").strip()
                    if _plain:
                        ovr.add("description").value = _plain

                _logger.info(
                    "[RADICALE][PUSH] Added RECURRENCE-ID override for occurrence "
                    '"%s" (id=%s, start=%s) in series "%s".',
                    occ.name,
                    occ.id,
                    occ.start,
                    event.name,
                )

        other_partners = event.partner_ids.filtered(
            lambda p: p != account.user_id.partner_id
        )

        if other_partners:
            owner = account.user_id.partner_id
            org = vevent.add("organizer")

            if account.server_type == "google":
                from urllib.parse import urlparse

                google_email = None
                try:
                    path_parts = urlparse(account.url).path.strip("/").split("/")
                    if len(path_parts) >= 3:
                        google_email = path_parts[2]
                except Exception:
                    pass
                org_email = google_email or owner.email or account.username
            elif account.server_type in ("zoho", "icloud"):
                org_email = account.username or owner.email
            else:
                org_email = owner.email or account.username

            org.value = f"mailto:{org_email}"
            org.params["CN"] = [owner.name or org_email]

            for partner in event.partner_ids:
                if not partner.email:
                    continue
                att = vevent.add("attendee")
                att.value = f"mailto:{partner.email}"
                att.params["CN"] = [partner.name or partner.email]
                att.params["PARTSTAT"] = ["ACCEPTED"]

        for alarm in event.alarm_ids:
            """Add a VALARM for each reminder configured on the event."""
            valarm = vevent.add("valarm")
            if account.server_type == "zoho" and alarm.alarm_type == "notification":
                valarm.add("action").value = "DISPLAY"
                valarm.add("x-action").value = "NOTIFICATION"
            else:
                action = "EMAIL" if alarm.alarm_type == "email" else "DISPLAY"
                valarm.add("action").value = action
            valarm.add("description").value = alarm.name or "Reminder"

            minutes = alarm.duration_minutes or 0
            valarm.add("trigger").value = timedelta(minutes=-minutes)

        return cal.serialize()

    @api.model
    def _migrate_recurrence_mappings(self, account):
        """Finds sync mappings for archived base events and transfers them to new active bases."""
        inactive_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("account_id", "=", account.id),
                    ("event_id.active", "=", False),
                ]
            )
        )
        for map_rec in inactive_maps:
            old_event = map_rec.event_id
            if old_event.recurrence_id:
                new_base = old_event.recurrence_id.base_event_id
                if new_base and new_base.active and new_base.id != old_event.id:
                    _logger.info(
                        "Migrating CalDAV mapping for recurrence %s: %s -> %s",
                        old_event.recurrence_id.id,
                        old_event.id,
                        new_base.id,
                    )
                    map_rec.sudo().write({"event_id": new_base.id})

    def _ical_to_odoo_vals(self, vevent, account):
        """Parse a vobject VEVENT component into Odoo calendar.event field values."""
        try:
            vals = {}

            summary = getattr(vevent, "summary", None)
            vals["name"] = summary.value if summary else "(No Title)"

            dtstart_comp = getattr(vevent, "dtstart", None)
            dtend_comp = getattr(vevent, "dtend", None)
            duration_comp = getattr(vevent, "duration", None)

            if dtstart_comp is None:
                return {}

            dtstart_val = dtstart_comp.value
            allday = _is_date_only(dtstart_val)
            vals["allday"] = allday

            if allday:
                vals["start"] = datetime(
                    dtstart_val.year, dtstart_val.month, dtstart_val.day, 8, 0, 0
                )
                if dtend_comp and dtend_comp.value:
                    dtend_val = dtend_comp.value
                    if _is_date_only(dtend_val):
                        end_date = date(
                            dtend_val.year, dtend_val.month, dtend_val.day
                        ) - timedelta(days=1)
                        vals["stop"] = datetime(
                            end_date.year, end_date.month, end_date.day, 18, 0, 0
                        )
                    else:
                        vals["stop"] = _to_utc_naive(dtend_val)
                else:
                    vals["stop"] = datetime(
                        dtstart_val.year, dtstart_val.month, dtstart_val.day, 18, 0, 0
                    )
            else:
                start_utc = _to_utc_naive(dtstart_val)
                if start_utc is None:
                    return {}
                vals["start"] = start_utc
                if dtend_comp and dtend_comp.value:
                    stop_val = _to_utc_naive(dtend_comp.value)
                    vals["stop"] = stop_val or (start_utc + timedelta(hours=1))
                elif duration_comp and duration_comp.value:
                    dur = duration_comp.value
                    vals["stop"] = start_utc + dur
                else:
                    vals["stop"] = start_utc + timedelta(hours=1)

            location_comp = getattr(vevent, "location", None)
            if location_comp and location_comp.value:
                vals["location"] = location_comp.value

            # --- Apple (iCloud) & Zoho: map URL field → videocall_location on pull ---
            # Only iCloud/Zoho use the iCal URL property for video call links.
            # Google and other servers are intentionally NOT touched here.
            if account.server_type in ("icloud", "zoho"):
                url_comp = getattr(vevent, "url", None)
                vals["videocall_location"] = (
                    url_comp.value if (url_comp and url_comp.value) else False
                )

            desc_comp = getattr(vevent, "description", None)
            if desc_comp and desc_comp.value:
                description = desc_comp.value

                if account.server_type == "google":
                    url_search = re.search(
                        r"https://meet\.google\.com/[a-z0-9\-]+", description
                    )
                    if url_search:
                        vals["videocall_location"] = url_search.group(0)
                        _logger.debug(
                            "Extracted Google Meet URL: %s", vals["videocall_location"]
                        )

                    markers = ["Join with Google Meet", "-::~"]
                    first_idx = len(description)
                    found = False
                    for marker in markers:
                        idx = description.find(marker)
                        if idx != -1:
                            first_idx = min(first_idx, idx)
                            found = True

                    if found:
                        description = description[:first_idx].strip()

                if description:
                    vals["description"] = (
                        f'<p>{description.replace(chr(10), "<br/>")}</p>'
                    )
                else:
                    vals["description"] = False

                if description:
                    vals["description"] = (
                        f'<p>{description.replace(chr(10), "<br/>")}</p>'
                    )
                else:
                    vals["description"] = False

            _class_to_privacy = {
                "PUBLIC": "public",
                "PRIVATE": "private",
                "CONFIDENTIAL": "confidential",
            }
            class_comp = getattr(vevent, "class", None)
            if class_comp and class_comp.value:
                privacy = _class_to_privacy.get(class_comp.value.upper(), "public")
                vals["privacy"] = privacy

            rrule_comp = getattr(vevent, "rrule", None)
            if rrule_comp and rrule_comp.value:
                rrule_str = rrule_comp.value
                if isinstance(rrule_str, dict):
                    parts = []
                    for k, v in rrule_str.items():
                        if isinstance(v, list):
                            v = ",".join(str(x) for x in v)
                        parts.append(f"{k}={v}")
                    rrule_str = ";".join(parts)

                # --- Normalize RRULE UNTIL: strip trailing Z suffix ---
                # Radicale / Thunderbird write UNTIL in UTC with a Z suffix,
                # e.g. UNTIL=20260430T113000Z.  Odoo's _rrule_parse passes a
                # timezone-naive start_dt to dateutil.  When UNTIL is tz-aware
                # (has Z) and dtstart is naive, dateutil raises:
                #   "can't compare offset-naive and offset-aware datetimes"
                # That exception is silently caught below, leaving vals without
                # 'rrule' and 'recurrency', so the event stays non-recurring.
                # Fix: strip the Z so UNTIL is also naive-UTC, consistent with
                # how we store all datetimes internally.
                _rrule_str_normalized = re.sub(
                    r"(UNTIL=\d{8}T\d{6})Z\b",
                    r"\1",
                    rrule_str,
                    flags=re.IGNORECASE,
                )
                if _rrule_str_normalized != rrule_str:
                    _logger.debug(
                        '[RRULE] Normalized UNTIL Z-suffix: "%s" -> "%s"',
                        rrule_str,
                        _rrule_str_normalized,
                    )
                    rrule_str = _rrule_str_normalized

                try:
                    start_dt = vals.get("start") or datetime.utcnow()
                    recurrence_vals = self.env["calendar.recurrence"]._rrule_parse(
                        f"FREQ={rrule_str}" if "FREQ=" not in rrule_str else rrule_str,
                        start_dt,
                    )
                    vals["recurrency"] = True
                    vals.update(recurrence_vals)
                    vals["rrule"] = rrule_str
                except Exception as e:
                    _logger.warning('Could not parse RRULE "%s": %s', rrule_str, e)

            attendee_components = []
            try:
                attendee_components = list(vevent.attendee_list)
            except AttributeError:
                pass

            partner_ids = []
            partner_ids.append(account.user_id.partner_id.id)

            for att in attendee_components:
                email_val = att.value
                if email_val.lower().startswith("mailto:"):
                    email_val = email_val[7:]
                partner = (
                    self.env["res.partner"]
                    .sudo()
                    .search([("email", "=ilike", email_val)], limit=1)
                )
                if not partner and account.auto_create_contacts and email_val:
                    cn = att.params.get("CN", [email_val])
                    cn = cn[0] if isinstance(cn, list) else cn
                    partner = (
                        self.env["res.partner"]
                        .sudo()
                        .create(
                            {
                                "name": cn or email_val,
                                "email": email_val,
                            }
                        )
                    )
                if partner:
                    partner_ids.append(partner.id)

            alarm_ids = []
            try:
                for component in vevent.components():
                    if component.name != "VALARM":
                        continue
                    trigger_comp = getattr(component, "trigger", None)
                    action_comp = getattr(component, "action", None)
                    if not trigger_comp:
                        continue
                    trigger_val = trigger_comp.value
                    if hasattr(trigger_val, "total_seconds"):
                        total_secs = abs(trigger_val.total_seconds())
                        trigger_minutes = int(total_secs // 60)
                    else:
                        continue
                    action_str = (
                        action_comp.value if action_comp else "DISPLAY"
                    ).upper()
                    alarm_type = "email" if action_str == "EMAIL" else "notification"
                    alarm = (
                        self.env["calendar.alarm"]
                        .sudo()
                        .search(
                            [
                                ("alarm_type", "=", alarm_type),
                                ("duration_minutes", "=", trigger_minutes),
                            ],
                            limit=1,
                        )
                    )
                    if not alarm:
                        alarm = (
                            self.env["calendar.alarm"]
                            .sudo()
                            .search(
                                [("duration_minutes", "=", trigger_minutes)], limit=1
                            )
                        )
                    if not alarm and trigger_minutes > 0:
                        all_alarms = self.env["calendar.alarm"].sudo().search([])
                        alarm = min(
                            all_alarms,
                            key=lambda a: abs(a.duration_minutes - trigger_minutes),
                            default=None,
                        )
                    if alarm:
                        alarm_ids.append(alarm.id)
            except Exception as ex:
                _logger.warning("Could not parse VALARM: %s", ex)
            if alarm_ids:
                vals["alarm_ids"] = [(6, 0, list(set(alarm_ids)))]

            if partner_ids:
                vals["partner_ids"] = [(6, 0, list(set(partner_ids)))]

            vals["user_id"] = account.user_id.id

            return vals

        except Exception as e:
            _logger.warning("Failed to parse VEVENT: %s", e, exc_info=True)
            return {}

    @api.model
    def action_sync_current_user(self):
        """Sync all active CalDAV accounts for the current user."""
        accounts = self.env["caldav.account"].search(
            [
                ("user_id", "=", self.env.uid),
                ("active", "=", True),
            ]
        )
        total_pushed = total_pulled = total_deleted = 0
        for account in accounts:
            try:
                stats = self.sync_account(account)
                total_pushed += stats.get("pushed", 0)
                total_pulled += stats.get("pulled", 0)
                total_deleted += stats.get("deleted", 0)
            except Exception as e:
                _logger.error(
                    "Sync error for account %s: %s", account.name, e, exc_info=True
                )

        if not accounts:
            message = "No active CalDAV accounts configured. Go to Settings → Calendar to add one."
            msg_type = "warning"
        else:
            message = (
                f"CalDAV Sync complete — {total_pushed} pushed, "
                f"{total_pulled} pulled, {total_deleted} deleted."
            )
            msg_type = "success"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "CalDAV Sync",
                "message": message,
                "type": msg_type,
                "sticky": False,
            },
        }