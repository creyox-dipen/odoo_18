from odoo import models, fields

class ReportDesignerPrintLog(models.Model):
    _name = 'report.designer.print.log'
    _description = 'Print History'

    template_id = fields.Many2one('report.designer.template', string='Template', required=True, ondelete='cascade')
    res_model = fields.Char(string='Record Model', required=True)
    res_id = fields.Integer(string='Record ID', required=True)
    user_id = fields.Many2one('res.users', string='Printed By', default=lambda self: self.env.user)
    print_date = fields.Datetime(string='Print Date', default=fields.Datetime.now)
    pdf_size_kb = fields.Integer(string='PDF Size (KB)')
    
    pdf_file = fields.Binary(string='PDF Document', attachment=True, readonly=True)
    pdf_file_name = fields.Char(string='File Name')
