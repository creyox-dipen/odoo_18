# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
from datetime import datetime, time
import pytz


class BiometricCalculateAttendanceWizard(models.TransientModel):
    _name = "biometric.calculate.attendance.wizard"
    _description = "Calculate Attendance from Logs"

    from_date = fields.Date(
        string="From Date", required=True, default=fields.Date.context_today
    )
    to_date = fields.Date(
        string="To Date", required=True, default=fields.Date.context_today
    )

    def action_calculate(self):
        # 1. Resolve Timezone from User Profile
        user_tz_name = self.env.user.tz or "Asia/Kolkata"
        local_tz = pytz.timezone(user_tz_name)

        # 2. Search for unprocessed logs in range
        # Note: We use datetime.combine to ensure we cover the full day
        from_dt = datetime.combine(self.from_date, time.min)
        to_dt = datetime.combine(self.to_date, time.max)

        logs = self.env["biometric.attendance.log"].search(
            [
                ("timestamp", ">=", from_dt),
                ("timestamp", "<=", to_dt),
                ("status", "in", ["new", "processed", "failed"]),
                ("employee_id", "!=", False),
            ],
            order="timestamp asc",
        )

        if not logs:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Calculation Complete"),
                    "message": _(
                        "No new logs found to process for the selected range."
                    ),
                    "sticky": False,
                },
            }

        # 3. Group logs by Employee and Date (Local)
        # Structure: {employee_id: {date: [log_ids]}}
        grouped_logs = {}
        for log in logs:
            # Convert UTC timestamp to local date for grouping
            ts_local = pytz.utc.localize(log.timestamp).astimezone(local_tz)
            log_date = ts_local.date()

            emp_id = log.employee_id.id
            if emp_id not in grouped_logs:
                grouped_logs[emp_id] = {}
            if log_date not in grouped_logs[emp_id]:
                grouped_logs[emp_id][log_date] = []
            grouped_logs[emp_id][log_date].append(log)

        # 4. Create or Update hr.attendance
        for emp_id, dates in grouped_logs.items():
            for att_date, day_logs in dates.items():
                first_punch = day_logs[0].timestamp  # UTC
                last_punch = day_logs[-1].timestamp  # UTC

                # Check if an attendance already exists for this employee on this local date
                # We search for attendances where the check_in (localized) is on att_date
                # Start of day (UTC) and End of day (UTC) for that local date
                start_local = (
                    local_tz.localize(datetime.combine(att_date, time.min))
                    .astimezone(pytz.utc)
                    .replace(tzinfo=None)
                )
                end_local = (
                    local_tz.localize(datetime.combine(att_date, time.max))
                    .astimezone(pytz.utc)
                    .replace(tzinfo=None)
                )

                existing_atts = self.env["hr.attendance"].search(
                    [
                        ("employee_id", "=", emp_id),
                        ("check_in", ">=", start_local),
                        ("check_in", "<=", end_local),
                    ],
                    order="check_in asc",
                )

                if existing_atts:
                    # Consolidate all attendances of the day into the first one
                    main_att = existing_atts[0]
                    other_atts = existing_atts[1:]

                    # Determine final check_in/out from all sources (logs + existing records)
                    final_in = min(first_punch, main_att.check_in)

                    # Get max check_out from main, others, and last log punch
                    all_outs = [last_punch, main_att.check_out]
                    for other in other_atts:
                        if other.check_in:
                            all_outs.append(other.check_in)
                        if other.check_out:
                            all_outs.append(other.check_out)

                    final_out = (
                        max([o for o in all_outs if o])
                        if any(o for o in all_outs if o)
                        else None
                    )

                    # Delete redundant attendance records first to avoid overlap validation errors
                    if other_atts:
                        other_atts.unlink()

                    # Ensure check_out is strictly after check_in
                    if final_out and final_out <= final_in:
                        final_out = False

                    main_att.write({"check_in": final_in, "check_out": final_out})
                else:
                    # Create new attendance
                    if len(day_logs) > 1:
                        self.env["hr.attendance"].create(
                            {
                                "employee_id": emp_id,
                                "check_in": first_punch,
                                "check_out": last_punch,
                            }
                        )
                    else:
                        self.env["hr.attendance"].create(
                            {
                                "employee_id": emp_id,
                                "check_in": first_punch,
                            }
                        )

                # Mark all logs in this group as processed
                for log in day_logs:
                    log.write({"status": "processed"})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Attendance calculation completed successfully."),
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
