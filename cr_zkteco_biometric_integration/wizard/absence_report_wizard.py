# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
from datetime import datetime, time, timedelta
import pytz


class BiometricAbsenceReportWizard(models.TransientModel):
    _name = "biometric.absence.report.wizard"
    _description = "Absence Report Wizard (PDF)"

    from_date = fields.Date(
        string="From Date", required=True, default=fields.Date.context_today
    )
    to_date = fields.Date(
        string="To Date", required=True, default=fields.Date.context_today
    )

    def action_print_pdf(self):
        return self.env.ref(
            "cr_zkteco_biometric_integration.action_report_absence"
        ).report_action(self)

    def get_report_data(self):
        user_tz = pytz.timezone(self.env.user.tz or "Asia/Kolkata")
        employees = self.env["hr.employee"].search(
            [("active", "=", True)], order="name asc"
        )

        absent_data = []
        delta = self.to_date - self.from_date

        for i in range(delta.days + 1):
            current_date = self.from_date + timedelta(days=i)

            # Start and End of the current_date in UTC
            start_utc = (
                user_tz.localize(datetime.combine(current_date, time.min))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
            )
            end_utc = (
                user_tz.localize(datetime.combine(current_date, time.max))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
            )

            # Find all attendances for this day
            attendances = self.env["hr.attendance"].search(
                [("check_in", ">=", start_utc), ("check_in", "<=", end_utc)]
            )
            present_emp_ids = attendances.mapped("employee_id").ids

            for emp in employees:
                if emp.id not in present_emp_ids:
                    absent_data.append(
                        {
                            "employee": emp.name,
                            "department": emp.department_id.name or "-",
                            "company": emp.company_id.name or "-",
                            "date": current_date.strftime("%Y-%m-%d"),
                            "day": current_date.strftime("%a"),
                        }
                    )

        return {
            "from_date": self.from_date.strftime("%Y-%m-%d"),
            "to_date": self.to_date.strftime("%Y-%m-%d"),
            "absent_records": absent_data,
            "total_absences": len(absent_data),
            "generated_on": pytz.utc.localize(datetime.utcnow())
            .astimezone(user_tz)
            .strftime("%Y-%m-%d %H:%M"),
        }
