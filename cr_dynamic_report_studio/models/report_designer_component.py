from odoo import models, fields

class ReportDesignerComponent(models.Model):
    _name = 'report.designer.component'
    _description = 'Canvas Component'
    _order = 'z_index, sequence, id'

    template_id = fields.Many2one('report.designer.template', string='Template', required=True, ondelete='cascade')
    page_id = fields.Many2one('report.designer.template.page', string='Page', required=True, ondelete='cascade')
    component_type = fields.Selection([
        ('text', 'Text'),
        ('field', 'Field'),
        ('image', 'Image'),
        ('barcode', 'Barcode'),
        ('qrcode', 'QR Code'),
        ('table', 'Table'),
        ('section', 'Section'),
        ('shape', 'Shape'),
        ('line', 'Line'),
        ('pagebreak', 'Page Break')
    ], string='Component Type', required=True)
    name = fields.Char(string='Internal Label', required=True)
    pos_x = fields.Float(string='Position X (mm)', default=0.0)
    pos_y = fields.Float(string='Position Y (mm)', default=0.0)
    width = fields.Float(string='Width (mm)', default=50.0)
    height = fields.Float(string='Height (mm)', default=10.0)
    z_index = fields.Integer(string='Z-Index', default=1)
    rotation = fields.Float(string='Rotation (degrees)', default=0.0)
    is_locked = fields.Boolean(string='Locked', default=False)
    is_visible = fields.Boolean(string='Visible', default=True)
    style_json = fields.Text(string='Style JSON', default='{}')
    data_json = fields.Text(string='Data JSON', default='{}')
    parent_id = fields.Many2one('report.designer.component', string='Parent Component', ondelete='cascade')
    children_ids = fields.One2many('report.designer.component', 'parent_id', string='Child Components')
    sequence = fields.Integer(string='Sequence', default=10)
    conditional_visibility = fields.Text(string='Conditional Visibility')
    repeat_for_field = fields.Char(string='Repeat For Field')
