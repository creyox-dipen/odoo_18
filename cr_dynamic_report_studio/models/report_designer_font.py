from odoo import models, fields


class ReportDesignerFont(models.Model):
    _name = "report.designer.font"
    _description = "Custom Font Registry"

    name = fields.Char(string="Display Name", required=True)
    font_family = fields.Char(string="CSS Font Family", required=True)
    font_file_regular = fields.Binary(
        string="Regular Font File", required=True, attachment=True
    )
    font_file_bold = fields.Binary(string="Bold Font File", attachment=True)
    font_file_italic = fields.Binary(string="Italic Font File", attachment=True)
    supports_cjk = fields.Boolean(string="Supports CJK", default=False)
    supports_rtl = fields.Boolean(string="Supports RTL", default=False)
    is_system = fields.Boolean(string="Is System Font", default=False)
