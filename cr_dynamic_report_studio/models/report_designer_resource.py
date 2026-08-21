from odoo import models, fields

class ReportDesignerResource(models.Model):
    _name = 'report.designer.resource'
    _description = 'Image Library'

    name = fields.Char(string='Image Name', required=True)
    image = fields.Binary(string='Image', required=True, attachment=True)
    image_small = fields.Binary(string='Thumbnail', attachment=True)
    mime_type = fields.Char(string='MIME Type')
    file_size = fields.Integer(string='File Size (Bytes)')
    category = fields.Selection([
        ('logo', 'Logo'),
        ('background', 'Background'),
        ('icon', 'Icon'),
        ('other', 'Other')
    ], string='Category', default='other')
