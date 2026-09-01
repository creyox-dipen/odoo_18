from odoo import models, fields


class ReportDesignerComponentTemplate(models.Model):
    _name = "report.designer.component.template"
    _description = "Reusable Component Preset"

    name = fields.Char(string="Preset Name", required=True)
    component_type = fields.Selection(
        [
            ("text", "Text"),
            ("field", "Field"),
            ("image", "Image"),
            ("barcode", "Barcode"),
            ("qrcode", "QR Code"),
            ("table", "Table"),
            ("section", "Section"),
            ("shape", "Shape"),
            ("line", "Line"),
            ("pagebreak", "Page Break"),
        ],
        string="Component Type",
        required=True,
    )
    thumbnail = fields.Binary(string="Thumbnail", attachment=True)
    data_json = fields.Text(string="Preset Data JSON", default="{}")
    style_json = fields.Text(string="Preset Style JSON", default="{}")
    category = fields.Selection(
        [
            ("header", "Header"),
            ("footer", "Footer"),
            ("content", "Content"),
            ("branding", "Branding"),
        ],
        string="Category",
        default="content",
    )
    is_system = fields.Boolean(string="Is System Preset", default=False)
