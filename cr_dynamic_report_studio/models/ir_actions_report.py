from odoo import models
import base64


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # Render the PDF
        pdf_content, ext = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )

        # Check if this is a custom report designer template
        report = self._get_report(report_ref)
        template = False
        if report:
            template = self.env["report.designer.template"].search(
                [("report_action_id", "=", report.id)], limit=1
            )

        if not template and report_ref:
            # Fallback search by parsing the template ID suffix (e.g. cr_report_designer.report_designer_template_4 -> ID 4)
            try:
                parts = report_ref.split("_")
                if parts:
                    template_id = int(parts[-1])
                    template = (
                        self.env["report.designer.template"]
                        .browse(template_id)
                        .exists()
                    )
            except Exception:
                pass

        if template and res_ids:
            # Create a log entry for each record
            for res_id in res_ids:
                self.env["report.designer.print.log"].sudo().create(
                    {
                        "template_id": template.id,
                        "res_model": report.model,
                        "res_id": res_id,
                        "pdf_size_kb": len(pdf_content) // 1024,
                        "pdf_file": base64.b64encode(pdf_content),
                        "pdf_file_name": f"{report.name}_{res_id}.pdf",
                    }
                )
            # Print log registration completed
            pass

        return pdf_content, ext
