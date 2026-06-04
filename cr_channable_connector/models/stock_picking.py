# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    channable_sync_status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
        ('manual', 'Manual'),
    ], string='Channable Sync Status', default='pending', copy=False)

    def button_validate(self):
        """Immediately trigger Channable shipment sync when picking is validated."""
        res = super(StockPicking, self).button_validate()
        if self.env.context.get('skip_channable_shipment_notify'):
            return res
        for picking in self:
            if (picking.state == 'done' 
                    and picking.picking_type_code == 'outgoing' 
                    and picking.sale_id 
                    and picking.sale_id.channable_order_id
                    and picking.channable_sync_status != 'done'):
                try:
                    picking.sale_id.action_channable_notify_shipped()
                except Exception as e:
                    _logger.warning("Immediate Channable shipment sync failed for order %s: %s", picking.sale_id.name, str(e))
        return res
