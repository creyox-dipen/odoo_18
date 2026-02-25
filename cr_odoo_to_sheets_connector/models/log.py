# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields

class DataProcessingLog(models.Model):
    _name = 'cr.data.processing.log'
    _description = 'Log of data processing operations'
    _order = 'create_date desc'

    table_name = fields.Char('Table Name', required=True)
    operation_type = fields.Selection([
        ('sheet_to_odoo', 'Sheet to Odoo'),
        ('odoo_to_sheet', 'Odoo to Sheet'),
        ('fetch_models_list', 'Fetch Models List'),
        ('fetch_model_fields', 'Fetch Model Fields')
    ], string='Operation Type', required=True, default='sheet_to_odoo')
    record_count = fields.Integer('Total Records', required=True)
    success_count = fields.Integer('Successful Records', default=0)
    failed_count = fields.Integer('Failed Records', default=0)
    partial_count = fields.Integer('Partially Updated Records', default=0)
    status = fields.Selection([
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failure', 'Failure')
    ], string='Status', default='success', required=True)
    message = fields.Text('Summary')
    error_message = fields.Text('Error Details')
    detailed_errors = fields.Text('Detailed Errors (JSON)')
    timestamp = fields.Char('Duration')
    initiated_at = fields.Datetime('Started At')
    completed_at = fields.Datetime('Completed At')
