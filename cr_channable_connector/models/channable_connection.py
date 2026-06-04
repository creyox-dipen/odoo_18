# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests


class ChannableConnection(models.Model):
    _name = 'channable.connection'
    _description = 'Channable Connection'

    name = fields.Char(string='Company Name', required=True)
    api_token = fields.Char(string='API Token', required=True)
    company_id_num = fields.Char(string='Company ID (Channable)', required=True)

    # Link to Odoo company so multi-company is properly scoped
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        ('company_token_uniq', 'unique(company_id_num, api_token)',
         'Only one connection can be configured with the same Company ID and API Token!')
    ]

    def action_test_connection(self):
        self.ensure_one()
        company_id = (self.company_id_num or '').strip()
        if not company_id:
            raise ValidationError(_("Please enter a valid Company ID (Channable)."))
            
        url = f'https://api.channable.com/v1/companies/{company_id}/projects'
        headers = {
            'Authorization': f'Bearer {self.api_token.strip()}',
            'Content-Type': 'application/json',
        }
        # 1. Try to test using the company projects endpoint (works for Personal tokens)
        url_projects = f'https://api.channable.com/v1/companies/{company_id}/projects'
        try:
            response = requests.get(url_projects, headers=headers, timeout=15)
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Channable Company ID: %s', company_id),
                        'type': 'success',
                        'sticky': False,
                    },
                }
        except Exception:
            pass
            
        # 2. If it's a restricted Company token (403/404 above), try using a configured project (or fallback to dummy project '0')
        project = self.env['channable.project'].search([('connection_id', '=', self.id)], limit=1)
        project_id = project.channable_identifier if project else '0'
        url_offers = f'https://api.channable.com/v1/companies/{company_id}/projects/{project_id}/offers'
        try:
            response = requests.get(url_offers, headers=headers, timeout=15)
            if response.status_code in (200, 404):
                message = _('Successfully connected to Channable Company ID: %s') % company_id
                if project:
                    message += _(' (verified via Project: %s)') % project.name
                else:
                    message += _(' (credentials verified)')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    },
                }
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 500
            error_msg = _("Unknown error occurred.")
            if e.response is not None:
                try:
                    res_data = e.response.json()
                    if isinstance(res_data, dict):
                        error_msg = res_data.get('message') or res_data.get('error') or e.response.text
                    else:
                        error_msg = e.response.text
                except Exception:
                    error_msg = e.response.text
            
            if status_code in (401, 403):
                message = _("Authentication Failed (Status %s): %s") % (status_code, error_msg)
            else:
                message = _("HTTP Error %s: %s") % (status_code, error_msg)
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': message,
                    'type': 'danger',
                    'sticky': True,
                },
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': _('Connection error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                },
            }
