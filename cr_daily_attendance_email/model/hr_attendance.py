# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import xlsxwriter
from datetime import datetime, date
from odoo import models, api, fields
from odoo.tools import format_datetime
from odoo.exceptions import UserError
from ..report.attendance_pdf import generate_attendance_pdf
import io
import base64

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def send_daily_attendance_report(self, report_type='morning'):

        today = date.today()
        report_time_str = "Morning" if report_type == 'morning' else "Evening"
        subject = f"Daily Attendance Report – ROVR Store Employees"

        attendances = self.search([
            ('check_in', '>=', today.strftime('%Y-%m-%d 00:00:00')),
            ('check_in', '<=', today.strftime('%Y-%m-%d 23:59:59')),
        ])

        if not attendances:
            return

        # --- PURE PYTHON PDF (NO TEMPLATE) ---
        pdf_report = generate_attendance_pdf(attendances, today, report_type)
        print(pdf_report)

        # Excel (you already have)
        excel_file = self._generate_excel_report(attendances, report_type, today)

        # Attach files
        attachments = []
        for fname, fdata in [
            (f"ROVR_Attendance_{today}_{report_time_str}_Report.pdf", pdf_report),
            (f"ROVR_Attendance_{today}_{report_time_str}_Report.xlsx", excel_file),
        ]:
            attachment = self.env['ir.attachment'].create({
                'name': fname,
                'datas': base64.b64encode(fdata),
                'res_model': 'hr.attendance',
                'public': False,
            })
            attachments.append(attachment.id)

        # Email body
        body = f"""
                Hello Candys,<br/><br/>
                Please find attached the daily attendance report for all ROVR store employees.<br/>
                The report includes the clock-in and clock-out times for each employee.<br/><br/>
                <strong>Report Details:</strong><br/>
                Date: {today.strftime('%d/%m/%Y')}<br/>
                Report Time: {report_time_str}<br/>
                Format: PDF + Excel attached<br/><br/>
                If you have any questions or need any adjustments, feel free to let us know.<br/><br/>
                Kind regards,<br/>
                <strong>ROVR Support Team</strong>
            """

        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': 'candys@example.com',
            'attachment_ids': [(6, 0, attachments)],
        }

        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def _generate_excel_report(self, attendances, report_type, report_date):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(f"Attendance {report_date}")

        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        cell_format = workbook.add_format({'border': 1})

        headers = ['Employee', 'Time']
        worksheet.write_row(0, 0, headers, header_format)

        row = 1
        for att in attendances:
            employee_name = att.employee_id.name
            if report_type == 'morning' and att.check_in:
                time_str = format_datetime(self.env, att.check_in, dt_format='HH:mm')
                worksheet.write_row(row, 0, [employee_name, f"Clock-in: {time_str}"], cell_format)
            elif report_type == 'evening' and att.check_out:
                time_str = format_datetime(self.env, att.check_out, dt_format='HH:mm')
                worksheet.write_row(row, 0, [employee_name, f"Clock-out: {time_str}"], cell_format)
            row += 1

        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 20)
        workbook.close()
        output.seek(0)
        return output.read()