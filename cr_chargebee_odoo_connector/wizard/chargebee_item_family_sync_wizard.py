from odoo import models, fields, api, _
import chargebee

class ChargebeeItemFamilySyncWizard(models.TransientModel):
    _name = 'chargebee.item.family.sync.wizard'
    _description = 'Sync Chargebee Item Families Wizard'

    sync_confirmed = fields.Boolean(string="Sync Confirmed", default=False)
    message = fields.Text(
        default="Click 'Sync' to fetch item families from Chargebee."
    )

    def action_sync(self):
        """Perform the sync and close the wizard."""
        self.env['chargebee.item.family'].sync_item_families()
        return {'type': 'ir.actions.act_window_close'}