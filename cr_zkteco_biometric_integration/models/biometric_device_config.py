# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BiometricDevice(models.Model):
    """
    Represents a registered ZKTeco biometric device that pushes attendance
    data to Odoo via the ADMS HTTP protocol.

    The device is identified by its unique serial number. When the device
    sends a push, Odoo looks up the record by serial number, validates the
    optional communication key, and processes the attendance payload.
    """

    _name = "biometric.device"
    _description = "Biometric Device (ADMS)"
    _rec_name = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    name = fields.Char(
        string="Device Name",
        required=True,
        tracking=True,
        help="A descriptive label for this biometric device (e.g. 'Main Entrance').",
    )
    serial_number = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        tracking=True,
        help=(
            "Unique hardware serial number of the ZKTeco device. "
            "Must match the SN= parameter sent by the device in every ADMS push."
        ),
    )
    device_ip = fields.Char(
        string="Device IP Address",
        copy=False,
        help=(
            "IP address of the ZKTeco device on the local network. "
            "Used to fetch user names via pyzk when auto-creating employees."
        ),
    )
    device_port = fields.Integer(
        string="Device Port",
        default=4370,
        help=(
            "TCP port of the ZKTeco device SDK service (default: 4370). "
            "Used together with Device IP to connect via pyzk."
        ),
    )
    password = fields.Boolean(
        string="Use Communication Key",
        default=False,
        help="If enabled, the device must provide a valid communication key to push data.",
    )
    communication_key = fields.Char(
        string="Communication Key",
        copy=False,
        help=(
            "Optional security key configured on the device. "
            "If set, every ADMS request must include a matching Key= parameter."
        ),
    )
    timezone = fields.Selection(
        string="Device Timezone",
        selection=[
            ("UTC", "UTC"),
            ("Asia/Kolkata", "Asia/Kolkata (IST +05:30)"),
            ("Asia/Dubai", "Asia/Dubai (GST +04:00)"),
            ("Asia/Karachi", "Asia/Karachi (PKT +05:00)"),
            ("Asia/Dhaka", "Asia/Dhaka (BST +06:00)"),
            ("Asia/Singapore", "Asia/Singapore (SGT +08:00)"),
            ("Asia/Shanghai", "Asia/Shanghai (CST +08:00)"),
            ("Asia/Riyadh", "Asia/Riyadh (AST +03:00)"),
            ("Africa/Cairo", "Africa/Cairo (EET +02:00)"),
            ("America/New_York", "America/New_York (EST -05:00)"),
            ("America/Los_Angeles", "America/Los_Angeles (PST -08:00)"),
            ("Europe/London", "Europe/London (GMT +00:00)"),
            ("Europe/Paris", "Europe/Paris (CET +01:00)"),
            ("Australia/Sydney", "Australia/Sydney (AEDT +11:00)"),
        ],
        default="Asia/Shanghai",
        required=True,
        help=(
            "Local timezone of the device. Timestamps in ADMS pushes are in device "
            "local time and will be converted to UTC before storing in Odoo."
        ),
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive devices are ignored by the ADMS endpoint.",
    )
    last_seen = fields.Datetime(
        string="Last Seen",
        readonly=True,
        copy=False,
        tracking=True,
        help="Timestamp of the last successful ADMS push received from this device.",
    )
    connection_status = fields.Selection(
        [
            ("not_connected", "Not Connected"),
            ("connected", "Connected"),
        ],
        string="Connection Status",
        compute="_compute_connection_status",
        store=False,
    )

    state = fields.Selection(
        [
            ("draft", "Pending Approval"),
            ("confirmed", "Approved"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    def action_approve(self):
        """Approves a discovered device."""
        self.write({"state": "confirmed"})
        return True

    def _compute_connection_status(self):
        """
        Calculates status based on the last_seen timestamp.
        If the device has pushed data in the last 2 minutes, it is 'Connected'.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        for record in self:
            if record.last_seen and (now - record.last_seen) < timedelta(minutes=2):
                record.connection_status = "connected"
            else:
                record.connection_status = "not_connected"

    attendance_log_ids = fields.One2many(
        comodel_name="biometric.attendance.log",
        inverse_name="device_id",
        string="Attendance Logs",
        help="Raw attendance punch logs received from this device.",
    )
    attendance_log_count = fields.Integer(
        string="Log Count",
        compute="_compute_attendance_log_count",
        help="Total number of attendance punch logs received from this device.",
    )
    command_ids = fields.One2many(
        comodel_name="biometric.device.command",
        inverse_name="device_id",
        string="Commands",
        help="Remote commands sent to this device via ADMS.",
    )

    # -------------------------------------------------------------------------
    # Calculation & Processing Rules
    # -------------------------------------------------------------------------

    min_punch_interval = fields.Integer(
        string="Min. Punch Interval (Mins)",
        default=5,
        help="Ignore punches from the same employee that occur within this many minutes of each other.",
    )
    auto_checkout = fields.Boolean(
        string="Auto Check-out",
        default=False,
        help="If enabled, the system will automatically close open attendances at a specific time.",
    )
    auto_checkout_time = fields.Float(
        string="Auto Check-out Time",
        default=20.0,
        help="The time of day (0-24) to automatically close open attendances (e.g. 20.0 = 8:00 PM).",
    )
    auto_clear_log = fields.Boolean(
        string="Auto-Clear Device Logs",
        default=False,
        help="If enabled, Odoo will automatically send a command to clear the device's attendance logs after a successful sync.",
    )
    heartbeat_delay = fields.Integer(
        string="Heartbeat Interval (Seconds)",
        default=30,
        help="How often the device checks Odoo for new commands. Higher values save server resources but make commands slower to reach the device. "
        "IMPORTANT: After changing this value, you MUST click the 'Push Heartbeat Interval' button to send the update to the device.",
    )
    used_for = fields.Selection(
        [
            ("in", "Check-in Only"),
            ("out", "Check-out Only"),
            ("both", "Both (Check-in and Check-out)"),
        ],
        string="Used For",
        default="both",
        required=True,
        help="Define if this device is used only for check-ins, only for check-outs, or both.",
    )
    status_code_based = fields.Boolean(
        string="Status Code Based",
        default=True,
        help="If enabled, the system uses the device's status code (In/Out) to determine punch type. "
        "If disabled (only for 'Both'), the first punch of the day is In and the second is Out.",
    )

    # Smart Policies
    attendance_policy = fields.Selection(
        [
            ("raw", "Raw (Exact Time)"),
            ("calendar", "Calendar-Based (Smart Rounding)"),
        ],
        string="Attendance Policy",
        default="raw",
        required=True,
        help="Raw: Records the exact time from the machine.\n"
        "Calendar-Based: Rounds the punch time to the employee's shift start/end if within the grace period.",
    )

    flexible_period = fields.Boolean(
        string="Flexible Period (Overnight)",
        default=False,
        help="If enabled, the system will search for shifts across the midnight boundary (+/- 14 hours). "
        "This is recommended for night shifts but can be disabled to improve performance.",
    )

    grace_end_in = fields.Integer(
        string="Grace End-In (Mins)",
        default=15,
        help="Round down to shift start if check-in is X mins late.",
    )
    grace_start_out = fields.Integer(
        string="Grace Start-Out (Mins)",
        default=15,
        help="Round up to shift end if check-out is X mins early.",
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "serial_number_uniq",
            "UNIQUE(serial_number)",
            "A device with this serial number already exists. Serial numbers must be unique.",
        ),
    ]

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends("attendance_log_ids")
    def _compute_attendance_log_count(self):
        """Compute the total count of attendance logs linked to each device."""
        for record in self:
            record.attendance_log_count = len(record.attendance_log_ids)

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------

    def action_reboot(self):
        """Send a REBOOT command to the device."""
        self.ensure_one()
        self.env["biometric.device.command"].create(
            {
                "device_id": self.id,
                "command_text": "REBOOT",
            }
        )
        return True

    def action_clear_log(self):
        """Send a CLEAR LOG command to the device."""
        self.ensure_one()
        self.env["biometric.device.command"].create(
            {
                "device_id": self.id,
                "command_text": "CLEAR LOG",
            }
        )
        return True

    def action_sync_all_biometrics(self):
        """
        Requests all Users, Fingerprints, and Faces from the device.
        This is a bulk operation.
        """
        self.ensure_one()
        Command = self.env["biometric.device.command"].sudo()
        # 1. Fetch all User Info
        Command.create(
            {"device_id": self.id, "command_text": "DATA QUERY UserInfo OpStamp=0"}
        )
        # 2. Fetch all Fingerprints
        Command.create(
            {"device_id": self.id, "command_text": "DATA QUERY FingerTmp OpStamp=0"}
        )
        # 3. Fetch all Face Templates
        Command.create(
            {"device_id": self.id, "command_text": "DATA QUERY Face OpStamp=0"}
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Started"),
                "message": _(
                    "Commands sent to device. Data will arrive in a few moments."
                ),
                "sticky": False,
                "type": "success",
            },
        }

    def action_request_attlog(self):
        """
        Forces the device to push all attendance logs.
        """
        self.ensure_one()
        self.env["biometric.device.command"].create(
            {
                "device_id": self.id,
                "command_text": "DATA QUERY ATTLOG OpStamp=0",
            }
        )
        return True

    def action_export_all_users(self):
        """
        Push all active employees to this device, auto-generating unique biometric IDs if missing.
        """
        self.ensure_one()
        employees = self.env["hr.employee"].sudo().search([])
        employees._ensure_device_user_id()

        for emp in employees:
            emp._generate_sync_commands(self)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Export Started"),
                "message": _('Queued %d users for export to "%s".')
                % (len(employees), self.name),
                "sticky": False,
                "type": "success",
            },
        }

    def action_view_logs(self):
        """
        Open the attendance logs list view filtered to this device.

        Returns:
            dict: Window action to open biometric.attendance.log filtered by device.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attendance Logs — %s") % self.name,
            "res_model": "biometric.attendance.log",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }

    def action_view_cleanup_cron(self):
        """
        Redirects to the Scheduled Action (Cron) for command cleanup.
        """
        cron = self.env.ref(
            "cr_zkteco_biometric_integration.ir_cron_gc_biometric_commands",
            raise_if_not_found=False,
        )
        if not cron:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": _("Command Cleanup Task"),
            "res_model": "ir.cron",
            "view_mode": "form",
            "res_id": cron.id,
            "target": "current",
        }

    def action_push_heartbeat_delay(self):
        """
        Creates a SET OPTION command to manually override the heartbeat delay
        on the device firmware.
        """
        self.ensure_one()
        self.env["biometric.device.command"].sudo().create(
            {
                "device_id": self.id,
                "command_text": f"SET OPTION Delay={self.heartbeat_delay}",
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _(
                    "Command queued: SET OPTION Delay=%d. It will be applied on the next heartbeat."
                )
                % self.heartbeat_delay,
                "type": "success",
                "sticky": False,
            },
        }

    def _notify_admin(self, notification_type="discovered"):
        """
        Creates an activity for all Attendance Managers when a device
        event occurs (discovered or came back online).
        """
        self.ensure_one()
        group = self.env.ref(
            "hr_attendance.group_hr_attendance_manager", raise_if_not_found=False
        )
        if not group:
            return

        managers = group.users
        subject = _("Biometric Device Alert: %s") % self.name
        if notification_type == "discovered":
            note = (
                _(
                    "A new biometric device with SN: <b>%s</b> has been discovered and automatically registered."
                )
                % self.serial_number
            )
        else:
            note = _("Device <b>%s</b> (SN: %s) has just come back ONLINE.") % (
                self.name,
                self.serial_number,
            )

        for manager in managers:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=manager.id,
                summary=subject,
                note=note,
            )

        # Only post to chatter for 'online' status (Discovery already has a default Odoo log)
        if notification_type == "online":
            self.message_post(body=note, subtype_xmlid="mail.mt_note")
