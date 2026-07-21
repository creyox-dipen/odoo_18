# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, api, fields, _
from datetime import datetime, date, timedelta
import pytz


class BiometricDashboard(models.AbstractModel):
    _name = "biometric.dashboard"
    _description = "Biometric Dashboard Logic"

    @api.model
    def get_dashboard_data(self):
        uid = self.env.context.get("uid", self.env.user.id)
        user = self.env["res.users"].browse(uid)
        company = user.company_id

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Convert to UTC for database queries
        tz = pytz.timezone(user.tz or "UTC")
        today_start_utc = (
            tz.localize(today_start).astimezone(pytz.utc).replace(tzinfo=None)
        )
        today_end_utc = tz.localize(today_end).astimezone(pytz.utc).replace(tzinfo=None)

        # 1. Total Active Employees
        all_employees = self.env["hr.employee"].search(
            [("active", "=", True), ("company_id", "=", company.id)]
        )
        total_employees = len(all_employees)

        # 2. Batch check employee statuses (Present, Leave, Holiday, Weekend, Absent)
        status_map = all_employees.get_attendance_statuses_for_date_batch(today, tz)

        present_emps = []
        leave_emps = []
        absent_emps = []

        for emp in all_employees:
            status, reason = status_map.get(emp.id, ("absent", False))
            if status == "present":
                present_emps.append(emp)
            elif status in ("leave", "holiday"):
                leave_emps.append((emp, reason))
            elif status == "absent":
                absent_emps.append(emp)

        present_count = len(present_emps)
        leave_count = len(leave_emps)
        absent_count = len(absent_emps)

        # 3. Format Employee Lists for UI
        presented_employees = []
        for e in present_emps[:50]:
            img = False
            if e.image_128:
                try:
                    img = e.image_128.decode("utf-8")
                except:
                    img = e.image_128
            presented_employees.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "job": e.job_id.name or "",
                    "image": img,
                }
            )

        leaved_employees = []
        for item in leave_emps[:50]:
            e, reason = item
            img = False
            if e.image_128:
                try:
                    img = e.image_128.decode("utf-8")
                except:
                    img = e.image_128
            leaved_employees.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "job": e.job_id.name or "",
                    "reason": reason or _("On Leave"),
                    "image": img,
                }
            )

        absented_employees = []
        for e in absent_emps[:50]:
            img = False
            if e.image_128:
                try:
                    img = e.image_128.decode("utf-8")
                except:
                    img = e.image_128
            absented_employees.append(
                {"id": e.id, "name": e.name, "job": e.job_id.name or "", "image": img}
            )

        # 4. Device Status
        devices = self.env["biometric.device"].search([])
        device_stats = []
        for dev in devices:
            is_online = False
            last_seen_str = _("Never seen")
            if dev.last_seen:
                if (datetime.now() - dev.last_seen) < timedelta(minutes=10):
                    is_online = True
                last_seen_str = dev.last_seen.strftime("%Y-%m-%d %H:%M:%S")

            device_stats.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "sn": dev.serial_number,
                    "status": "online" if is_online else "offline",
                    "last_seen": last_seen_str,
                }
            )

        # 5. Recent Punches (Last 10)
        recent_punches = []
        logs = self.env["biometric.attendance.log"].search(
            [], order="timestamp desc", limit=10
        )
        for log in logs:
            ts_utc = pytz.utc.localize(log.timestamp)
            ts_user = ts_utc.astimezone(tz)

            recent_punches.append(
                {
                    "employee": log.employee_id.name,
                    "device": log.device_id.name,
                    "time": ts_user.strftime("%I:%M:%S %p"),
                    "type": (
                        "Check In" if log.verify_state in ["0", "4"] else "Check Out"
                    ),
                }
            )

        # 6. Late/Early Counts
        late_arrival_count = self.env["hr.attendance"].search_count(
            [
                ("check_in", ">=", today_start_utc),
                ("check_in", "<=", today_end_utc),
                ("is_late", "=", True),
            ]
        )
        early_leaving_count = self.env["hr.attendance"].search_count(
            [
                ("check_out", ">=", today_start_utc),
                ("check_out", "<=", today_end_utc),
                ("is_early_leaving", "=", True),
            ]
        )

        return {
            "total_employees": total_employees,
            "present_count": present_count,
            "absent_count": absent_count,
            "leave_count": leave_count,
            "late_count": late_arrival_count,
            "early_count": early_leaving_count,
            "device_stats": device_stats,
            "recent_punches": recent_punches,
            "presented_employees": presented_employees,
            "leaved_employees": leaved_employees,
            "absented_employees": absented_employees,
        }
