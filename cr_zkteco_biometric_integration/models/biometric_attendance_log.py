# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class BiometricAttendanceLog(models.Model):
    """
    Stores a single raw attendance punch record received from a ZKTeco device
    via the ADMS HTTP push protocol.

    Each record corresponds to one line in an ATTLOG payload. Duplicates are
    prevented at the database level via a unique constraint on `unique_key`
    which is built from the device serial number, device user ID, and UTC timestamp.
    """

    _name = "biometric.attendance.log"
    _description = "Biometric Attendance Log"
    _order = "timestamp desc"
    _rec_name = "device_user_id"

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    device_id = fields.Many2one(
        comodel_name="biometric.device",
        string="Device",
        required=True,
        ondelete="cascade",
        index=True,
        help="The biometric device that sent this punch record.",
    )
    device_user_id = fields.Char(
        string="Device User ID",
        required=True,
        index=True,
        help="User ID as stored on the biometric device (matches hr.employee.device_user_id).",
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
        compute="_compute_employee_id",
        store=True,
        index=True,
        help="Odoo employee matched to this punch via device_user_id.",
    )
    timestamp = fields.Datetime(
        string="Punch Time (UTC)",
        required=True,
        help="The punch timestamp converted to UTC from the device's local timezone.",
    )
    verify_state = fields.Selection(
        string="Verify State",
        selection=[
            ("0", "Check-in"),
            ("1", "Check-out"),
            ("4", "Check-in"),
            ("5", "Check-out"),
        ],
        help="Verification state (eg 0 - checkin, 1 - checkout, 4 - Overtime-In, 5 - Overtime-Out)",
    )
    status = fields.Selection(
        string="Status",
        selection=[
            ("new", "New"),
            ("processed", "Processed"),
            ("failed", "Failed"),
        ],
        default="new",
        index=True,
        help="Processing status of this attendance punch record.",
    )
    raw_data = fields.Text(
        string="Raw Data",
        help="The original tab-separated ATTLOG line as received from the device (for audit).",
    )
    unique_key = fields.Char(
        string="Unique Key",
        compute="_compute_unique_key",
        store=True,
        copy=False,
        index=True,
        help="Composite deduplication key: {serial_number}_{device_user_id}_{utc_timestamp}.",
    )
    image = fields.Binary(
        string="Punch Photo",
        help="Photo captured by the device at the moment of the attendance punch.",
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "unique_key_uniq",
            "UNIQUE(unique_key)",
            "A duplicate attendance punch record already exists for this device/user/timestamp.",
        ),
    ]

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends("device_user_id")
    def _compute_employee_id(self):
        """
        Link the log to an hr.employee by matching `device_user_id`
        against `hr.employee.device_user_id`.
        """
        for record in self:
            if record.device_user_id:
                employee = self.env["hr.employee"].search(
                    [("device_user_id", "=", record.device_user_id)], limit=1
                )
                record.employee_id = employee.id if employee else False
            else:
                record.employee_id = False

    @api.depends("device_id.serial_number", "device_user_id", "timestamp")
    def _compute_unique_key(self):
        """
        Compute a string unique key combining serial number, device user ID,
        and UTC timestamp to serve as a deduplication fingerprint.
        """
        for record in self:
            serial = (record.device_id.serial_number or "").strip()
            uid = (record.device_user_id or "").strip()
            ts = fields.Datetime.to_string(record.timestamp) if record.timestamp else ""
            record.unique_key = f"{serial}_{uid}_{ts}"

    def action_process_punch(self):
        """
        Manually trigger the processing logic for this specific log.
        Useful for testing policies or re-processing failed logs.
        """
        self.ensure_one()
        if not self.employee_id:
            return

        PUNCH_TYPE_MAP = {
            "0": "in",
            "4": "in",
            "1": "out",
            "5": "out",
        }

        device = self.device_id
        punch_type = PUNCH_TYPE_MAP.get(self.verify_state)

        # Override punch type based on device settings if needed
        if device.used_for == "in":
            punch_type = "in"
        elif device.used_for == "out":
            punch_type = "out"
        elif not punch_type:
            # Guessing logic
            open_att = (
                self.env["hr.attendance"]
                .sudo()
                .search(
                    [
                        ("employee_id", "=", self.employee_id.id),
                        ("check_out", "=", False),
                    ],
                    limit=1,
                )
            )
            punch_type = "out" if open_att else "in"

        success = self.employee_id._process_biometric_punch(
            device, self.timestamp, punch_type
        )
        if success:
            self.status = "processed"
        else:
            self.status = "failed"

    def action_process_logs(self):
        """
        Scheduled action to process 'new' logs.
        """
        # Find all devices that have real-time disabled or just process all 'new' logs
        # To be safe and respect the user's choice, we only process 'new' logs from
        # devices where real-time is disabled.
        batch_devices = self.env["biometric.device"].search([("active", "=", True)])

        # We filter logs that are 'new' and have an employee linked
        new_logs = self.search(
            [
                ("status", "=", "new"),
                ("device_id", "in", batch_devices.ids),
                ("employee_id", "!=", False),
            ],
            order="timestamp asc",
        )

        # Mapping verify_state to punch type
        PUNCH_TYPE_MAP = {
            "0": "in",
            "4": "in",
            "1": "out",
            "5": "out",
        }

        for log in new_logs:
            device = log.device_id
            punch_type = False

            if device.used_for == "in":
                punch_type = "in"
            elif device.used_for == "out":
                punch_type = "out"
            elif device.used_for == "both" and not device.status_code_based:
                # If not status code based, we guess: In if no open attendance, Out otherwise
                open_att = self.env["hr.attendance"].search(
                    [
                        ("employee_id", "=", log.employee_id.id),
                        ("check_out", "=", False),
                    ],
                    limit=1,
                )
                punch_type = "out" if open_att else "in"
            else:
                punch_type = PUNCH_TYPE_MAP.get(log.verify_state)
                if not punch_type:
                    # Logic to guess: In if no open attendance, Out otherwise
                    open_att = self.env["hr.attendance"].search(
                        [
                            ("employee_id", "=", log.employee_id.id),
                            ("check_out", "=", False),
                        ],
                        limit=1,
                    )
                    punch_type = "out" if open_att else "in"

            # Update log's verify_state to reflect what was actually considered
            # 0=In, 1=Out
            new_verify_state = "0" if punch_type == "in" else "1"
            if log.verify_state != new_verify_state:
                log.verify_state = new_verify_state

            success = log.employee_id._process_biometric_punch(
                log.device_id, log.timestamp, punch_type
            )
            if success:
                log.write({"status": "processed"})
            else:
                # It might fail if it's a duplicate or within interval
                # We mark as processed so we don't try again forever, but we can log it
                log.write({"status": "processed"})

        # After processing all logs, run auto-checkout
        self.env["hr.employee"]._run_biometric_auto_checkout()
