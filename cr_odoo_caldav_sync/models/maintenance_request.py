# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    """Extends the Odoo maintenance.request model for CalDAV synchronisation."""

    _inherit = "maintenance.request"

    caldav_uid = fields.Char(
        string="CalDAV UID",
        copy=False,
        index=True,
        help="UUID used as the iCal UID for this request. Generated automatically.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign a CalDAV UID to every new maintenance request.

        :param list vals_list: List of field-value dicts for new maintenance requests.
        :return: Newly created maintenance request recordset.
        :rtype: recordset
        """
        for vals in vals_list:
            if not vals.get("caldav_uid"):
                vals["caldav_uid"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, values):
        """Override write to auto-assign CalDAV UID if missing.

        :param dict values: Field-value pairs to update.
        :return: True on success.
        :rtype: bool
        """
        for record in self:
            if not record.caldav_uid:
                values.setdefault("caldav_uid", str(uuid.uuid4()))

        return super().write(values)

    def unlink(self):
        """Intercept deletion to propagate CalDAV removals."""
        req_ids = self.ids
        _logger.info("[UNLINK] Triggered for maintenance request ids: %s", req_ids)

        all_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("maintenance_request_id", "in", req_ids),
                ]
            )
        )
        _logger.debug(
            "[UNLINK] Found %s mapping records for these maintenance requests.", len(all_maps)
        )

        for map_rec in all_maps:
            try:
                _logger.info(
                    '[UNLINK] CalDAV DELETE: maintenance request "%s" (id=%s) via account %s at %s',
                    map_rec.maintenance_request_id.name,
                    map_rec.maintenance_request_id.id,
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
