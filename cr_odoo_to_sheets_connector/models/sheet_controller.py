# -*- coding: utf-8 -*-
# Part of Creyox Technologies

import json
from datetime import datetime
from odoo import models, fields, api, _
from odoo import http
from odoo.http import request, Response


class OdooDataController(http.Controller):

    @http.route('/ht', auth='public', type='http', methods=['GET'])
    def fetch_data(self):
        """Fetches the list of available models and returns them as a JSON response."""
        start_time = datetime.now()
        initiated_at = start_time
        try:  
            model_records = request.env['ir.model'].sudo().search([])
            result = {model.model: model.name for model in model_records}
            end_time = datetime.now()
            duration = end_time - start_time
            record_count = len(model_records)
            self._log_data_processing('All the Table', record_count, 'success', duration, initiated_at)
            return Response(json.dumps(result), content_type='application/json', status=200)
        except Exception as e:
            end_time = datetime.now()
            duration = end_time - start_time
            self._log_data_processing('All the Table', 0, 'failure', duration, initiated_at, str(e))
            return Response(json.dumps({'error': str(e)}), content_type='application/json', status=500)

    @http.route('/get_table/<string:table>', auth='public', type='http', csrf=False, methods=['POST'])
    def fetch_table_data(self, table):
        """Fetches the data of models and returns them as a response."""
        start_time = datetime.now()
        initiated_at = start_time   
        tables = table.split(',')
        if not tables:
            return Response(json.dumps({"error": "No tables provided"}), status=400)

        all_data = []

        for table in tables:
            try:
                Model = request.env[table].sudo()
                records = Model.search([])
                record_count = len(records)
                data = []
                for record in records:
                    record_data = record.read()[0]

                    for key, value in record_data.items():
                        if isinstance(value, bytes):
                            record_data[key] = value.decode('utf-8')
                        elif isinstance(value, (datetime, fields.Datetime)):
                            record_data[key] = value.isoformat()
                        elif isinstance(value, fields.Date):
                            record_data[key] = value.strftime('%Y-%m-%d')
                        elif isinstance(value, list):
                            record_data[key] = ','.join(map(str, value)) if value else None
                        else:
                            record_data[key] = str(value)

                    data.append(record_data)

                all_data.extend(data)
                end_time = datetime.now()
                duration = end_time - start_time
                self._log_data_processing(table, record_count, 'success', duration, initiated_at)

            except Exception as e:
                end_time = datetime.now()
                duration = end_time - start_time
                self._log_data_processing(table, 0, 'failure', duration, initiated_at, str(e))
                return Response(json.dumps({"error": f"Failed to process table '{table}': {str(e)}"}), status=400)

        return Response(json.dumps(all_data), status=200)

    @http.route('/send_data', auth='public', type='json', csrf=False, methods=['POST'])
    def fetch_table_odoo_data(self, **params):
        data = json.loads(request.httprequest.data.decode('utf-8'))
        start_time = datetime.now()
        initiated_at = start_time   

        if not data or 'table' not in data or 'data' not in data:
            return {"error": "Missing table or data in the request."}, 400

        table = data.get('table')
        records_data = data.get('data')
        model = request.env.get(table)
        record_count = len(records_data) - 1

        headers = records_data[0]
        for row in records_data[1:]:
            record_data = {headers[i]: value for i, value in enumerate(row)}
            processed_data = self._prepare_data(record_data, model)
            record_id = int(processed_data.get('id')) if processed_data.get('id') else None

            try:
                existing_record = model.sudo().search([('id', '=', record_id)], limit=1)
                if existing_record:
                    existing_record.sudo().write(processed_data)
                else:
                    model.sudo().create(processed_data)

                end_time = datetime.now()
                duration = end_time - start_time
                self._log_data_processing(table, record_count, 'success', duration, initiated_at)

            except Exception as e:
                end_time = datetime.now()
                duration = end_time - start_time
                self._log_data_processing(table, 0, 'failure', duration, initiated_at, str(e))
                return {"error": f"Error processing record with ID {record_id}: {str(e)}"}, 500

        return {"message": "Data written successfully"}, 200

    def _process_record(self, record_data):
        """Processes individual record data by converting field types to appropriate formats."""
        for key, value in record_data.items():
            if isinstance(value, bytes):
                record_data[key] = value.decode('utf-8')
            elif isinstance(value, (datetime, fields.Datetime)):
                record_data[key] = value.isoformat()
            elif isinstance(value, fields.Date):
                record_data[key] = value.strftime('%Y-%m-%d')
            elif isinstance(value, list):
                record_data[key] = ','.join(map(str, value)) if value else None
            else:
                record_data[key] = str(value)
        return record_data

    def _prepare_data(self, record_data, model):
        """Prepares record data by converting field values to appropriate types based on model fields."""
        for field_name, field_value in record_data.items():
            field = model._fields.get(field_name)
            if not field:
                continue

            if field.type == 'many2one':
                record_data[field_name] = self._prepare_many2one(field_value)
            elif field.type == 'many2many':
                record_data[field_name] = self._prepare_many2many(field_value)
            elif field.type == 'one2many':
                record_data[field_name] = self._prepare_one2many(field_value)
            elif field.type in ['date', 'datetime']:
                record_data[field_name] = self._prepare_date(field_value)
            elif field.type == 'float':
                record_data[field_name] = float(field_value) if field_value else 0.0
            elif field.type == 'integer':
                record_data[field_name] = int(field_value) if field_value else 0
            elif field.type == 'boolean':
                record_data[field_name] = bool(field_value)
            elif field.type in ['char', 'text', 'html']:
                record_data[field_name] = str(field_value)
            elif field.type == 'binary':
                record_data[field_name] = field_value or b''
            elif field.type == 'monetary':
                record_data[field_name] = float(field_value) if field_value else 0.0
            elif field.type == 'selection':
                record_data[field_name] = field_value if field_value else None

        return record_data

    def _prepare_many2one(self, value):
        """Prepares a Many2one field value for insertion."""
        # value format : (11, 'Gemini Furniture') : 11 is id of related model, Gemini Furniture is display name of that model
        if isinstance(value, bool):
            return value
        elif ',' in value:
            try:
                return int(value.split(',')[0].strip())
            except ValueError:
                return 1
        elif isinstance(value, int):
            return value
        return None

    def _prepare_many2many(self, value):
        """Prepares a Many2many field value for insertion."""
        # Value format : 3,7,11, This record is linked to IDs 3, 7, and 11 in the related model.
        if isinstance(value, str):
            return [(6, 0, [int(v.strip()) for v in value.split(',') if v.strip().isdigit()])]
        elif isinstance(value, list):
            return [(6, 0, [v for v in value if isinstance(v, int)])]
        return [(6, 0, [])]

    def _prepare_one2many(self, value):
        """Prepares a One2many field value for insertion."""
        # value format same as many2many
        if isinstance(value, str):
            return [(6, 0, [int(v.strip()) for v in value.split(',') if v.strip().isdigit()])]
        elif isinstance(value, list):
            return [(6, 0, [v for v in value if isinstance(v, int)])]
        return [(6, 0, [])]

    def _prepare_date(self, value):
        """Prepares a date field value for insertion."""
        # Value Format : 2025-11-11T04:08:58.967Z
        if isinstance(value, str):
            value = value.rstrip('Z').replace('T', ' ')
            if '.' in value:
                value = value.split('.')[0]
            return fields.Datetime.from_string(value)
        else:
            return None

    def _log_data_processing(self, table_name, record_count, status, timespan, initiated_at, error_message=''):
        """Logs data processing operations into the DataProcessingLog model."""
        request.env['cr.data.processing.log'].sudo().create({
            'table_name': table_name,
            'record_count': record_count,
            'status': status,
            'error_message': error_message,
            'timestamp': timespan,
            'initiated_at': initiated_at,
        })
