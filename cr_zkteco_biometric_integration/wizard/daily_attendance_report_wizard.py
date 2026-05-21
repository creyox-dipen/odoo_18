# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
from datetime import datetime, time
import pytz


class BiometricDailyAttendanceReportWizard(models.TransientModel):
    _name = "biometric.daily.attendance.report.wizard"
    _description = "Daily Attendance Report Wizard (PDF)"

    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    def action_print_pdf(self):
        return self.env.ref(
            "cr_zkteco_biometric_integration.action_report_daily_attendance"
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

        # Fetch only present employees for this specific report
        attendances = self.env["hr.attendance"].search(
            [("check_in", ">=", start_utc), ("check_in", "<=", end_utc)],
            order="employee_id asc",
        )

        report_lines = []
        total_hours = 0.0
        for att in attendances:
            worked = att.worked_hours or 0.0
            total_hours += worked

            # Format times for the report
            in_local = pytz.utc.localize(att.check_in).astimezone(user_tz)
            out_local = (
                pytz.utc.localize(att.check_out).astimezone(user_tz)
                if att.check_out
                else None
            )

            report_lines.append(
                {
                    "employee": att.employee_id.name,
                    "check_in": in_local.strftime("%H:%M:%S"),
                    "check_out": out_local.strftime("%H:%M:%S") if out_local else "-",
                    "worked_hours": f"{worked:.2f}",
                    "difference": f"{worked:.2f}",  # Placeholder for difference
                }
            )

        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "day": self.date.strftime("%A"),
            "present_count": len(attendances),
            "total_hours": f"{total_hours:.2f}",
            "lines": report_lines,
            "generated_on": pytz.utc.localize(datetime.utcnow())
            .astimezone(user_tz)
            .strftime("%Y-%m-%d %H:%M"),
            "generated_by": self.env.user.name,
            "company": self.env.company.name,
        }
