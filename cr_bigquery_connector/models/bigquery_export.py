# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import base64
import csv
import os
import tempfile
from datetime import datetime, date
from odoo import models, fields, api, _
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
import json
from odoo.exceptions import ValidationError ,UserError
import binascii


class BigQueryExport(models.Model):
    _name = 'cr.big.query.export'
    _description = 'BigQuery Data Export'
    _rec_name = 'cr_name'

    cr_name = fields.Char('Name', required=True)
    cr_config_id = fields.Many2one('cr.big.query.config', 'Configuration', required=True,
                                   ondelete='cascade', domain="[('status', '=', 'verified')]")
    cr_export_model_ids = fields.Many2many(
        'ir.model', 'export_models',
        string='Models to Export',
        help="Select the model to export to BigQuery", required=True,
    )
    cr_export_cron_value_ = fields.Integer(string='Schedule Export time', readonly=False, store=True)
    cr_export_scheduled_units_ = fields.Selection(
        [('hours', 'Hours'), ('minutes', 'Minute'), ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
        string="Export Cron Units", default="hours", readonly=False, store=True)
    cr_import_model_ids = fields.Many2many(
        'ir.model', 'import_models',
        string='Models to Import',
        help="Select the model to import from BigQuery", required=True,
    )
    cr_import_cron_value_ = fields.Integer(string='Schedule Import time', readonly=False, store=True)
    cr_import_scheduled_units_ = fields.Selection(
        [('hours', 'Hours'), ('minutes', 'Minute'), ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
        string="Import Cron Units", default="hours", readonly=False, store=True)
    cr_export_cron_job_id = fields.Many2one("ir.cron", string="Scheduled Action", readonly=True)
    cr_import_cron_job_id = fields.Many2one("ir.cron", string="Scheduled Action", readonly=True)

    _sql_constraints = [
        ('unique_cr_config_id', 'UNIQUE(cr_config_id)', 'This configuration is already used.')
    ]

    @api.depends('cr_model_id')
    def _compute_cr_model_name(self):
        for rec in self:
            rec.cr_model_name = rec.cr_model_id.model if rec.cr_model_id else False

    @api.depends('cr_model_id')
    def _compute_available_fields(self):
        for record in self:
            if record.cr_model_id:
                fields_domain = [('model', '=', record.cr_model_id.model), ('store', '=', True)]
                record.available_field_ids = self.env['ir.model.fields'].search(fields_domain)
            else:
                record.available_field_ids = self.env['ir.model.fields'].search([('store', '=', True)])

    @api.constrains('cr_model_columns')
    def _check_stored_fields(self):
        """Ensure all selected fields are stored."""
        for record in self:
            if record.cr_model_columns:
                non_stored_fields = record.cr_model_columns.filtered(lambda f: not f.store)
                if non_stored_fields:
                    raise ValidationError(
                        _("The following fields are not stored and cannot be exported: %s") %
                        ", ".join(non_stored_fields.mapped('name'))
                    )

    def _get_bigquery_client(self, config):
        """Initialize BigQuery client with credentials from config."""
        try:
            credentials_info = json.loads(config.cr_credentials_json)
            credentials = Credentials.from_service_account_info(credentials_info)
            client = bigquery.Client(credentials=credentials, project=config.cr_project_id)
            return client
        except Exception as e:
            raise ValidationError(_("Failed to initialize BigQuery client: %s") % str(e))

    def action_export_data(self, id):

        record = self.env['cr.big.query.export'].search([('id', '=', id)])
        if not record:
            return

        for model_record in record.cr_export_model_ids:
            config = record.cr_config_id
            client = self._get_bigquery_client(config)

            model_name = model_record.model
            table_name = model_name.replace('.', '_')

            model = self.env[model_name]
            table = model._table

            model_fields = self.env['ir.model.fields'].search([
                ('model', '=', model_name), ('store', '=', True)
            ])

            self.env.cr.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = %s
            """, [table])
            real_columns = {row[0] for row in self.env.cr.fetchall()}
            query_fields = [f.name for f in model_fields if f.name in real_columns]

            field_names = query_fields
            if 'id' not in field_names:
                field_names.insert(0, 'id')

            where_clauses = []
            params = []

            where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
            query = f"SELECT {', '.join(query_fields)} FROM {table} WHERE {where_clause}"

            schema = []
            for field_name in query_fields:
                field = next((f for f in model_fields if f.name == field_name), None)
                bq_type = "STRING"
                if field:
                    bq_type = {
                        'integer': "INTEGER",
                        'float': "FLOAT",
                        'boolean': "BOOLEAN",
                        'datetime': "TIMESTAMP",
                        'date': "DATE"
                    }.get(field.ttype, "STRING")
                schema.append(bigquery.SchemaField(field_name, bq_type))

            table_id = f"{config.cr_project_id}.{config.cr_dataset_id}.{table_name}"
            try:
                client.get_table(table_id)
            except Exception as e:
                client.create_table(bigquery.Table(table_id, schema=schema))

            batch_size = 100000
            offset = 0
            total_rows = 0

            job_config = bigquery.LoadJobConfig(
                schema=schema,
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            )

            while True:
                batch_query = f"{query} LIMIT {batch_size} OFFSET {offset}"

                self.env.cr.execute(batch_query, params)
                rows = self.env.cr.dictfetchall()

                if not rows:
                    break

                if rows:
                    total_rows += len(rows)

                    temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', newline='', encoding='utf-8')
                    writer = csv.DictWriter(temp_file, fieldnames=field_names, extrasaction='ignore')
                    writer.writeheader()
                    for row in rows:
                        for k, v in row.items():
                            if isinstance(v, datetime):
                                row[k] = v.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                            elif isinstance(v, date):
                                row[k] = v.isoformat()
                            elif v is None:
                                row[k] = ''
                        writer.writerow(row)
                    temp_file.close()

                    with open(temp_file.name, "rb") as source_file:

                        job = client.load_table_from_file(source_file, table_id, job_config=job_config)
                        job.result()
                    os.remove(temp_file.name)

                offset += batch_size

            if total_rows == 0:
                raise ValidationError("No new or updated records to export.")
            else:
                message = f"✅ Export complete. {total_rows} rows uploaded to BigQuery."

    def action_import_data(self, id):
        """Import data from BigQuery to the selected Odoo model."""
        record = self.env['cr.big.query.export'].search([('id', '=', id)])
        for model in record.cr_import_model_ids:
            config = record.cr_config_id
            client = self._get_bigquery_client(config)

            project_id = config.cr_project_id
            dataset_id = config.cr_dataset_id
            model_name = model.model

            table_id = f"{project_id}.{dataset_id}.{model_name.replace('.', '_')}"
            if not self.env['cr.big.query.scheduler']._check_table_exists(client, table_id):
                raise UserError(_("The selected table '%s' does not exist in BigQuery.") % model_name)

            model_fields = self.env['ir.model.fields'].search([
                ('model', '=', model_name), ('store', '=', True)
            ])

            model = self.env[model_name]
            table = model._table
            self.env.cr.execute("""
                                        SELECT column_name FROM information_schema.columns 
                                        WHERE table_name = %s
                                    """, [table])
            real_columns = {row[0] for row in self.env.cr.fetchall()}
            query_fields = [f.name for f in model_fields if f.name in real_columns]
            field_names = set(query_fields)

            field_names.add('id')

            # Build SELECT clause
            select_clause = ', '.join([f"`{name}`" for name in field_names])

            # Build full query
            query = f"SELECT {select_clause} FROM `{table_id}`"

            query_job = client.query(query)
            rows = query_job.result()

            imported_records = []
            updated_records = []
            unique_identifier = 'id'

            for row in rows:
                record_data = {}
                record_id = row.get(unique_identifier)
                rec_id = record_id
                if record_id is None:
                    continue
                else:
                    try:
                        record_id = int(record_id)
                    except ValueError:
                        continue

                    existing_record = self.env[model_name].search([(unique_identifier, '=', record_id)], limit=1)

                    for field_name in query_fields:
                        field = next((f for f in model_fields if f.name == field_name), None)
                        if not field:
                            continue

                        field_value = row.get(field_name)

                        if self.env['cr.big.query.scheduler']._is_value_valid(field_value):
                            if field.ttype == 'many2one':
                                record_id = field_value[0] if isinstance(field_value, tuple) and len(
                                    field_value) > 0 else None
                                record_data[field_name] = record_id if isinstance(record_id, int) else 1

                            elif field.ttype == 'many2many':
                                if isinstance(field_value, list):
                                    valid_ids = [v for v in field_value if isinstance(v, int)]
                                    if valid_ids:
                                        record_data[field_name] = [(6, 0, valid_ids)]

                            elif field.ttype == 'date':
                                try:
                                    record_data[field_name] = fields.Date.from_string(field_value)
                                except ValueError:
                                    record_data[field_name] = None


                            elif field.ttype == 'datetime':

                                try:

                                    dt_value = fields.Datetime.from_string(field_value) if isinstance(field_value,
                                                                                                      str) else field_value

                                    if dt_value and dt_value.tzinfo is not None:
                                        dt_value = dt_value.replace(tzinfo=None)

                                    record_data[field_name] = dt_value

                                except ValueError:

                                    record_data[field_name] = None


                            elif field.ttype == 'float':
                                record_data[field_name] = float(field_value)

                            elif field.ttype == 'integer':
                                record_data[field_name] = int(field_value)

                            elif field.ttype == 'boolean':
                                record_data[field_name] = bool(field_value)

                            elif field.ttype in ['char', 'text']:
                                record_data[field_name] = field_value

                            elif field.ttype == 'binary':
                                if field_value:
                                    try:

                                        if isinstance(field_value, str):

                                            field_value += '=' * (-len(field_value) % 4)

                                            decoded_value = base64.b64decode(field_value, validate=True)
                                            record_data[field_name] = base64.b64encode(decoded_value).decode('utf-8')
                                        elif isinstance(field_value, bytes):

                                            record_data[field_name] = base64.b64encode(field_value).decode('utf-8')
                                        else:
                                            raise ValueError("Invalid binary data type.")
                                    except (binascii.Error, ValueError) as e:
                                        record_data[field_name] = b''
                                else:
                                    record_data[field_name] = b''

                            elif field.ttype == 'monetary':
                                record_data[field_name] = float(field_value) if field_value else 0.0

                            elif field.ttype == 'html':
                                record_data[field_name] = field_value

                            elif field.ttype == 'one2many':
                                record_data[field_name] = [(6, 0, record_id) for record_id in field_value if
                                                           isinstance(record_id, int)]

                    account_code = record_data.get('code')
                    if account_code:
                        existing_account = self.env[model_name].search([
                            ('code', '=', account_code),
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)

                        if existing_account and existing_account.id != existing_record.id:
                            continue

                    if existing_record:
                        existing_record.write(record_data)
                        updated_records.append(rec_id)

                    else:
                        imported_records.append(record_data)

            if imported_records:
                self.env[model_name].create(imported_records)

    def run_export_manually(self):
        self.action_export_data(self.id)

    def run_import_manually(self):
        self.action_import_data(self.id)

    def action_create_scheduler(self):
        for rec in self:
            vals = {
                'name': f"BigQuery Export Scheduler - {self.cr_name}",
                'model_id': self.env.ref('cr_bigquery_connector.model_cr_big_query_export').id,
                'state': 'code',
                'code': f"model.action_export_data({self.id})",
                'interval_number': self.cr_export_cron_value_,
                'interval_type': self.cr_export_scheduled_units_,

                'active': True,
            }

            cron = self.env['ir.cron'].sudo().create(vals)
            rec.cr_export_cron_job_id = cron.id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Create Scheduler",
                "message": 'Export Scheduler Action Created Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_update_scheduler(self):
        for rec in self:
            if not rec.cr_export_cron_job_id:
                raise ValidationError(_("No existing scheduler to edit. Please create one first."))
            vals = {
                'interval_number': self.cr_export_cron_value_,
                'interval_type': self.cr_export_scheduled_units_,
            }
            rec.cr_export_cron_job_id.sudo().write(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Update Scheduler",
                "message": 'Export Scheduler Action Updated Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_delete_scheduler(self):
        for rec in self:
            if rec.cr_export_cron_job_id:
                rec.cr_export_cron_job_id.sudo().unlink()
                rec.cr_export_cron_job_id = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Delete Scheduler",
                "message": 'Export Scheduler Action Deleted Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_i_create_scheduler(self):
        for rec in self:
            vals = {
                'name': f"BigQuery Import Scheduler - {self.cr_name}",
                'model_id': self.env.ref('cr_bigquery_connector.model_cr_big_query_export').id,
                'state': 'code',
                'code': f"model.action_import_data({self.id})",
                'interval_number': self.cr_import_cron_value_,
                'interval_type': self.cr_import_scheduled_units_,

                'active': True,
            }

            cron = self.env['ir.cron'].sudo().create(vals)
            rec.cr_import_cron_job_id = cron.id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Create Scheduler",
                "message": 'Import Scheduler Action Created Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_i_update_scheduler(self):
        for rec in self:
            if not rec.cr_import_cron_job_id:
                raise ValidationError(_("No existing scheduler to edit. Please create one first."))
            vals = {
                'interval_number': self.cr_import_cron_value_,
                'interval_type': self.cr_import_scheduled_units_,
            }
            rec.cr_import_cron_job_id.sudo().write(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Update Scheduler",
                "message": 'Import Scheduler Action Updated Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_i_delete_scheduler(self):
        for rec in self:
            if rec.cr_import_cron_job_id:
                rec.cr_import_cron_job_id.sudo().unlink()
                rec.cr_import_cron_job_id = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Delete Scheduler",
                "message": 'Import Scheduler Action Deleted Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }