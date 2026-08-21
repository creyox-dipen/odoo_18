# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api
import secrets
import logging
import json
import math
from datetime import datetime
import re
from psycopg2 import sql
import hashlib
import time
import csv
import io
import base64
import pandas as pd

_logger = logging.getLogger(__name__)

_model_columns_cache = {}
_batch_cache = {}
BATCH_CACHE_TTL = 300

# PostgreSQL OID type codes
INTEGER_OIDS = {20, 21, 23, 26}        # int8, int2, int4, oid
FLOAT_OIDS = {700, 701, 1700}           # float4, float8, numeric
TEXT_OIDS = {25, 1042, 1043, 2950}      # text, char, varchar, uuid
BOOL_OIDS = {16}                         # bool
DATE_OIDS = {1082}                       # date
DATETIME_OIDS = {1114, 1184}            # timestamp, timestamptz

# Odoo ttype -> Power BI type mapping
ODOO_TO_POWERBI_TYPE = {
    'integer':   'integer',
    'float':     'float',
    'monetary':  'float',
    'char':      'text',
    'text':      'text',
    'html':      'text',
    'selection': 'text',
    'boolean':   'boolean',
    'date':      'date',
    'datetime':  'datetime',
    'many2one':  'integer',
    'one2many':  'text',
    'many2many': 'text',
    'binary':    'text',
    'reference': 'text',
    'serialized':'text',
}


class Powerbi_Config(models.Model):
    _name = "cr.power.bi.configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "PowerBi Configuration"

    cr_connector_url = fields.Char(
        "Connector Url",
        default=lambda self: self.env["ir.config_parameter"]
        .sudo()
        .get_param("web.base.url"),
        required=True,
    )
    cr_access_token = fields.Char("Access Token")

    def generate_token(self):
        """Generate a new API token."""
        token = secrets.token_hex(16)
        self.env["ir.config_parameter"].sudo().set_param("access.token", token)
        self.cr_access_token = token
        return token


