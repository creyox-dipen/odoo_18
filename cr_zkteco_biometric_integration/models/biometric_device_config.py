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
    connect_via_ip = fields.Boolean(
        string="Connect via IP",
        default=False,
        tracking=True,
        help="If enabled, the device configuration will use IP Address and Port to establish direct connections.",
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

    last_download_from = fields.Datetime(
        string="Last Download From",
        help="Internal helper to filter incoming logs on the server side (Start Time).",
    )
    last_download_to = fields.Datetime(
        string="Last Download To",
        help="Internal helper to filter incoming logs on the server side (End Time).",
    )
    min_punch_interval = fields.Integer(
        string="Min. Punch Interval (Mins)",
        default=5,
        help="Ignore punches from the same employee that occur within this many minutes of each other.",
    )
    auto_checkout = fields.Boolean(
        string="Auto Check-out",
        default=False,
        help="If enabled, the system will automatically close open attendances based on the shift end time.",
    )
    auto_checkout_time = fields.Float(
        string="Auto Check-out Delay (Hours)",
        default=2.0,
        help="The delay in hours after the scheduled shift end time to automatically close open attendances (e.g. 2.0 = 2 hours).",
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

    enable_absent_alert = fields.Boolean(
        string="Enable Absent Email Alerts",
        default=False,
        help="If enabled, Odoo will automatically send an email to the admin listing employees who haven't clocked in within the threshold time.",
    )
    absent_alert_delay = fields.Integer(
        string="Alert Delay (Minutes)",
        default=30,
        help="Time in minutes after shift start to send the alert email.",
    )
    absent_alert_email = fields.Char(
        string="Admin Alert Email",
        help="The email address of the administrator who should receive the absent report.",
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
        """Opens a wizard to choose dates for downloading attendance logs."""
        self.ensure_one()
        return {
            "name": _("Download Attendance Logs"),
            "type": "ir.actions.act_window",
            "res_model": "biometric.download.log.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_device_id": self.id,
            },
        }

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

        managers = group.users if hasattr(group, "users") else group.user_ids
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

    @api.model
    def _cron_send_absent_late_alerts(self):
        """Automated daily absent email alerts check triggered by cron."""
        _logger.info("ADMS Absent Alert Cron: Starting automated absent email alerts check.")
        devices = self.search([("active", "=", True), ("enable_absent_alert", "=", True)])
        if not devices:
            _logger.info("ADMS Absent Alert Cron: Skipped — No active devices with enable_absent_alert=True found.")
            return True

        from datetime import datetime, time, timedelta
        import pytz

        # Get all active employees with biometric IDs
        employees = self.env["hr.employee"].search([
            ("active", "=", True),
            ("device_user_id", "!=", False)
        ])
        if not employees:
            _logger.info("ADMS Absent Alert Cron: Skipped — No active employees with device_user_id configured.")
            return True

        now_utc = datetime.now(pytz.utc)

        for device in devices:
            if not device.absent_alert_email:
                _logger.info("ADMS Absent Alert Cron: Device %s (SN=%s) skipped — Admin Alert Email is empty.", device.name, device.serial_number)
                continue

            alert_delay = device.absent_alert_delay or 30
            tz_name = device.timezone or "UTC"
            tz = pytz.timezone(tz_name)
            today_local = now_utc.astimezone(tz).date()

            _logger.info("ADMS Absent Alert Cron: Processing device %s (SN=%s) for date %s", device.name, device.serial_number, today_local)

            # 1. Fetch already alerted employees today
            already_alerted_ids = set(
                self.env["biometric.attendance.alert.log"]
                .search([("alert_date", "=", today_local)])
                .mapped("employee_id.id")
            )

            # 2. Batch check statuses for all employees
            status_map = employees.get_attendance_statuses_for_date_batch(today_local, tz)

            # 3. Group employees by calendar to batch-fetch intervals
            calendar_groups = {}
            for employee in employees:
                if employee.id in already_alerted_ids:
                    _logger.info("ADMS Absent Alert Cron: Employee %s skipped — already alerted today (%s).", employee.name, today_local)
                    continue
                # Exclude employees already present, on leave, holiday, or weekend
                status, reason = status_map.get(employee.id, ("absent", False))
                if status in ("present", "leave", "holiday", "weekend"):
                    _logger.info("ADMS Absent Alert Cron: Employee %s skipped — status is '%s' (details: %s).", employee.name, status, reason or "N/A")
                    continue
                if not employee.resource_calendar_id:
                    _logger.info("ADMS Absent Alert Cron: Employee %s skipped — no working calendar (resource_calendar_id) assigned.", employee.name)
                    continue
                calendar_groups.setdefault(employee.resource_calendar_id, []).append(employee)

            if not calendar_groups:
                _logger.info("ADMS Absent Alert Cron: Device %s (SN=%s) — no employees eligible for shift check.", device.name, device.serial_number)
                continue

            day_start = tz.localize(datetime.combine(today_local, time.min))
            day_end = tz.localize(datetime.combine(today_local, time.max))

            late_absent_list = []

            # 4. Batch-fetch intervals per calendar
            for calendar, group_employees in calendar_groups.items():
                cal_tz_name = calendar.tz or device.timezone or "UTC"
                cal_tz = pytz.timezone(cal_tz_name)

                resources = self.env["resource.resource"].browse(
                    [emp.resource_id.id for emp in group_employees if emp.resource_id]
                )
                if not resources:
                    for emp in group_employees:
                        _logger.info("ADMS Absent Alert Cron: Employee %s skipped — missing resource.resource record.", emp.name)
                    continue

                intervals_dict = calendar._attendance_intervals_batch(day_start, day_end, resources)

                for employee in group_employees:
                    emp_intervals = intervals_dict.get(employee.resource_id.id, [])
                    if not emp_intervals:
                        _logger.info("ADMS Absent Alert Cron: Employee %s skipped — no scheduled shift intervals today on calendar '%s'.", employee.name, calendar.name)
                        continue

                    # Get earliest shift start today
                    shift_start = min(start for start, end, att in emp_intervals)
                    alert_time = shift_start + timedelta(minutes=alert_delay)

                    if now_utc > alert_time:
                        shift_start_str = shift_start.astimezone(cal_tz).strftime("%I:%M %p")
                        _logger.info("ADMS Absent Alert Cron: Employee %s IS ABSENT & THRESHOLD PASSED (shift start: %s, alert delay: %s mins, alert time: %s). Added to alert list.", employee.name, shift_start_str, alert_delay, alert_time)
                        late_absent_list.append({
                            "employee": employee,
                            "shift_start": shift_start_str,
                        })
                    else:
                        _logger.info("ADMS Absent Alert Cron: Employee %s skipped — shift delay threshold not reached yet (alert time: %s, current UTC: %s).", employee.name, alert_time, now_utc)

            if late_absent_list:
                _logger.info(
                    "ADMS Absent Alert Cron: Sending alert email for %s absent employee(s) to %s",
                    len(late_absent_list),
                    device.absent_alert_email
                )
                device._send_absent_alert_email(late_absent_list, today_local)

                # Log alert sent
                alert_logs = []
                for item in late_absent_list:
                    alert_logs.append({
                        "employee_id": item["employee"].id,
                        "alert_date": today_local,
                    })
                self.env["biometric.attendance.alert.log"].create(alert_logs)
            else:
                _logger.info("ADMS Absent Alert Cron: Device %s (SN=%s) — no absent employees passed the threshold delay. Email skipped.", device.name, device.serial_number)

        return True

    def _send_absent_alert_email(self, alert_data, alert_date):
        """Send a clean HTML formatted email to the configured administrator."""
        self.ensure_one()
        if not self.absent_alert_email:
            return

        body_html = f"""
        <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 20px; color: #333333; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #6a4a6e; border-bottom: 2px solid #6a4a6e; padding-bottom: 10px; margin-top: 0;">Biometric Attendance Alert</h2>
            <p>The following employees have not clocked in for their shifts today (<b>{alert_date}</b>) and have exceeded the check-in threshold delay of <b>{self.absent_alert_delay}</b> minutes:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #6a4a6e; color: #ffffff;">
                        <th style="padding: 10px; text-align: left; border: 1px solid #e2e8f0;">Employee Name</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid #e2e8f0;">Department</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid #e2e8f0;">Scheduled Shift Start</th>
                    </tr>
                </thead>
                <tbody>
        """
        for item in alert_data:
            emp = item["employee"]
            dept = emp.department_id.name or "-"
            body_html += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e2e8f0;"><b>{emp.name}</b></td>
                        <td style="padding: 10px; border: 1px solid #e2e8f0; color: #666666;">{dept}</td>
                        <td style="padding: 10px; border: 1px solid #e2e8f0; color: #dc3545; font-weight: bold;">{item["shift_start"]}</td>
                    </tr>
            """

        body_html += """
                </tbody>
            </table>
            
            <p style="font-size: 12px; color: #718096; border-top: 1px solid #e2e8f0; padding-top: 15px; margin-bottom: 0;">
                This is an automated alert generated by the Smart ZKTeco Biometric Integration module.
            </p>
        </div>
        """

        mail_values = {
            "subject": f"Biometric Attendance Alert - {alert_date}",
            "body_html": body_html,
            "email_to": self.absent_alert_email,
            "email_from": self.env.company.email or "biometric-alerts@creyox.com",
        }

        try:
            mail = self.env["mail.mail"].sudo().create(mail_values)
            mail.send()
            _logger.info("ADMS: Sent absent alert email to %s", self.absent_alert_email)
        except Exception as e:
            _logger.info("ADMS: Failed to send alert email: %s", str(e))
