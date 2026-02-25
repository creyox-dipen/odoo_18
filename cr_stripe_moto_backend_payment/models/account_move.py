# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    def open_moto_payment_wizard(self):
        print("opening moto payment wizard")
        return {
            'name': 'moto payment wizard',
            'res_model': 'moto.payment.wizard',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'target': 'new',
        }