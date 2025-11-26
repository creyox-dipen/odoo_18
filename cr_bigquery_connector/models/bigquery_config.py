# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo.exceptions import UserError
from odoo import models, fields, api, _
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
import json


class BigQueryConfig(models.Model):
    _name = 'cr.big.query.config'
    _rec_name = 'cr_name'
    _description = 'BigQuery Configuration'

    cr_name = fields.Char('Name', required=True)
    cr_project_id = fields.Char('BigQuery Project ID', required=True)
    cr_dataset_id = fields.Char('BigQuery Dataset ID', required=True)
    cr_credentials_json = fields.Text('BigQuery Credentials JSON', required=True)
    cr_company_id = fields.Many2one('res.company', 'Company', required=True)
    status = fields.Selection(
        selection=[
            ('not_verified', 'Not Verified'),
            ('verified', 'Verified'),
        ],
        string='Status',
        default='not_verified',
        required=True, copy=False
    )


    # _sql_constraints = [
    #     ('unique_cr_company_id', 'UNIQUE(cr_company_id)', 'This Company is already used.')
    # ]

    # Allow user to create multiple configuration with same company with different dataset id
    @api.constrains('cr_company_id', 'cr_dataset_id')
    def _check_company_dataset_unique(self):
        for rec in self:
            duplicate = self.search([
                ('cr_company_id', '=', rec.cr_company_id.id),
                ('cr_dataset_id', '=', rec.cr_dataset_id),
                ('id', '!=', rec.id)
            ], limit=1)

            if duplicate:
                raise UserError(_("Cannot Create Multiple Configuration with Duplicate Dataset ID with Company"))

    def _test_bigquery_connection(self):
        try:
            credentials_dict = json.loads(self.cr_credentials_json)  # converts credential json to python dict
            credentials = Credentials.from_service_account_info(
                credentials_dict)  # converts dict to bigquery credential object to allow secure authentication

            # creates a BigQuery client instance
            # This client object is used for all queries, exporting, listing datasets, etc
            client = bigquery.Client(credentials=credentials, project=self.cr_project_id)
            datasets = list(client.list_datasets())
            return True
        except Exception as e:
            raise UserError(_("Verification failed:\n%s") % str(e))

    def action_verify_credentials(self):
        for rec in self:
            if rec._test_bigquery_connection():
                rec.status = 'verified'
