# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
from datetime import datetime, time
import pytz


class BiometricDailySummaryReportWizard(models.TransientModel):
    _name = "biometric.daily.summary.report.wizard"
    _description = "Daily Summary Report Wizard (PDF)"

    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    def action_print_pdf(self):
        return self.env.ref(
            "cr_zkteco_biometric_integration.action_report_daily_summary"
        ).report_action(self)

    def get_report_data(self):
        user_tz = pytz.timezone(self.env.user.tz or "Asia/Kolkata")

        # Start and End of the selected day in UTC
        start_utc = (
            user_tz.localize(datetime.combine(self.date, time.min))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        end_utc = (
            user_tz.localize(datetime.combine(self.date, time.max))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )

        # 1. Total Active Employees
        all_employees = self.env["hr.employee"].search(
            [("active", "=", True)], order="name asc"
        )
        total_employees = len(all_employees)

        # 2. Batch check statuses for this date
        status_map = all_employees.get_attendance_statuses_for_date_batch(self.date, user_tz)

        present_count = 0
        absent_count = 0
        on_leave_count = 0

        absent_employees = []
        on_leave_employees = []

        for emp in all_employees:
            status, reason = status_map.get(emp.id, ("absent", False))
            emp_info = {
                "name": emp.name,
                "company": emp.company_id.name or "-",
                "department": emp.department_id.name or "-",
            }

            if status == "present":
                present_count += 1
            elif status in ("leave", "holiday"):
                on_leave_count += 1
                emp_info["type"] = reason or _("On Leave")
                on_leave_employees.append(emp_info)
            elif status == "absent":
                absent_count += 1
                absent_employees.append(emp_info)
            elif status == "weekend":
                # Do not count weekend as present, absent or on leave
                pass

        # 3. Late Arrivals and Early Departures
        late_count = self.env["hr.attendance"].search_count(
            [
                ("check_in", ">=", start_utc),
                ("check_in", "<=", end_utc),
                ("is_late", "=", True),
            ]
        )
        early_count = self.env["hr.attendance"].search_count(
            [
                ("check_out", ">=", start_utc),
                ("check_out", "<=", end_utc),
                ("is_early_leaving", "=", True),
            ]
        )

        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day": self.date.strftime("%A"),
            "total_employees": total_employees,
            "present_count": present_count,
            "absent_count": absent_count,
            "on_leave_count": on_leave_count,
            "late_count": late_count,
            "early_count": early_count,
            "absent_employees": absent_employees,
            "on_leave_employees": on_leave_employees,
            "generated_on": pytz.utc.localize(datetime.utcnow())
            .astimezone(user_tz)
            .strftime("%Y-%m-%d %H:%M"),
            "generated_by": self.env.user.name,
        }
