# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class BiometricDownloadLogWizard(models.TransientModel):
    """
    Wizard to select a date range for downloading biometric attendance logs.
    If the date range is left blank, all logs are downloaded.
    """

    _name = "biometric.download.log.wizard"
    _description = "Download Biometric Logs Wizard"

    device_id = fields.Many2one(
        comodel_name="biometric.device",
        string="Device",
        required=True,
    )
    download_from = fields.Datetime(
        string="Download From",
        help="The starting date and time for attendance log synchronization.",
    )
    download_to = fields.Datetime(
        string="Download To",
        help="The ending date and time for attendance log synchronization.",
    )

    def action_download_logs(self):
        """Builds and queues the DATA QUERY ATTLOG command on the device."""
        self.ensure_one()
        device = self.device_id

        _logger.info(
            "Wizard action triggered: Requesting logs from device SN=%s (From: %s, To: %s)",
            device.serial_number,
            self.download_from,
            self.download_to,
        )

        # Store requested dates temporarily on the device record to enable server-side filtering
        device.sudo().write({
            "last_download_from": self.download_from,
            "last_download_to": self.download_to,
        })

        command_text = "DATA QUERY ATTLOG"
        conditions = []

        if self.download_from:
            dt_from = self.download_from
            if device.timezone:
                import pytz
                utc_tz = pytz.utc
                device_tz = pytz.timezone(device.timezone)
                dt_from = utc_tz.localize(dt_from).astimezone(device_tz)
            conditions.append("StartTime=%s" % dt_from.strftime("%Y-%m-%d %H:%M:%S"))

        if self.download_to:
            dt_to = self.download_to
            if device.timezone:
                import pytz
                utc_tz = pytz.utc
                device_tz = pytz.timezone(device.timezone)
                dt_to = utc_tz.localize(dt_to).astimezone(device_tz)
            conditions.append("EndTime=%s" % dt_to.strftime("%Y-%m-%d %H:%M:%S"))

        if conditions:
            command_text += " " + " ".join(conditions)
        else:
            command_text += " OpStamp=0"

        self.env["biometric.device.command"].sudo().create(
            {
                "device_id": device.id,
                "command_text": command_text,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Logs Requested"),
                "message": _("Command sent to device. Logs will sync on the next heartbeat."),
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.act_window_close"
                },
            },
        }
