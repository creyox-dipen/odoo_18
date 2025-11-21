from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import io


def generate_attendance_pdf(attendances, report_date, report_type):
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

    # Rows
    for att in attendances:
        time_value = att.check_in if report_type == "morning" else att.check_out

        if not time_value:
            continue

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
        pdf.drawString(300, y, time_value.strftime("%H:%M"))
        y -= 20

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return buffer.read()