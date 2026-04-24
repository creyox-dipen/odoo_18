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

    _inherit = "calendar.event"

    caldav_uid = fields.Char(
        string="CalDAV UID",
        copy=False,
        index=True,
        help="UUID used as the iCal UID for this event. Generated automatically.",
    )

    caldav_original_start = fields.Datetime(
        string="CalDAV Original Start",
        copy=False,
        help="The original start datetime of this occurrence before it was modified. "
        "Used as the RECURRENCE-ID in CalDAV sync to identify which occurrence "
        "is being overridden.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign a CalDAV UID to every new event.

        :param list vals_list: List of field-value dicts for new events.
        :return: Newly created calendar event recordset.
        :rtype: recordset
        """
        for vals in vals_list:
            if not vals.get("caldav_uid"):
                vals["caldav_uid"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, values):
        """Override write to auto-assign CalDAV UID if missing and track original start.

        Ensures events created before module installation also receive a UID
        on their next write operation. Also captures the original start date
        for recurring occurrences before they are moved, ensuring RECURRENCE-ID
        consistency during sync.

        :param dict values: Field-value pairs to update.
        :return: True on success.
        :rtype: bool
        """
        for record in self:
            if not record.caldav_uid:
                values.setdefault("caldav_uid", str(uuid.uuid4()))

            # If start is changing and this is a recurring occurrence that doesn't
            # have an original start yet, record the CURRENT start as original.
            if (
                "start" in values
                and record.recurrence_id
                and not record.caldav_original_start
            ):
                values["caldav_original_start"] = record.start

        return super().write(values)

    def unlink(self):
        """Intercept deletion to propagate CalDAV removals."""
        event_ids = self.ids
        _logger.info("[UNLINK] Triggered for event ids: %s", event_ids)

        all_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("event_id", "in", event_ids),
                ]
            )
        )
        _logger.debug(
            "[UNLINK] Found %s mapping records for these events.", len(all_maps)
        )

        sync_svc = self.env["caldav.sync.service"]

        handled_map_ids = set()

        for event in self:
            if not event.recurrence_id:
                continue
            recurrence = event.recurrence_id
            base_event = recurrence.base_event_id

            if not base_event:
                continue

            original_start = event.caldav_original_start or event.start
            start_iso = (
                original_start.strftime("%Y%m%dT%H%M%SZ") if original_start else None
            )

            google_base_maps = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("event_id", "=", base_event.id),
                        ("account_id.server_type", "=", "google"),
                    ]
                )
            )
            seen_google_accounts = set()

            for g_map in google_base_maps:
                handled_map_ids.add(g_map.id)
                if event.id == base_event.id:
                    # Deduplicate: if we already handled this account, just clean up the extra map
                    if g_map.account_id.id in seen_google_accounts:
                        _logger.info(
                            "[UNLINK] Scenario B (Google): Duplicate map id=%s for account %s — unlinking.",
                            g_map.id,
                            g_map.account_id.name,
                        )
                        # Keep in handled_map_ids so generic DELETE block skips it
                        continue
                    seen_google_accounts.add(g_map.account_id.id)

                    _logger.info(
                        "[UNLINK] Scenario B (Google): Base Delete (id=%s)", event.id
                    )
                    next_occ = (
                        self.env["calendar.event"]
                        .sudo()
                        .search(
                            [
                                ("recurrence_id", "=", recurrence.id),
                                ("active", "=", True),
                                ("id", "not in", event_ids),
                            ],
                            order="start asc",
                            limit=1,
                        )
                    )

                    if next_occ:
                        if next_occ.caldav_uid != g_map.caldav_uid:
                            next_occ.sudo().write({"caldav_uid": g_map.caldav_uid})
                        ex_list = set(
                            d for d in (g_map.google_exdates or "").split(",") if d
                        )
                        if start_iso:
                            ex_list.add(start_iso)
                        new_exdates = ",".join(sorted(ex_list))
                        g_map.sudo().write(
                            {
                                "event_id": next_occ.id,
                                "last_odoo_write": False,
                                "google_exdates": new_exdates,
                            }
                        )
                    else:
                        handled_map_ids.discard(g_map.id)
                else:
                    _logger.info(
                        "[UNLINK] Scenario A (Google): Occurrence Delete (id=%s)",
                        event.id,
                    )
                    ex_list = set(
                        d for d in (g_map.google_exdates or "").split(",") if d
                    )
                    if start_iso:
                        ex_list.add(start_iso)
                    new_exdates = ",".join(sorted(ex_list))
                    g_map.sudo().write(
                        {"google_exdates": new_exdates, "last_odoo_write": False}
                    )

                    # Mark the occurrence's OWN map as handled so the generic
                    # DELETE block below does not attempt to DELETE the base .ics
                    occ_maps = (
                        self.env["caldav.event.map"]
                        .sudo()
                        .search(
                            [
                                ("event_id", "=", event.id),
                                ("account_id", "=", g_map.account_id.id),
                            ]
                        )
                    )
                    for occ_map in occ_maps:
                        handled_map_ids.add(occ_map.id)

            basic_base_maps = (
                self.env["caldav.event.map"]
                .sudo()
                .search(
                    [
                        ("event_id", "=", base_event.id),
                        ("account_id.server_type", "!=", "google"),
                    ]
                )
            )
            _logger.info(
                '[UNLINK] Basic Auth: found %s map(s) for base_event id=%s ("%s").',
                len(basic_base_maps),
                base_event.id,
                base_event.name,
            )

            for b_map in basic_base_maps:
                handled_map_ids.add(b_map.id)
                _logger.info(
                    "[UNLINK] Basic Auth: processing map id=%s, href=%s, account=%s.",
                    b_map.id,
                    b_map.caldav_href,
                    b_map.account_id.name,
                )
                if event.id == base_event.id:
                    _logger.info(
                        "[UNLINK] Scenario B (Basic): Base Delete (id=%s, start=%s)",
                        event.id,
                        start_iso,
                    )
                    next_occ = (
                        self.env["calendar.event"]
                        .sudo()
                        .search(
                            [
                                ("recurrence_id", "=", recurrence.id),
                                ("active", "=", True),
                                ("id", "not in", event_ids),
                            ],
                            order="start asc",
                            limit=1,
                        )
                    )

                    if next_occ:
                        if next_occ.caldav_uid != b_map.caldav_uid:
                            _logger.info(
                                "[UNLINK] Scenario B (Basic): Copying UID from map (%s) "
                                "to next_occ (id=%s, current uid=%s) so href and iCal UID match.",
                                b_map.caldav_uid,
                                next_occ.id,
                                next_occ.caldav_uid,
                            )
                            next_occ.sudo().write({"caldav_uid": b_map.caldav_uid})

                        ex_list = set(
                            d.strip()
                            for d in (b_map.google_exdates or "").split(",")
                            if d.strip()
                        )
                        if start_iso:
                            ex_list.add(start_iso)
                        new_exdates = ",".join(sorted(ex_list))
                        _logger.info(
                            "[UNLINK] Scenario B (Basic): Accumulated EXDATEs for map id=%s: %s",
                            b_map.id,
                            new_exdates,
                        )
                        b_map.sudo().write(
                            {
                                "event_id": next_occ.id,
                                "google_exdates": new_exdates,
                                "last_odoo_write": False,
                            }
                        )
                    else:

                        _logger.info(
                            "[UNLINK] Scenario C (Basic): Last occurrence — will DELETE series."
                        )
                        handled_map_ids.discard(b_map.id)
                else:
                    ex_list = set(
                        d.strip()
                        for d in (b_map.google_exdates or "").split(",")
                        if d.strip()
                    )
                    if start_iso:
                        ex_list.add(start_iso)
                    new_exdates = ",".join(sorted(ex_list))
                    _logger.info(
                        "[UNLINK] Scenario A (Basic): Occurrence Delete (id=%s, start=%s). "
                        "Accumulated EXDATEs for map id=%s: %s",
                        event.id,
                        start_iso,
                        b_map.id,
                        new_exdates,
                    )

                    b_map.sudo().write(
                        {"google_exdates": new_exdates, "last_odoo_write": False}
                    )
                    occ_maps = (
                        self.env["caldav.event.map"]
                        .sudo()
                        .search(
                            [
                                ("event_id", "=", event.id),
                                ("account_id", "=", b_map.account_id.id),
                            ]
                        )
                    )
                    for occ_map in occ_maps:
                        handled_map_ids.add(occ_map.id)

        for map_rec in all_maps:
            if not map_rec.exists():
                continue

            if map_rec.id in handled_map_ids:
                _logger.debug(
                    "[UNLINK] Map id=%s already handled by recurring logic, skipping DELETE.",
                    map_rec.id,
                )
                continue
            if map_rec.event_id and map_rec.event_id.id not in event_ids:
                _logger.debug(
                    "[UNLINK] Map id=%s was promoted to next occurrence, skipping DELETE.",
                    map_rec.id,
                )
                continue

            if (
                map_rec.event_id
                and map_rec.event_id.recurrence_id
                and map_rec.event_id.id
                != map_rec.event_id.recurrence_id.base_event_id.id
            ):
                _logger.info(
                    "[UNLINK] Map id=%s belongs to occurrence. Skipping HTTP DELETE to prevent series wipe.",
                    map_rec.id,
                )
                map_rec.unlink()
                continue

            try:
                _logger.info(
                    '[UNLINK] CalDAV DELETE: event "%s" (id=%s) via account %s at %s',
                    map_rec.event_id.name,
                    map_rec.event_id.id,
                    map_rec.account_id.name,
                    map_rec.caldav_href,
                )
                map_rec.account_id._delete_event(
                    map_rec.caldav_href, etag=map_rec.caldav_etag
                )
            except Exception as ex:
                _logger.warning("[UNLINK] Direct CalDAV DELETE failed: %s", ex)
            map_rec.unlink()

        return super().unlink()

    def caldav_sync_action(self):
        """Trigger a CalDAV sync for the current user from the calendar view button."""
        return self.env["caldav.sync.service"].action_sync_current_user()
