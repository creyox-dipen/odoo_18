# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ApprovalRemarkWizard(models.TransientModel):
    _name = 'approval.remark.wizard'
    _description = 'RFQ Approval Remark Wizard'

    purchase_id = fields.Many2one('purchase.order', string="RFQ Reference", required=True)
    remark = fields.Text(string="Remark/Comment", required=True)
    action = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string="Action", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.remark or not self.remark.strip():
            raise UserError(_("Please provide a mandatory remark before proceeding."))

        order = self.purchase_id
        if self.action == 'approve':
            order.hackathon_state = 'approved'
            order.approval_remark = self.remark
            order._create_history_record('Approved', self.remark)
            # Send approved email notification
            order._notify_approval_approved()
        elif self.action == 'reject':
            order.hackathon_state = 'rejected'
            order.approval_remark = self.remark
            order._create_history_record('Rejected', self.remark)
            # Send rejected email notification
            order._notify_approval_rejected()

        return {'type': 'ir.actions.act_window_close'}
