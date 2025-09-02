# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api
from collections import defaultdict

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.onchange('location_id')
    def auto_populate_product_packages(self):
        # if not self.picking_type_id or self.picking_type_id != self.env.ref(
        #         'cr_logistics.pallet_transfer_operation_type_id'):
        #     return
        # quants = self.env['stock.quant'].search([('location_id', '=', self.location_id.id), ('quantity', '>', 0)])
        # if not quants:
        #     return
        # print("It is pallet transfer")
        # print(self.location_id)
        # moves = self.env['stock.move'].search([('location_dest_id', '=', self.location_id.id)])
        # print(moves)
        # for move in moves :
        #     print("for this move")
        #     print(move.picking_id)

        # self.move_ids_without_package = self.env['stock.move'].search([('location_dest_id', '=', self.location_id.id)])

        if not self.location_id:
            return

        self.move_ids_without_package = [(5, 0, 0)]

        quants = self.env['stock.quant'].search([
            ('location_id', '=', self.location_id.id),
            ('quantity', '>', 0),
            ('package_id', '=', False),
        ])

        move_vals = []
        for quant in quants:
            move_vals.append((0, 0, {
                'name': quant.product_id.display_name,
                'product_id': quant.product_id.id,
                'product_uom_qty': quant.quantity,
                'product_uom': quant.product_id.uom_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id or False,
            }))

        self.move_ids_without_package = move_vals

        # populating the packages
        source_packages = self.env['stock.quant.package'].search([
            ('location_id', '=', self.location_id.id)
        ])

        package_levels = []
        for package in source_packages:
            package_levels.append((0, 0, {
                'picking_id': self.id,
                'package_id': package.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
            }))

        self.package_level_ids = package_levels