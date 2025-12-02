# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields

class DataProcessingLog(models.Model):
    _name = 'cr.data.processing.log'
    _description = 'Log of data processing operations'

    table_name = fields.Char('Table Name', required=True)
    record_count = fields.Integer('Number of Records', required=True)
    status = fields.Selection([
        ('success', 'Success'),
        ('failure', 'Failure')
    ], default='success', required=True)
    error_message = fields.Text('Error Message')
    timestamp = fields.Char('Timestamp')
    initiated_at = fields.Char('Initiated At ')

