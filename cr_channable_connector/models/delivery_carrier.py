# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    channable_transporter_code = fields.Char(
        string='Transporter Code (Channable)',
        help='Transporter code supplied by Channable API'
    )
