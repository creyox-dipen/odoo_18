# -*- coding: utf-8 -*-
from odoo import models, fields

class ApprovalHistory(models.Model):
    _name = 'approval.history'
    _description = 'Procurement Approval History'
    _order = 'date desc, id desc'

    purchase_id = fields.Many2one('purchase.order', string="RFQ / Purchase Order", required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string="User", required=True, default=lambda self: self.env.user)
    action = fields.Selection([
        ('RFQ Created', 'RFQ Created'),
        ('RFQ Sent', 'RFQ Sent'),
        ('Vendor Submitted Quote', 'Vendor Submitted Quote'),
        ('Approval Requested', 'Approval Requested'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('PO Generated', 'PO Generated')
    ], string="Action", required=True)
    remark = fields.Text(string="Remarks/Details")
    date = fields.Datetime(string="Date", default=fields.Datetime.now, required=True)