class PowerBIDataFetcher(models.Model):
    _name = "cr.power.bi.data.fetcher"
    _description = "Power BI Data Fetcher"

    BATCH_SIZE = 10000

    def _serialize_value(self, value):
        """Serialize value for Power BI with correct type handling."""
        # Must check bool BEFORE None/False since bool is subclass of int
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        # Odoo returns False for empty fields (not None), treat as None
        if value is False:
            return None
        if value in ("Null", "null"):
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore") if value else ""
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value), ensure_ascii=False)
        if isinstance(value, dict):
            return next(iter(value.values()), "") if value else ""
        try:
            return str(value).encode("utf-8").decode("utf-8") if value else ""
        except (TypeError, ValueError):
            return ""

    def _map_column_types(self, raw_types):
        """Map Odoo field types to Power BI compatible types."""
        return {
            col: ODOO_TO_POWERBI_TYPE.get(ttype, "text")
            for col, ttype in raw_types.items()
        }

    def _table_data_to_csv(self, table_data, column_names):
        """Convert table data to compressed CSV using pandas and encode as base64."""
        start_time = time.time()
        try:
            df = pd.DataFrame(table_data, columns=column_names).reset_index(drop=True)
            output_buffer = io.BytesIO()
            df.to_csv(
                output_buffer,
                index=False,
                header=False,
                compression="gzip",
                encoding="utf-8",
                quoting=csv.QUOTE_ALL,
            )
            compressed_data = output_buffer.getvalue()
            output_buffer.close()
            result = base64.b64encode(compressed_data).decode("utf-8")
            duration = time.time() - start_time
            return result
        except Exception as e:
            duration = time.time() - start_time
            raise ValueError(f"Failed to generate CSV: {str(e)}")

    def _log_data_processing(
        self,
        table_name,
        record_count,
        status,
        timespan,
        initiated_at,
        error_message="",
        batch_number=None,
    ):
        """Log data processing with reduced overhead."""
        start_time = time.time()
        try:
            if batch_number == 1 or status in ("done", "failure"):
                log_data = {
                    "table_name": table_name,
                    "record_count": record_count,
                    "status": status,
                    "error_message": error_message,
                    "timestamp": timespan,
                    "initiated_at": initiated_at,
                    "batch_number": batch_number,
                }
                self.with_context(active_test=False).env[
                    "cr.data.processing"
                ].sudo().create(log_data)
            duration = time.time() - start_time
        except Exception as e:
            duration = time.time() - start_time
            _logger.warning("Failed to log data processing: %s", str(e))

    def _get_concrete_children(self, abstract_model_name, cr):
        """Returns concrete children for abstract models."""
        start_time = time.time()
        try:
            concrete_models = []
            for model_name, model_class in self.env.items():
                if getattr(model_class, "_abstract", False) or getattr(
                    model_class, "_transient", False
                ):
                    continue
                if abstract_model_name in getattr(model_class, "_inherit", []):
                    concrete_models.append(model_name)
            duration = time.time() - start_time
            return concrete_models
        except Exception as e:
            duration = time.time() - start_time
            return []

    def _get_column_types_from_query(self, cr, query):
        """
        Infer Power BI compatible column types from query result description.
        Uses psycopg2 OID codes (integers) — NOT string type names.
        """
        start_time = time.time()
        try:
            cr.execute(query)
            column_types = {}
            for desc in cr.description:
                col_name = desc[0]
                col_oid = desc[1]   # psycopg2 returns integer OID, not a string
                if col_oid in INTEGER_OIDS:
                    column_types[col_name] = "integer"
                elif col_oid in FLOAT_OIDS:
                    column_types[col_name] = "float"
                elif col_oid in BOOL_OIDS:
                    column_types[col_name] = "boolean"
                elif col_oid in DATE_OIDS:
                    column_types[col_name] = "date"
                elif col_oid in DATETIME_OIDS:
                    column_types[col_name] = "datetime"
                else:
                    column_types[col_name] = "text"
            duration = time.time() - start_time
            return column_types
        except Exception as e:
            duration = time.time() - start_time
            return {}

    def fetch_query_data(self, query, batch_number=1):
        """Fetch data from SQL query using batch processing."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cleaned_query = query.rstrip(";").strip()
            batch_number = max(
                1, int(batch_number) if str(batch_number).isdigit() else 1
            )

            with self._cr as cr:
                count_start = time.time()
                count_query = f"SELECT COUNT(*) FROM ({cleaned_query}) AS subquery"
                try:
                    cr.execute(count_query)
                    total_records = cr.fetchone()[0]
                except Exception as e:
                    total_records = 0
                count_duration = time.time() - count_start

                total_batches = (
                    math.ceil(total_records / self.BATCH_SIZE)
                    if total_records > 0
                    else 1
                )
                limit = self.BATCH_SIZE
                offset = (batch_number - 1) * self.BATCH_SIZE
                batched_query = f"{cleaned_query} LIMIT {limit} OFFSET {offset}"

                fetch_start = time.time()
                cr.execute(batched_query)
                result = cr.fetchall()
                fetch_duration = time.time() - fetch_start

                column_names = [desc[0] for desc in cr.description]

                # Get Power BI compatible column types using OID mapping
                column_types = self._get_column_types_from_query(cr, batched_query)

                serialize_start = time.time()
                table_data = [
                    {
                        column_names[i]: self._serialize_value(row[i])
                        for i in range(len(column_names))
                    }
                    for row in result
                ]
                if not table_data:
                    table_data = [{col: "" for col in column_names}]
                serialize_duration = time.time() - serialize_start

                csv_data = self._table_data_to_csv(table_data, column_names)
                status = "done" if batch_number >= total_batches else "in_progress"
                record_count = len(table_data)

                self._log_data_processing(
                    table_name="SQL Query",
                    record_count=record_count,
                    status="success",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    batch_number=batch_number,
                )

                method_duration = time.time() - method_start_time

                return {
                    "csvData": csv_data,
                    "columnNames": column_names,
                    "columnTypes": column_types,
                    "batch_number": batch_number,
                    "total_batches": total_batches,
                    "status": status,
                    "record_count": record_count,
                }

        except Exception as e:
            method_duration = time.time() - method_start_time
            self._log_data_processing(
                table_name="SQL Query",
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message=str(e),
                batch_number=batch_number,
            )
            return {
                "error": f"An error occurred: {str(e)}",
                "status": "failure",
                "record_count": 0,
                "batch_number": batch_number,
                "total_batches": 1,
            }

    def fetch_table_data(self, table_name, batch_number=1, search_query=None):
        """Fetch table data using batch processing and direct SQL queries."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            batch_number = max(
                1, int(batch_number) if str(batch_number).isdigit() else 1
            )

            fetch_model_start = time.time()
            result = (
                self.env["ir.model"].sudo().search([("name", "=", table_name)], limit=1)
            )
            fetch_model_duration = time.time() - fetch_model_start

            if not result:
                self._log_data_processing(
                    table_name=table_name,
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message=f"Model not found for table name: {table_name}",
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return {
                    "error": f"Model not found for table name: {table_name}",
                    "status": "failure",
                    "record_count": 0,
                    "batch_number": batch_number,
                    "total_batches": 1,
                }

            model_name = result.model
            model_class = self.env[model_name]
            if getattr(model_class, "_abstract", False):
                result = self._fetch_abstract_model_data(model_name, batch_number)
            else:
                result = self._fetch_regular_model_data(
                    model_name, batch_number, search_query
                )

            method_duration = time.time() - method_start_time
            return result

        except Exception as e:
            method_duration = time.time() - method_start_time
            self._log_data_processing(
                table_name=table_name,
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message=str(e),
                batch_number=batch_number,
            )
            return {
                "error": f"An error occurred: {str(e)}",
                "status": "failure",
                "record_count": 0,
                "batch_number": batch_number,
                "total_batches": 1,
            }

    def _fetch_abstract_model_data(self, model_name, batch_number):
        """Fetch data for abstract model using batch processing."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.env.cr as cr:

            concrete_models = self._get_concrete_children(model_name, cr)
            if not concrete_models:
                self._log_data_processing(
                    table_name=model_name,
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message=f"No concrete models found for abstract model '{model_name}'",
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return {
                    "error": f"No concrete models found for abstract model '{model_name}'",
                    "status": "failure",
                    "record_count": 0,
                    "batch_number": batch_number,
                    "total_batches": 1,
                }

            fetch_fields_start = time.time()
            model_names_str = ",".join(f"'{m}'" for m in concrete_models)
            cr.execute(
                """
                SELECT f.model, f.name, f.ttype
                FROM ir_model_fields f
                WHERE f.model IN (%s)
                """
                % model_names_str
            )
            field_data = cr.fetchall()
            fetch_fields_duration = time.time() - fetch_fields_start

            # Store raw Odoo types then map to Power BI types
            raw_column_types = {row[1]: row[2] for row in field_data}
            column_types = self._map_column_types(raw_column_types)
            all_column_names = list(set(row[1] for row in field_data))

            fetch_columns_start = time.time()
            table_names_str = ",".join(
                f"'{m.replace('.', '_')}'" for m in concrete_models
            )
            cr.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_name IN (%s)
                """
                % table_names_str
            )
            valid_columns = {row[1] for row in cr.fetchall()}
            column_names = list(
                filter(lambda col: col in valid_columns, all_column_names)
            )
            fetch_columns_duration = time.time() - fetch_columns_start

            if not column_names:
                self._log_data_processing(
                    table_name=model_name,
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="No valid columns found for the abstract model",
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return {
                    "error": "No valid columns found for the abstract model",
                    "status": "failure",
                    "record_count": 0,
                    "batch_number": batch_number,
                    "total_batches": 1,
                }

            count_start = time.time()
            total_records = 0
            for table_name_db in [m.replace(".", "_") for m in concrete_models]:
                cr.execute(f"SELECT COUNT(*) FROM {table_name_db}")
                total_records += cr.fetchone()[0]
            count_duration = time.time() - count_start

            total_batches = (
                math.ceil(total_records / self.BATCH_SIZE) if total_records > 0 else 1
            )

            table_data = []
            limit = self.BATCH_SIZE // len(concrete_models)
            offset = (batch_number - 1) * self.BATCH_SIZE

            fetch_data_start = time.time()
            for concrete_model in concrete_models:
                table_name_db = concrete_model.replace(".", "_")
                columns = ", ".join(column_names)
                query = f"""
                    SELECT {columns}
                    FROM {table_name_db}
                    ORDER BY id
                    LIMIT {limit} OFFSET {offset}
                """
                cr.execute(query)
                result = cr.fetchall()

                formatted_result = [
                    {
                        column_names[i]: self._serialize_value(row[i])
                        for i in range(len(column_names))
                    }
                    for row in result
                ]
                table_data.extend(formatted_result)
            fetch_data_duration = time.time() - fetch_data_start

            if not table_data:
                table_data = [{col: "" for col in column_names}]

            csv_data = self._table_data_to_csv(table_data, column_names)
            status = "done" if batch_number >= total_batches else "in_progress"
            record_count = len(table_data)

            self._log_data_processing(
                table_name=model_name,
                record_count=record_count,
                status="success",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                batch_number=batch_number,
            )

            method_duration = time.time() - method_start_time

            return {
                "csvData": csv_data,
                "columnNames": column_names,
                "columnTypes": column_types,
                "batch_number": batch_number,
                "total_batches": total_batches,
                "status": status,
                "record_count": record_count,
            }

    def _fetch_regular_model_data(self, model_name, batch_number, search_query=None):
        """Fetch data for regular (non-abstract) model using batch processing."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        batch_number = max(1, int(batch_number) if str(batch_number).isdigit() else 1)

        cache_key = hashlib.md5(
            f"{model_name}_{batch_number}_{search_query or ''}".encode()
        ).hexdigest()
        current_time = time.time()

        if cache_key in _batch_cache:
            cached_result, timestamp = _batch_cache[cache_key]
            if current_time - timestamp < BATCH_CACHE_TTL:
                method_duration = time.time() - method_start_time
                return cached_result

        cr = self.env.cr
        column_cache_key = model_name

        if column_cache_key not in _model_columns_cache:
            fetch_columns_start = time.time()
            cr.execute(
                """
                SELECT name, ttype
                FROM ir_model_fields
                WHERE model = %s
            """,
                (model_name,),
            )
            model_fields = cr.fetchall()
            table_name_db = model_name.replace(".", "_")
            cr.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (table_name_db,),
            )
            valid_columns = set(row[0] for row in cr.fetchall())
            column_info = [(field[0], field[1]) for field in model_fields]

            # Store raw Odoo types then map to Power BI types
            raw_column_types = dict(column_info)
            column_types = self._map_column_types(raw_column_types)
            column_names = [name for name, _ in column_info if name in valid_columns]

            _model_columns_cache[column_cache_key] = (column_names, column_types)
            fetch_columns_duration = time.time() - fetch_columns_start
        else:
            column_names, column_types = _model_columns_cache[column_cache_key]

        if not column_names:
            result = {
                "error": "No valid columns found for the table",
                "status": "failure",
                "record_count": 0,
                "batch_number": batch_number,
                "total_batches": 1,
            }
            self._log_data_processing(
                table_name=model_name,
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message="No valid columns found for the table",
                batch_number=batch_number,
            )
            method_duration = time.time() - method_start_time
            _batch_cache[cache_key] = (result, current_time)
            return result

        limit = self.BATCH_SIZE
        table_name_db = model_name.replace(".", "_")
        columns_sql = sql.SQL(", ").join(map(sql.Identifier, column_names))

        last_id_start = time.time()
        last_id = 0
        if batch_number > 1:
            cr.execute(
                sql.SQL("SELECT id FROM {} ORDER BY id LIMIT 1 OFFSET %s").format(
                    sql.Identifier(table_name_db)
                ),
                [(batch_number - 1) * limit],
            )
            last_id = cr.fetchone()[0] if cr.rowcount > 0 else 0
        last_id_duration = time.time() - last_id_start

        where_clause = sql.SQL("WHERE id > %s")
        params = [last_id]
        if search_query:
            search_conditions = [
                sql.SQL("CAST({} AS TEXT) ILIKE %s").format(sql.Identifier(col))
                for col in column_names
            ]
            search_clause = sql.SQL(" AND ({})").format(
                sql.SQL(" OR ").join(search_conditions)
            )
            where_clause = sql.SQL("{} {}").format(where_clause, search_clause)
            params.extend([f"%{search_query}%"] * len(column_names))

        count_start = time.time()
        cr.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name_db))
        )
        total_records = cr.fetchone()[0]
        count_duration = time.time() - count_start

        total_batches = (
            math.ceil(total_records / self.BATCH_SIZE) if total_records > 0 else 1
        )

        fetch_start = time.time()
        query = sql.SQL(
            """
            SELECT {}
            FROM {}
            {}
            ORDER BY id
            LIMIT %s
        """
        ).format(columns_sql, sql.Identifier(table_name_db), where_clause)
        cr.execute(query, params + [limit])
        rows = cr.fetchall()
        fetch_duration = time.time() - fetch_start

        serialize_start = time.time()
        table_data = (
            [
                {
                    column_names[i]: self._serialize_value(row[i])
                    for i in range(len(column_names))
                }
                for row in rows
            ]
            if rows
            else [{col: "" for col in column_names}]
        )

        # Fallback to ORM if SQL returns nothing
        if not table_data or table_data == [{col: "" for col in column_names}]:
            offset = (batch_number - 1) * limit
            records = (
                self.env[model_name]
                .sudo()
                .search([], limit=self.BATCH_SIZE, offset=offset)
            )
            orm_data = []
            for record in records:
                try:
                    record_data = record.read(column_names)[0]
                    serialized_data = {
                        k: self._serialize_value(v) for k, v in record_data.items()
                    }
                    orm_data.append(serialized_data)
                except Exception:
                    continue
            if orm_data:
                table_data = orm_data

        if not table_data:
            table_data = [{col: None for col in column_names}]

        serialize_duration = time.time() - serialize_start

        csv_data = self._table_data_to_csv(table_data, column_names)
        status = "done" if batch_number >= total_batches else "in_progress"
        record_count = len(table_data)

        self._log_data_processing(
            table_name=model_name,
            record_count=record_count,
            status="success",
            timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            initiated_at=initiated_at,
            batch_number=batch_number,
        )

        result = {
            "csvData": csv_data,
            "columnNames": column_names,
            "columnTypes": column_types,
            "batch_number": batch_number,
            "total_batches": total_batches,
            "status": status,
            "record_count": record_count,
        }

        _batch_cache[cache_key] = (result, current_time)

        # Clean expired cache entries
        expired_keys = [
            k
            for k, (_, t) in _batch_cache.items()
            if current_time - t >= BATCH_CACHE_TTL
        ]
        for k in expired_keys:
            del _batch_cache[k]

        method_duration = time.time() - method_start_time
        return result