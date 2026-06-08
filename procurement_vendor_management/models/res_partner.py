# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vendor_rating = fields.Float(string="Vendor Rating (0-5)", compute="_compute_vendor_metrics", group_operator="avg")
    delivery_score = fields.Float(string="Delivery Score (0-100)", compute="_compute_vendor_metrics", group_operator="avg")
    quality_score = fields.Float(string="Quality Score (0-100)", compute="_compute_vendor_metrics", group_operator="avg")
    on_time_percentage = fields.Float(string="On-Time Delivery (%)", compute="_compute_vendor_metrics", group_operator="avg")
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    total_procurement_amount = fields.Monetary(string="Total Procurement Spend", compute="_compute_vendor_metrics", currency_field='currency_id')
    total_completed_orders = fields.Integer(string="Total Completed Orders", compute="_compute_vendor_metrics")

    def _compute_vendor_metrics(self):
        for partner in self:
            # 1. Total Completed Orders and Total Procurement Amount
            # We define completed orders as purchase orders in state 'purchase' or 'done'
            completed_pos = self.env['purchase.order'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ('purchase', 'done'))
            ])
            partner.total_completed_orders = len(completed_pos)
            partner.total_procurement_amount = sum(completed_pos.mapped('amount_total'))

            # 2. On-Time Delivery Percentage & Delivery Score
            # Check all pickings (receipts) related to the partner's purchase orders if inventory integration exists
            if 'picking_ids' in self.env['purchase.order']._fields:
                all_pickings = completed_pos.mapped('picking_ids').filtered(lambda p: p.picking_type_code == 'incoming' and p.state == 'done')
                if all_pickings:
                    on_time_pickings = all_pickings.filtered(lambda p: p.date_done and p.scheduled_date and p.date_done <= p.scheduled_date)
                    on_time_pct = (len(on_time_pickings) / len(all_pickings)) * 100.0
                else:
                    on_time_pct = 100.0 # Default if no delivery history
            else:
                on_time_pct = 100.0

            partner.on_time_percentage = on_time_pct
            partner.delivery_score = on_time_pct

            # 3. Quality Score
            # Compute based on quantity received vs quantity ordered in completed POs
            total_ordered_qty = 0.0
            total_received_qty = 0.0
            for line in completed_pos.mapped('order_line'):
                total_ordered_qty += line.product_qty
                total_received_qty += line.qty_received

            if total_ordered_qty > 0:
                # Cap quality score at 100% (extra deliveries don't increase it beyond 100%)
                q_score = min((total_received_qty / total_ordered_qty) * 100.0, 100.0)
            else:
                q_score = 100.0 # Default if no PO lines

            partner.quality_score = q_score

            # 4. Approval Rate (from vendor.quotation submissions)
            # Find all quotations for this vendor
            quotations = self.env['vendor.quotation'].search([('vendor_id', '=', partner.id)])
            submitted_quotes = quotations.filtered(lambda q: q.state in ('submitted', 'accepted', 'rejected'))
            accepted_quotes = quotations.filtered(lambda q: q.state == 'accepted')
            
            if submitted_quotes:
                approval_rate = (len(accepted_quotes) / len(submitted_quotes)) * 100.0
            else:
                approval_rate = 100.0 # Default if no quotes submitted

            # 5. Overall Vendor Rating (0-5 scale)
            # Combine: Delivery Score (40%), Quality Score (40%), and Approval Rate (20%)
            overall_pct = (partner.delivery_score * 0.4) + (partner.quality_score * 0.4) + (approval_rate * 0.2)
            partner.vendor_rating = round(overall_pct / 20.0, 2)
