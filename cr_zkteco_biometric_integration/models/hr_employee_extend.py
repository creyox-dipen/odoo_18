# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, models, fields, _
import logging

logger = logging.getLogger(__name__)


class HrEmployeeExtend(models.Model):
    """
    Extends hr.employee to store the ZKTeco biometric device user ID.
    This field is used to match punch records received via ADMS to the
    correct Odoo employee.
    """

    _inherit = "hr.employee"

    device_user_id = fields.Char(
        string="Biometric User ID",
        index=True,
        copy=False,
        groups="hr.group_hr_user",
        help=(
            "The user ID enrolled on the ZKTeco biometric device. "
            "This is matched against incoming ADMS attendance punches "
            "to identify the employee."
        ),
    )

    biometric_template_ids = fields.One2many(
        comodel_name="biometric.user.template",
        inverse_name="employee_id",
        string="Biometric Templates",
        help="Fingerprint and Face templates stored for this employee.",
    )
    biometric_privilege = fields.Selection(
        [
            ("0", "Normal User"),
            ("14", "Super Admin"),
        ],
        string="Biometric Privilege",
        default="0",
        help="User privilege level on the biometric device.\n0=Normal User, 1/3=Enroller, 2=Manager, 14=Super Admin.",
    )

    _sql_constraints = [
        (
            "device_user_id_unique",
            "unique(device_user_id)",
            "The Biometric User ID must be unique per employee!",
        ),
    ]

    def _ensure_device_user_id(self):
        """
        Ensures that every employee in this recordset has a unique, numeric device_user_id.
        If an employee does not have one, it will auto-generate and write it.
        """
        all_pins = (
            self.env["hr.employee"]
            .sudo()
            .search([("device_user_id", "!=", False)])
            .mapped("device_user_id")
        )
        numeric_pins = []
        for pin in all_pins:
            try:
                numeric_pins.append(int(pin))
            except ValueError:
                continue

        max_pin = max(numeric_pins) if numeric_pins else 9999
        next_pin = max(max_pin + 1, 10000)

        for employee in self:
            if not employee.device_user_id:
                employee.sudo().write({"device_user_id": str(next_pin)})
                next_pin += 1

    def action_sync_to_devices(self, device_ids=None):
        self.ensure_one()
        if not self.device_user_id:
            return

        if device_ids:
            devices = self.env["biometric.device"].sudo().browse(device_ids)
        else:
            devices = (
                self.env["biometric.device"].sudo().search([("active", "=", True)])
            )

        for device in devices:
            self._generate_sync_commands(device)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Initiated"),
                "message": _(
                    'Employee "%s" data has been queued for syncing to %d device(s).'
                )
                % (self.name, len(devices)),
                "sticky": False,
                "type": "success",
            },
        }

    def _generate_sync_commands(self, device):
        """Creates the ADMS commands to push user info and templates to a specific device."""
        self.ensure_one()
        Command = self.env["biometric.device.command"].sudo()

        # 1. Push User Info — fields TAB separated
        priv = self.biometric_privilege
        priv_fields = ""
        if priv == "14":
            priv_fields = f"Pri=14\t"
        elif priv == "0":
            priv_fields = f"Pri=0\t"
        # If priv is empty or a custom code, we don't send any privilege fields.
        # This keeps the device's existing role untouched.

        logger.info(
            "➡️ Sending User Sync for PIN=%s Name=%s to Device SN=%s",
            self.device_user_id,
            self.name,
            device.serial_number,
        )

        Command.create(
            {
                "device_id": device.id,
                "command_text": (
                    f"DATA UPDATE UserInfo\t"
                    f"PIN={self.device_user_id}\t"
                    f"Name={self.name}\t"
                    f"{priv_fields}"
                    f"Passwd=\t"
                    f"Card=\t"
                    f"Grp=1\t"
                    f"TZ=0000000100000000\t"
                    f"Verify=0\t"
                    f"ViceCard="
                ),
            }
        )

        # 2. Push Fingerprints / Face Templates
        for template in self.biometric_template_ids:
            if template.type == "finger":
                # ✅ Fingerprint — table: FingerTmp
                cmd = (
                    f"DATA UPDATE FingerTmp\t"
                    f"PIN={self.device_user_id}\t"
                    f"FID={template.finger_index}\t"
                    f"Size={len(template.template_data)}\t"
                    f"Valid=1\t"
                    f"TMP={template.template_data}"
                )
            else:
                # ✅ Face — table: FaceTemp
                cmd = (
                    f"DATA UPDATE Face\t"
                    f"PIN={self.device_user_id}\t"
                    f"FID={template.finger_index}\t"
                    f"Size={len(template.template_data)}\t"
                    f"Valid=1\t"
                    f"TMP={template.template_data}"
                )

            Command.create(
                {
                    "device_id": device.id,
                    "command_text": cmd,
                }
            )

    def action_request_templates_from_device(self):
        """
        Sends specific query commands to fetch this employee's info and templates.
        """
        self.ensure_one()
        if not self.device_user_id:
            return

        devices = self.env["biometric.device"].sudo().search([("active", "=", True)])
        Command = self.env["biometric.device.command"].sudo()

        for device in devices:
            # 1. Fetch User Info (Name, Role)
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY UserInfo PIN={self.device_user_id}",
                }
            )
            # 2. Fetch Fingerprints
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY FingerTmp PIN={self.device_user_id}",
                }
            )
            # 3. Fetch Face Templates
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY Face PIN={self.device_user_id}",
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Request Sent"),
                "message": _('Commands sent to fetch templates for "%s".') % self.name,
                "sticky": False,
                "type": "info",
            },
        }

    def action_open_enroll_wizard(self):
        self.ensure_one()
        return {
            "name": "Remote Biometric Enrollment",
            "type": "ir.actions.act_window",
            "res_model": "biometric.enroll.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.id,
            },
        }

    def action_open_transfer_wizard(self):
        self.ensure_one()
        return {
            "name": "Transfer to Devices",
            "type": "ir.actions.act_window",
            "res_model": "biometric.user.transfer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.id,
            },
        }

    def action_delete_from_devices(self, device_ids=None):
        """Send a DELETE command to remove this user from the hardware."""
        self.ensure_one()
        if not self.device_user_id:
            return

        if device_ids:
            devices = self.env["biometric.device"].sudo().browse(device_ids)
        else:
            devices = (
                self.env["biometric.device"].sudo().search([("active", "=", True)])
            )

        Command = self.env["biometric.device.command"].sudo()
        for device in devices:
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA DELETE UserInfo PIN={self.device_user_id}",
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Deletion Queued"),
                "message": _("Delete command sent to %s device(s).") % len(devices),
                "type": "warning",
                "sticky": False,
            },
        }

    def _process_biometric_punch(self, device, utc_dt, punch_type):
        """
        Processes a single punch for this employee and updates hr.attendance.
        Returns True if successful, False otherwise.
        """
        self.ensure_one()
        Attendance = self.env["hr.attendance"].sudo()

        # --- SMART POLICY: Calendar-Based Rounding ---
        final_dt = utc_dt
        if device.attendance_policy == "calendar" and self.resource_calendar_id:
            final_dt = self._get_smart_punch_time(device, utc_dt, punch_type)

        # 1. Rule: Min. Punch Interval (use the original utc_dt for interval check)
        if device.min_punch_interval > 0:
            last_attendance = Attendance.search(
                [("employee_id", "=", self.id)], order="check_in desc", limit=1
            )

            last_time = False
            if last_attendance:
                last_time = last_attendance.check_out or last_attendance.check_in

            if last_time:
                import datetime

                diff = (utc_dt - last_time).total_seconds() / 60.0
                if abs(diff) < device.min_punch_interval:
                    return False

        # --- LATE/EARLY CALCULATION ---
        perf_stats = self._get_punch_performance_stats(device, utc_dt, punch_type)

        if punch_type == "in":
            # Check for existing open attendance
            open_attendance = Attendance.search(
                [
                    ("employee_id", "=", self.id),
                    ("check_out", "=", False),
                ],
                limit=1,
            )
            if not open_attendance:
                Attendance.create(
                    {
                        "employee_id": self.id,
                        "check_in": final_dt,
                        "is_late": perf_stats.get("is_late", False),
                        "late_minutes": perf_stats.get("late_minutes", 0.0),
                    }
                )
                return True
            return False

        elif punch_type == "out":
            open_attendance = Attendance.search(
                [
                    ("employee_id", "=", self.id),
                    ("check_out", "=", False),
                ],
                order="check_in desc",
                limit=1,
            )
            if open_attendance and final_dt > open_attendance.check_in:
                open_attendance.write(
                    {
                        "check_out": final_dt,
                        "is_early_leaving": perf_stats.get("is_early_leaving", False),
                        "early_leaving_minutes": perf_stats.get(
                            "early_leaving_minutes", 0.0
                        ),
                    }
                )
                return True
            return False

        return False

    def _get_punch_performance_stats(self, device, utc_dt, punch_type):
        """
        Calculates if a punch is late or early based on the employee's calendar.
        Improved to handle multiple shifts (Morning/Afternoon) and late-night punches.
        """
        import pytz
        from datetime import datetime, timedelta, time

        stats = {
            "is_late": False,
            "late_minutes": 0.0,
            "is_early_leaving": False,
            "early_leaving_minutes": 0.0,
        }

        calendar = self.resource_calendar_id
        if not calendar:
            return stats

        # 1. Convert UTC punch to Local timezone
        # Use employee's timezone if set, else company/device
        tz_name = self.tz or calendar.tz or device.timezone or "UTC"
        tz = pytz.timezone(tz_name)
        local_dt = pytz.utc.localize(utc_dt).astimezone(tz)
        local_date = local_dt.date()

        # 2. Get all shift intervals for the day
        day_start = tz.localize(datetime.combine(local_date, time.min))
        day_end = tz.localize(datetime.combine(local_date, time.max))
        if device.flexible_period:
            day_start = local_dt - timedelta(hours=14)
            day_end = local_dt + timedelta(hours=14)

        intervals = calendar._attendance_intervals_batch(
            day_start, day_end, self.resource_id
        )[self.resource_id.id]
        if not intervals:
            return stats

        # 3. Find the best matching shift
        if punch_type == "in":
            # For check-in, we compare against the START of the relevant shift.
            # Usually, the employee is checking in for the first shift they haven't worked yet.
            # If they punch at 17:11, we compare against the start of the last shift of the day.

            # Sort shifts by start time
            sorted_intervals = sorted(intervals, key=lambda x: x[0])

            # Find the shift that should have started before (or is closest to) the punch
            target_shift = sorted_intervals[0]  # Default to first
            for start, end, meta in sorted_intervals:
                shift_start_local = start.astimezone(tz)
                # If the punch is after this shift start, this is a potential target
                if local_dt >= shift_start_local:
                    target_shift = (start, end, meta)

            start, end, meta = target_shift
            shift_start_local = start.astimezone(tz)

            diff_late = (local_dt - shift_start_local).total_seconds() / 60.0
            if diff_late > device.grace_end_in:
                stats["is_late"] = True
                stats["late_minutes"] = diff_late

        elif punch_type == "out":
            # For check-out, we compare against the END of the relevant shift.
            # Usually the one that ended closest to the punch.

            # Sort shifts by end time descending (latest first)
            sorted_intervals = sorted(intervals, key=lambda x: x[1], reverse=True)

            # Find the shift that ended closest to the punch
            target_shift = sorted_intervals[0]
            for start, end, meta in sorted_intervals:
                shift_end_local = end.astimezone(tz)
                # If we punched before this shift ended, or it's the latest shift we completed
                if local_dt <= shift_end_local:
                    target_shift = (start, end, meta)

            start, end, meta = target_shift
            shift_end_local = end.astimezone(tz)

            diff_early = (shift_end_local - local_dt).total_seconds() / 60.0
            if diff_early > device.grace_start_out:
                stats["is_early_leaving"] = True
                stats["early_leaving_minutes"] = diff_early

        return stats

    def _get_smart_punch_time(self, device, utc_dt, punch_type):
        """
        Calculates the 'Smart' punch time by rounding the raw UTC time to the
        nearest shift boundary if within the device's grace period.
        """
        import pytz
        from datetime import datetime, timedelta, time

        calendar = self.resource_calendar_id
        if not calendar:
            return utc_dt

        # 1. Convert UTC punch to the Employee's Local timezone (from Calendar)
        # We prioritize the Calendar timezone, then Device, then User, then UTC
        tz_name = calendar.tz or device.timezone or self.env.user.tz or "UTC"
        tz = pytz.timezone(tz_name)
        local_dt = pytz.utc.localize(utc_dt).astimezone(tz)
        local_date = local_dt.date()

        # 2. Get shift intervals around the punch time
        if device.flexible_period:
            # Flexible: Search +/- 14 hours around the punch to catch overnight shifts
            day_start = local_dt - timedelta(hours=14)
            day_end = local_dt + timedelta(hours=14)
        else:
            # Standard: Only search the exact same day as the punch (High Performance)
            day_start = tz.localize(datetime.combine(local_date, time.min))
            day_end = tz.localize(datetime.combine(local_date, time.max))

        # Get intervals (this handles both standard and global calendars)
        intervals = calendar._attendance_intervals_batch(
            day_start, day_end, self.resource_id
        )[self.resource_id.id]

        if not intervals:
            return utc_dt

        # 3. Find the best shift boundary to round to
        # We perform the comparison in LOCAL time to avoid UTC offset confusion
        for start, end, meta in intervals:
            # start and end from Odoo are UTC-aware datetimes.
            # We convert them to the same local timezone as the punch.
            shift_start_local = start.astimezone(tz)
            shift_end_local = end.astimezone(tz)

            if punch_type == "in":
                # Check-In Grace
                diff_early = (
                    shift_start_local - local_dt
                ).total_seconds() / 60.0  # Positive if early
                diff_late = (
                    local_dt - shift_start_local
                ).total_seconds() / 60.0  # Positive if late

                if 0 <= diff_late <= device.grace_end_in:
                    # Rounding Goal: Shift Start (Only if LATE within grace)
                    rounded_utc = shift_start_local.astimezone(pytz.utc).replace(
                        tzinfo=None
                    )

                    # Check if the employee ALREADY has a record starting at this exact rounded time.
                    existing_count = (
                        self.env["hr.attendance"]
                        .sudo()
                        .search_count(
                            [
                                ("employee_id", "=", self.id),
                                ("check_in", "=", rounded_utc),
                            ]
                        )
                    )
                    if not existing_count:
                        return rounded_utc

            elif punch_type == "out":
                # Check-Out Grace
                diff_early = (
                    shift_end_local - local_dt
                ).total_seconds() / 60.0  # Positive if early

                if 0 <= diff_early <= device.grace_start_out:
                    # Rounding Goal: Shift End (Only if EARLY within grace)
                    rounded_utc = shift_end_local.astimezone(pytz.utc).replace(
                        tzinfo=None
                    )

                    # Check if the employee ALREADY has a record ending at this exact rounded time.
                    existing_count = (
                        self.env["hr.attendance"]
                        .sudo()
                        .search_count(
                            [
                                ("employee_id", "=", self.id),
                                ("check_out", "=", rounded_utc),
                            ]
                        )
                    )
                    if not existing_count:
                        return rounded_utc

        return utc_dt

    def _run_biometric_auto_checkout(self):
        """
        Finds open attendances for employees and closes them if auto-checkout is enabled on the device.
        Auto-checkout delay is configured in hours relative to the employee's working calendar shift end time.
        """
        from datetime import datetime, timedelta, time
        import pytz

        devices = (
            self.env["biometric.device"].sudo().search([("auto_checkout", "=", True)])
        )
        if not devices:
            return

        # Find all open attendances
        open_attendances = (
            self.env["hr.attendance"].sudo().search([("check_out", "=", False)])
        )
        if not open_attendances:
            return

        for att in open_attendances:
            employee = att.employee_id
            calendar = employee.resource_calendar_id
            if not calendar:
                continue

            # In multi-device setups, we can use the device settings of the first active device with auto_checkout.
            device = devices[0]

            tz_name = calendar.tz or device.timezone or self.env.user.tz or "UTC"
            tz = pytz.timezone(tz_name)

            # Convert check_in UTC time to timezone-aware local time
            check_in_local = pytz.utc.localize(att.check_in).astimezone(tz)

            # Get shift intervals for that day (search up to 30 hours to catch night shifts starting on that date)
            day_start = tz.localize(datetime.combine(check_in_local.date(), time.min))
            day_end = day_start + timedelta(hours=30)

            intervals = calendar._attendance_intervals_batch(
                day_start, day_end, employee.resource_id
            )[employee.resource_id.id]

            if not intervals:
                continue

            # Find the shift that should have ended after the employee checked in
            matching_shift = False
            for start, end, meta in sorted(intervals, key=lambda x: x[0]):
                start_local = start.astimezone(tz)
                end_local = end.astimezone(tz)
                if end_local > check_in_local:
                    matching_shift = (start_local, end_local)

            if not matching_shift:
                continue

            shift_start, shift_end = matching_shift

            # Threshold time: shift_end + delay hours
            threshold_dt = shift_end + timedelta(hours=device.auto_checkout_time)

            # Current local time
            now_local = datetime.now(tz)

            if now_local > threshold_dt:
                checkout_utc = shift_end.astimezone(pytz.utc).replace(tzinfo=None)
                logger.info(
                    "Auto-Checkout: Closing attendance for %s. Shift ended at %s, auto-checkout triggered at %s.",
                    employee.name,
                    shift_end,
                    threshold_dt,
                )
                # Ensure the check_out is later than check_in (sanity check)
                if checkout_utc > att.check_in:
                    att.write({"check_out": checkout_utc})

    def get_attendance_statuses_for_date_batch(self, check_date, user_tz):
        """
        Batch check attendance, leaves, and public holiday status for a recordset of employees on a single date.
        Returns a dict mapping: employee_id -> (status_string, detail_reason)
        Status string can be: 'present', 'leave', 'holiday', 'weekend', 'absent'
        """
        import pytz
        from datetime import datetime, time

        res = {}
        if not self:
            return res

        # 1. Start and End of the check_date in UTC
        start_utc = user_tz.localize(datetime.combine(check_date, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = user_tz.localize(datetime.combine(check_date, time.max)).astimezone(pytz.utc).replace(tzinfo=None)

        attendances = self.env["hr.attendance"].sudo().search([
            ("employee_id", "in", self.ids),
            ("check_in", "<=", end_utc),
            "|",
            ("check_out", ">=", start_utc),
            ("check_out", "=", False),
        ])
        present_ids = set(attendances.mapped("employee_id.id"))

        # 2. Fetch approved leaves today
        approved_leaves = set()
        leave_reasons = {}
        if self.env.registry.get("hr.leave"):
            leaves = self.env["hr.leave"].sudo().search([
                ("employee_id", "in", self.ids),
                ("state", "=", "validate"),
                ("date_from", "<=", end_utc),
                ("date_to", ">=", start_utc),
            ])
            for leave in leaves:
                eid = leave.employee_id.id
                approved_leaves.add(eid)
                leave_reasons[eid] = leave.holiday_status_id.name or _("Approved Leave")

        # 3. Fetch public holidays and scheduled work today per calendar
        calendar_working = {}
        public_holidays = {}
        unique_calendars = self.mapped("resource_calendar_id")

        for cal in unique_calendars:
            if not cal:
                continue
            # Check for public holiday
            holiday_leaves = self.env["resource.calendar.leaves"].sudo().search([
                ("calendar_id", "=", cal.id),
                ("resource_id", "=", False),
                ("date_from", "<=", datetime.combine(check_date, time.max)),
                ("date_to", ">=", datetime.combine(check_date, time.min)),
            ], limit=1)
            if holiday_leaves:
                public_holidays[cal.id] = holiday_leaves[0].name or _("Public Holiday")

            # Check working day status
            day_start = user_tz.localize(datetime.combine(check_date, time.min))
            day_end = user_tz.localize(datetime.combine(check_date, time.max))
            intervals = cal._attendance_intervals_batch(day_start, day_end)
            # cal._attendance_intervals_batch returns a dict mapping resource_id -> list of tuples
            calendar_working[cal.id] = bool(intervals.get(False) or intervals.get(None))

        # 4. Map statuses
        for emp in self:
            if emp.id in present_ids:
                res[emp.id] = ("present", False)
            elif emp.id in approved_leaves:
                res[emp.id] = ("leave", leave_reasons.get(emp.id))
            elif emp.resource_calendar_id and emp.resource_calendar_id.id in public_holidays:
                res[emp.id] = ("holiday", public_holidays.get(emp.resource_calendar_id.id))
            elif emp.resource_calendar_id and emp.resource_calendar_id.id in calendar_working and not calendar_working.get(emp.resource_calendar_id.id):
                res[emp.id] = ("weekend", False)
            else:
                res[emp.id] = ("absent", False)

        return res

