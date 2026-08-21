from odoo import models, fields

class ReportDesignerTemplatePage(models.Model):
    _name = 'report.designer.template.page'
    _description = 'Template Page'
    _order = 'sequence, id'

    template_id = fields.Many2one('report.designer.template', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Page Name', required=True)
    page_break_before = fields.Boolean(string='Page Break Before', default=False)
    background_color = fields.Char(string='Background Color', default='#FFFFFF')
    background_image = fields.Binary(string='Background Image', attachment=True)
    component_ids = fields.One2many('report.designer.component', 'page_id', string='Components')
