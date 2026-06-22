# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class FSMOrder(models.Model):
    """Extends the Odoo fsm.order model for CalDAV synchronisation."""

    _inherit = "fsm.order"

    caldav_uid = fields.Char(
        string="CalDAV UID",
        copy=False,
        index=True,
        help="UUID used as the iCal UID for this FSM order. Generated automatically.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign a CalDAV UID to every new FSM order.

        :param list vals_list: List of field-value dicts for new FSM orders.
        :return: Newly created FSM order recordset.
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
        order_ids = self.ids
        _logger.info("[UNLINK] Triggered for FSM order ids: %s", order_ids)

        all_maps = (
            self.env["caldav.event.map"]
            .sudo()
            .search(
                [
                    ("fsm_order_id", "in", order_ids),
                ]
            )
        )
        _logger.debug(
            "[UNLINK] Found %s mapping records for these FSM orders.", len(all_maps)
        )

        for map_rec in all_maps:
            try:
                _logger.info(
                    '[UNLINK] CalDAV DELETE: FSM order "%s" (id=%s) via account %s at %s',
                    map_rec.fsm_order_id.name,
                    map_rec.fsm_order_id.id,
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
