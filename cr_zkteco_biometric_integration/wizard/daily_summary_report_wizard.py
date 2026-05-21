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

        # 2. Attendances for the day
        attendances = self.env["hr.attendance"].search(
            [("check_in", ">=", start_utc), ("check_in", "<=", end_utc)]
        )
        present_emp_ids = attendances.mapped("employee_id").ids
        present_count = len(set(present_emp_ids))
        absent_count = total_employees - present_count

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

        # 4. List of Absent Employees
        absent_employees = []
        for emp in all_employees:
            if emp.id not in present_emp_ids:
                absent_employees.append(
                    {
                        "name": emp.name,
                        "company": emp.company_id.name or "-",
                        "department": emp.department_id.name or "-",
                    }
                )

        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day": self.date.strftime("%A"),
            "total_employees": total_employees,
            "present_count": present_count,
            "absent_count": absent_count,
            "late_count": late_count,
            "early_count": early_count,
            "absent_employees": absent_employees,
            "generated_on": pytz.utc.localize(datetime.utcnow())
            .astimezone(user_tz)
            .strftime("%Y-%m-%d %H:%M"),
            "generated_by": self.env.user.name,
        }
