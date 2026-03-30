# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Extends Odoo's res.config.settings to add CalDAV Sync configuration.

    Adds a toggle to enable/disable the CalDAV sync feature globally, and a
    shortcut button to open the CalDAV Accounts management form.
    """

    _inherit = 'res.config.settings'

    caldav_sync_enabled = fields.Boolean(
        string='Enable CalDAV Sync',
        config_parameter='cr_odoo_caldav_sync.enabled',
        help=(
            'When enabled, Odoo will automatically sync calendar events with '
            'configured CalDAV servers every 15 minutes.'
        ),
    )
    caldav_google_client_id = fields.Char(
        string='Google Client ID',
        config_parameter='cr_odoo_caldav_sync.google_client_id',
        help='Client ID from Google Cloud Console for OAuth 2.0.',
    )
    caldav_google_client_secret = fields.Char(
        string='Google Client Secret',
        config_parameter='cr_odoo_caldav_sync.google_client_secret',
        help='Client Secret from Google Cloud Console for OAuth 2.0.',
    )

    def set_values(self):
        """Toggle the visibility of the CalDAV Accounts menu based on the setting.

        If disabled, the menu is deactivated (active=False).
        """
        super().set_values()
        menu = self.env.ref('cr_odoo_caldav_sync.menu_caldav_accounts', raise_if_not_found=False)
        if menu:
            menu.sudo().active = self.caldav_sync_enabled

    def action_open_caldav_accounts(self):
        """Open the CalDAV Accounts list/form view.

        :return: Window action to open the CalDAV Accounts view.
        :rtype: dict
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'CalDAV Accounts',
            'res_model': 'caldav.account',
            'view_mode': 'list,form',
            'target': 'current',
        }
