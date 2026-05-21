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

        # 1. Total Employees
        total_employees = self.env["hr.employee"].search_count(
            [("active", "=", True), ("company_id", "=", company.id)]
        )

        # 2. Present Today (Employees who have at least one biometric log today)
        present_employee_ids = self.env["biometric.attendance.log"].read_group(
            [("timestamp", ">=", today_start_utc), ("timestamp", "<=", today_end_utc)],
            ["employee_id"],
            ["employee_id"],
        )
        present_count = len(present_employee_ids)
        present_ids = [
            res["employee_id"][0] for res in present_employee_ids if res["employee_id"]
        ]

        # 3. Absent Today
        absent_count = total_employees - present_count

        # 4. Device Status
        devices = self.env["biometric.device"].search([])
        device_stats = []
        for dev in devices:
            is_online = False
            last_seen_str = _("Never seen")
            if dev.last_seen:
                # If seen in last 10 minutes, consider online
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
            # Convert timestamp back to user timezone for display
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

        # 6. Employee Lists
        presented_employees = []
        if present_ids:
            # Limit to 50 for performance
            emps = self.env["hr.employee"].search([("id", "in", present_ids)], limit=50)
            for e in emps:
                img = False
                if e.image_128:
                    try:
                        img = e.image_128.decode("utf-8")
                    except:
                        img = e.image_128  # already string?
                presented_employees.append(
                    {
                        "id": e.id,
                        "name": e.name,
                        "job": e.job_id.name or "",
                        "image": img,
                    }
                )

        absented_employees = []
        absent_emps = self.env["hr.employee"].search(
            [
                ("id", "not in", present_ids),
                ("active", "=", True),
                ("company_id", "=", company.id),
            ],
            limit=50,
        )
        for e in absent_emps:
            img = False
            if e.image_128:
                try:
                    img = e.image_128.decode("utf-8")
                except:
                    img = e.image_128
            absented_employees.append(
                {"id": e.id, "name": e.name, "job": e.job_id.name or "", "image": img}
            )

        # 7. Late/Early Counts
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
            "late_count": late_arrival_count,
            "early_count": early_leaving_count,
            "device_stats": device_stats,
            "recent_punches": recent_punches,
            "presented_employees": presented_employees,
            "absented_employees": absented_employees,
        }
