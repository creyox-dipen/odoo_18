# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

def generate_attendance_pdf(attendances, report_date, report_type):
    from pytz import UTC, timezone  # Import here if not at top
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    # Heading
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "ROVR Store – Daily Attendance Report")
    y -= 30
    pdf.setFont("Helvetica", 12)
    type_label = "Morning Report (Check-in)" if report_type == "morning" else "Evening Report (Check-out)"
    pdf.drawString(50, y, f"{report_date.strftime('%d/%m/%Y')} – {type_label}")
    y -= 40
    # Table Header
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Employee")
    pdf.drawString(300, y, "Time")
    y -= 20
    pdf.line(50, y, width - 50, y)
    y -= 20
    pdf.setFont("Helvetica", 11)
    # Rows - FIXED: Explicit pytz conversion to Israel timezone (handles Odoo UTC storage)
    israel_tz = 'Asia/Jerusalem'
    for att in attendances:
        time_value = att.check_in if report_type == "morning" else att.check_out
        if not time_value:
            continue
        # Assume time_value is naive UTC (Odoo standard) - localize and convert
        utc_dt = UTC.localize(time_value.replace(tzinfo=None))
        local_tz = timezone(israel_tz)
        local_dt = utc_dt.astimezone(local_tz)
        type = "Clock-in: " if report_type == "morning" else "Clock-out: "
        time_str = type + local_dt.strftime('%H:%M')
        if y < 60:
            pdf.showPage()
            y = height - 80
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(50, y, "Employee")
            pdf.drawString(300, y, "Time")
            y -= 20
            pdf.line(50, y, width - 50, y)
            y -= 20
            pdf.setFont("Helvetica", 11)
        pdf.drawString(50, y, att.employee_id.name)
        pdf.drawString(300, y, time_str)  # Use converted time_str
        y -= 20
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()