# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import re
from odoo import models, fields, api, _

class ChannableAttributeMapping(models.Model):
    _name = 'channable.attribute.mapping'
    _description = 'Channable Attribute Mapping'
    _order = 'id'

    marketplace_id = fields.Many2one(
        'channable.marketplace', string='Marketplace',
        required=True, ondelete='cascade'
    )
    mapping_type = fields.Selection([
        ('field', 'Product Field'),
        ('attribute', 'Product Attribute'),
    ], string='Mapping Type', required=True, default='attribute')
    
    # If mapping_type is 'field'
    field_id = fields.Many2one(
        'ir.model.fields', string='Product Field',
        domain="[('model', 'in', ('product.product', 'product.template'))]",
        help="Choose a standard or custom field from the product model to export."
    )
    
    # If mapping_type is 'attribute'
    attribute_id = fields.Many2one(
        'product.attribute', string='Product Attribute',
        help="Choose a variant attribute (e.g. Color, Size) to export."
    )
    
    # Target XML tag name
    target_tag = fields.Char(
        string='Target XML Tag', required=True,
        help="The tag name inside the XML feed (e.g. color, size, material)"
    )

    _sql_constraints = [
        ('uniq_tag_marketplace', 'unique(marketplace_id, target_tag)', 'The target XML tag must be unique per marketplace!')
    ]

    @api.constrains('target_tag')
    def _check_target_tag(self):
        for rec in self:
            if not rec.target_tag:
                continue
            # XML tags must start with a letter or underscore and contain only alphanumeric, hyphens, or underscores
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', rec.target_tag):
                raise models.ValidationError(_("The target XML tag name '%s' is invalid. It must start with a letter or underscore and contain only alphanumeric characters, hyphens, or underscores.") % rec.target_tag)
