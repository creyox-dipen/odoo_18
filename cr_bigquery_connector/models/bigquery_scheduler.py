# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import base64
import binascii
import csv
import os
import tempfile
from datetime import datetime, date
from odoo import models, fields, api, _
from google.oauth2.service_account import Credentials
from google.cloud import bigquery
import json
from odoo.exceptions import ValidationError
import hashlib


class BigQueryScheduler(models.Model):
    _name = 'cr.big.query.scheduler'
    _rec_name = 'cr_name'
    _description = 'BigQuery scheduler'

    cr_name = fields.Char('Name', required=True)
    cr_operation = fields.Selection(
        selection=[
            ('import', 'Import Data'),
            ('export', 'Export Data'),
        ],
        string='Operation',
        default='import',
        required=True, copy=False
    )
    cr_export_cron_value_ = fields.Integer(string='Schedule Export time', readonly=False, store=True)
    cr_export_scheduled_units_ = fields.Selection(
        [('hours', 'Hours'), ('minutes', 'Minute'), ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
        string="Export Cron Units", default="hours", readonly=False, store=True)
    cr_export_model_id = fields.Many2one('ir.model', string='Model To Export',
                                         readonly=False, store=True)
    cr_import_cron_value_ = fields.Integer(string='Schedule Import time', readonly=False, store=True)
    cr_import_scheduled_units_ = fields.Selection(
        [('hours', 'Hours'), ('minutes', 'Minute'), ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')],
        string="Import Cron Units", default="hours", readonly=False, store=True)
    cr_import_model_id = fields.Many2one('ir.model', string='Models To Import',
                                         readonly=False, store=True)
    cr_mailing_domain = fields.Char(
        string='Filter Domain',
        default='[]',
        help="Domain to filter records for the export"
    )
    cr_model_columns = fields.Many2many(
        'ir.model.fields',
        string='Model Columns',
        domain="[('id', 'in', available_field_ids), ('store', '=', True)]",
        help="Model field to auto-fill this parameter",
    )
    cr_cron_job_id = fields.Many2one("ir.cron", string="Scheduled Action", readonly=True)
    available_field_ids = fields.Many2many(
        'ir.model.fields',
        compute='_compute_available_fields',
        store=False,
    )
    cr_model_name = fields.Char(
        compute="_compute_cr_model_name",
        store=False
    )
    cr_config_id = fields.Many2one('cr.big.query.config', 'Configuration', required=True,
                                   ondelete='cascade', domain="[('status', '=', 'verified')]")

    @api.depends('cr_export_model_id', 'cr_import_model_id')
    def _compute_cr_model_name(self):
        for rec in self:
            rec.cr_model_name = rec.cr_export_model_id.model if rec.cr_export_model_id else rec.cr_import_model_id.model

    @api.depends('cr_export_model_id', 'cr_import_model_id')
    def _compute_available_fields(self):
        for record in self:
            if record.cr_export_model_id:
                fields_domain = [('model', '=', record.cr_export_model_id.model), ('store', '=', True)]
                record.available_field_ids = self.env['ir.model.fields'].search(fields_domain)
            elif record.cr_import_model_id:
                fields_domain = [('model', '=', record.cr_import_model_id.model), ('store', '=', True)]
                record.available_field_ids = self.env['ir.model.fields'].search(fields_domain)
            else:
                record.available_field_ids = self.env['ir.model.fields'].search([('store', '=', True)])

    def _get_scheduler_config(self):
        self.ensure_one()
        if self.cr_operation == 'import':
            interval = self.cr_import_cron_value_ or 1
            interval_type = self.cr_import_scheduled_units_ or "minutes"
        else:
            interval = self.cr_export_cron_value_ or 1
            interval_type = self.cr_export_scheduled_units_ or "minutes"

        vals = {
            'name': f"BigQuery {self.cr_operation.capitalize()} - {self.cr_name}",
            'model_id': self.env.ref('cr_bigquery_connector.model_cr_big_query_scheduler').id,
            'state': 'code',
            'code': f"model.execute_scheduler({self.id})",
            'interval_number': interval,
            'interval_type': interval_type,

            'active': True,
        }
        return vals

    def action_create_scheduler(self):
        for rec in self:
            vals = rec._get_scheduler_config()

            cron = self.env['ir.cron'].sudo().create(vals)
            rec.cr_cron_job_id = cron.id
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Create Scheduler",
                "message": 'Scheduler Action Created Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def action_edit_scheduler(self):
        for rec in self:
            if not rec.cr_cron_job_id:
                raise ValidationError(_("No existing scheduler to edit. Please create one first."))
            vals = rec._get_scheduler_config()
            rec.cr_cron_job_id.sudo().write(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Update Scheduler",
                "message": 'Scheduler Action Updated Successfully!!!',
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
            if rec.cr_cron_job_id:
                rec.cr_cron_job_id.sudo().unlink()
                rec.cr_cron_job_id = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Delete Scheduler",
                "message": 'Scheduler Action Deleted Successfully!!!',
                "type": 'success',
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            }
        }

    def execute_scheduler(self, id):
        record_id = self.env['cr.big.query.scheduler'].sudo().search([('id', '=', id)])
        operation_type = record_id.cr_operation
        config = record_id.cr_config_id
        if operation_type == 'import':
            self.import_records(record_id, config)
        else:
            self.export_records(record_id, config)

    def run_manually(self):
        record_id = self.env['cr.big.query.scheduler'].sudo().search([('id', '=', self.id)])
        operation_type = record_id.cr_operation
        config = record_id.cr_config_id
        if operation_type == 'import':
            sol = self.import_records(record_id, config)
            if sol:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'BigQuery Import',
                        'message': 'Successfully Imported Data from Bigquery ',
                        'sticky': False,
                        'type': 'success',
                    }
                }
        else:
            sol = self.export_records(record_id, config)
            if sol:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'BigQuery Export',
                        'message': 'Successfully Exported Data from Bigquery ',
                        'sticky': False,
                        'type': 'success',
                    }}

    def _get_bigquery_client(self, config):
        """Initialize BigQuery client with credentials from config."""
        credentials_info = json.loads(config.cr_credentials_json)
        credentials = Credentials.from_service_account_info(credentials_info)
        client = bigquery.Client(credentials=credentials, project=config.cr_project_id)
        return client

    def _check_table_exists(self, client, table_id):
        """Check if the specified table exists in BigQuery."""
        try:
            client.get_table(table_id)
            return True
        except Exception as e:
            return False

    def _is_value_valid(self, value):
        """Check if the value is valid (not None, False, empty string, or whitespace)."""
        return value not in [None, False, '', ' ', 'false', 'False', 'None']

    def import_records(self, record, config):

        client = self._get_bigquery_client(config)

        config = record.cr_config_id
        project_id = config.cr_project_id
        dataset_id = config.cr_dataset_id

        model_record = record.cr_import_model_id
        model_name = model_record.model

        table_id = f"{project_id}.{dataset_id}.{model_name.replace('.', '_')}"
        print(config)
        print(project_id)
        print(dataset_id)
        print(model_record)
        print(model_name)
        print(table_id)

        if not self._check_table_exists(client, table_id):
            raise ValidationError(_("The selected table '%s' does not exist in BigQuery.") % model_name)

        table = client.get_table(table_id)
        bigquery_fields = {schema_field.name for schema_field in table.schema}
        print(table)
        print(bigquery_fields)

        if record.cr_model_columns:
            selected_fields = set(record.cr_model_columns.mapped('name'))
        else:
            selected_fields = set(self.env[model_name]._fields.keys())

        field_names = selected_fields.intersection(bigquery_fields)
        print(field_names)
        if not field_names:
            raise ValidationError(
                _("No matching fields found between Odoo model '%s' and BigQuery table '%s'") % (
                    model_name, table_id)
            )

        if 'id' in bigquery_fields:
            field_names.add('id')

        invalid_fields = selected_fields - bigquery_fields
        print(invalid_fields)
        select_clause = ', '.join([f"`{name}`" for name in field_names])
        print(select_clause)

        domain = record.cr_mailing_domain.strip() if record.cr_mailing_domain else '[]'
        print("domain : ", domain)
        where_clause = ''

        if domain and domain != '[]':
            try:
                parsed_domain = eval(domain)

                where_clauses = []
                model_fields = self.env[model_name]._fields

                for condition in parsed_domain:
                    field, operator, value = condition

                    if field not in field_names:
                        continue
                    field_type = model_fields.get(field).type if model_fields.get(field) else 'char'

                    if value in [False, 'False', 'false', None, 'None', '']:
                        if operator == '=':
                            where_clauses.append(f"`{field}` IS NULL")
                        elif operator == '!=':
                            where_clauses.append(f"`{field}` IS NOT NULL")
                        else:
                            raise ValidationError(
                                _("Unsupported operator '%s' for NULL-like value on field '%s'") % (operator, field)
                            )
                        continue

                    if field_type in ['char', 'text', 'selection', 'html']:
                        value_str = f"'{str(value)}'"
                    elif field_type == 'boolean':
                        value_str = 'TRUE' if value in [True, 'True', 'true', 1, '1'] else 'FALSE'
                    elif field_type in ['integer', 'float', 'monetary']:
                        value_str = str(value)
                    elif field_type == 'date':
                        value_str = f"DATE('{value}')"
                    elif field_type == 'datetime':
                        value_str = f"TIMESTAMP('{value}')"
                    else:
                        value_str = f"'{str(value)}'"

                    where_clauses.append(f"`{field}` {operator} {value_str}")

                where_clause = 'WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''


            except Exception as e:

                raise ValidationError(_("Invalid domain format: %s") % str(e))

        query = f"SELECT {select_clause} FROM `{table_id}` {where_clause}"

        query_job = client.query(query)
        print(query_job)
        rows = query_job.result()
        print(rows)
        imported_records = []
        updated_records = []

        model_fields = self.env[model_name]._fields
        print(model_fields)
        unique_identifier = 'id'

        for row in rows:

            record_data = {}
            record_id = row.get(unique_identifier)
            rec_id = record_id

            if record_id is None:
                continue

            try:
                record_id = int(record_id)
            except ValueError:

                continue

            existing_record = self.env[model_name].search([(unique_identifier, '=', record_id)], limit=1)

            for field_name, field in model_fields.items():
                field_value = row.get(field_name)

                if self._is_value_valid(field_value):
                    try:
                        if field.type == 'many2one':
                            record_id = field_value[0] if isinstance(field_value, tuple) and len(
                                field_value) > 0 else None
                            record_data[field_name] = record_id if isinstance(record_id, int) else 1

                        elif field.type == 'many2many':
                            if isinstance(field_value, list):
                                valid_ids = [v for v in field_value if isinstance(v, int)]
                                if valid_ids:
                                    record_data[field_name] = [(6, 0, valid_ids)]

                        elif field.type == 'date':
                            record_data[field_name] = fields.Date.from_string(field_value)

                        elif field.type == 'datetime':
                            dt_value = fields.Datetime.from_string(field_value) if isinstance(field_value,
                                                                                              str) else field_value
                            if dt_value and dt_value.tzinfo is not None:
                                dt_value = dt_value.replace(tzinfo=None)
                            record_data[field_name] = dt_value

                        elif field.type == 'float':
                            record_data[field_name] = float(field_value)

                        elif field.type == 'integer':
                            record_data[field_name] = int(field_value)

                        elif field.type == 'boolean':
                            record_data[field_name] = bool(field_value)

                        elif field.type in ['char', 'text']:
                            record_data[field_name] = field_value

                        elif field.type == 'binary':
                            if field_value:
                                if isinstance(field_value, str):
                                    field_value += '=' * (-len(field_value) % 4)
                                    decoded_value = base64.b64decode(field_value, validate=True)
                                    record_data[field_name] = base64.b64encode(decoded_value).decode('utf-8')
                                elif isinstance(field_value, bytes):
                                    record_data[field_name] = base64.b64encode(field_value).decode('utf-8')
                            else:
                                record_data[field_name] = b''

                        elif field.type == 'monetary':
                            record_data[field_name] = float(field_value) if field_value else 0.0

                        elif field.type == 'html':
                            record_data[field_name] = field_value

                        elif field.type == 'one2many':
                            record_data[field_name] = [(6, 0, record_id) for record_id in field_value if
                                                       isinstance(record_id, int)]

                    except Exception as e:
                        print(f"[BQUERY IMPORT] Failed to process field {field_name}: {str(e)}")

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

        return True

    def export_records(self, record, config):
        client = self._get_bigquery_client(config)
        config = record.cr_config_id  # configuration
        model_name = record.cr_export_model_id.model
        table_name = model_name.replace('.', '_')
        model = self.env[model_name]
        table = model._table
        model_fields = record.cr_model_columns or self.env['ir.model.fields'].search([
            ('model', '=', model_name), ('store', '=', True)
        ])

        self.env.cr.execute(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = %s
                """, [table])

        real_columns = {row[0] for row in self.env.cr.fetchall()}
        query_fields = [f.name for f in model_fields if f.name in real_columns]

        field_names = query_fields
        if 'id' not in field_names:
            field_names.insert(0, 'id')

        print("config : ", config)
        print("model_name : ", model_name)
        print("table_name : ", table_name)
        print("model : ", model)
        print("table : ", table)
        print("model_fields : ", model_fields)
        print("real columns : ", real_columns)
        print("query fields : ", query_fields)
        print("field names : ", field_names)

        where_clauses = []
        params = []

        if record.cr_mailing_domain:
            try:
                domain = eval(record.cr_mailing_domain.strip())
                if not isinstance(domain, list):
                    raise ValidationError(_("Domain must evaluate to a list"))

                for condition in domain:
                    # process further only when if condition is valid
                    if isinstance(condition, (list, tuple)) and len(condition) == 3:
                        field, op, value = condition  # unpack values of condition  for ex : ('active', '=', True) → field = active, op = =, value = True
                        if field not in real_columns:
                            continue
                        # ('country_id', '=', False) → means no country selected
                        # SQL does not use = False for empty fields
                        # Empty fields = NULL, so proper SQL:
                        # Case: op '=' ⇒ field IS NULL
                        # Case: op '!=' ⇒ field IS NOT NULL
                        if value is False and op in ('=', '!='):

                            if op == '=':
                                where_clauses.append(f"{field} IS NULL")
                            else:
                                where_clauses.append(f"{field} IS NOT NULL")
                        else:
                            where_clauses.append(f"{field} {op} %s")
                            params.append(value)
            except Exception as e:
                raise ValidationError(_("Invalid domain format: %s") % str(e))
        table_exists = True
        table_id = f"{config.cr_project_id}.{config.cr_dataset_id}.{table_name}"
        try:
            client.get_table(table_id)
        except Exception:
            table_exists = False

        # join every conditions like state = %s AND amount_total > %s
        where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
        # build full select query with conditions
        query = f"SELECT {', '.join(query_fields)} FROM {table} WHERE {where_clause}"

        schema = []
        for field_name in query_fields:
            field = next((f for f in model_fields if f.name == field_name), None)
            bq_type = "STRING"  # consider default type is string if any other type
            if field:
                # select BigQuery supported type for field
                bq_type = {
                    'integer': "INTEGER",
                    'float': "FLOAT",
                    'boolean': "BOOLEAN",
                    'datetime': "TIMESTAMP",
                    'date': "DATE"
                }.get(field.ttype, "STRING")  # if type is not from above list then consider string as default

            # add the field definition into BigQuery schema
            # Each field becomes a SchemaField object like:
            # SchemaField("amount_total", "FLOAT")
            # SchemaField("state", "STRING")
            schema.append(bigquery.SchemaField(field_name, bq_type))

        # if table not exists create BQ table
        if table_exists == False:
            client.create_table(bigquery.Table(table_id, schema=schema))

        # Define how many rows to process per batch
        batch_size = 100000  # It will fetch/export records in chunks of 100,000 rows
        offset = 0  # Used for SQL pagination (LIMIT ... OFFSET ...)
        total_rows = 0  # Keeps track of how many records were exported overall.

        first_batch = True  # will control write disposition per batch

        while True:
            batch_query = f"{query} LIMIT {batch_size} OFFSET {offset}"

            self.env.cr.execute(batch_query, params)
            rows = self.env.cr.dictfetchall()

            if not rows:
                break

            total_rows += len(rows)

            # create a temp CSV for this batch
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
            # close before reopening for read (important on Windows)
            temp_file.close()

            # choose write disposition: truncate on first batch, append afterwards
            write_disp = bigquery.WriteDisposition.WRITE_TRUNCATE if first_batch else bigquery.WriteDisposition.WRITE_APPEND

            job_config = bigquery.LoadJobConfig(
                schema=schema,
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                write_disposition=write_disp
            )

            # upload this batch file to BigQuery
            with open(temp_file.name, "rb") as source_file:
                job = client.load_table_from_file(source_file, table_id, job_config=job_config)
                job.result()

            # remove temp file to free disk space
            try:
                os.remove(temp_file.name)
            except Exception:
                pass

            # after first successful upload, switch to append mode
            first_batch = False
            offset += batch_size

        # after loop, check result
        if total_rows == 0:
            raise ValidationError("No new or updated records to export.")
        else:
            return True