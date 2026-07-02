# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import json
import logging
import time
import hashlib
from datetime import datetime
from psycopg2 import sql
from odoo import models, fields, api, _
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Global cache for column information
_model_columns_cache = {}
_batch_cache = {}
BATCH_CACHE_TTL = 5  # 5 seconds


class OdooDataController(http.Controller):

    def _get_config_or_error(self):
        """Get config record for token or return None, error_response."""
        token = request.httprequest.headers.get("X-Odoo-Access-Token")
        if not token:
            _logger.info("Access denied: Token missing")
            return None, Response(
                json.dumps({"error": "Unauthorized: Token missing"}),
                content_type="application/json",
                status=401,
            )

        config = request.env["cr.google.sheet.connector.config"].sudo().search(
            [("cr_access_token", "=", token.strip())], limit=1
        )
        if not config:
            _logger.info("Access denied: Invalid Token")
            return None, Response(
                json.dumps({"error": "Unauthorized: Invalid Token"}),
                content_type="application/json",
                status=401,
            )

        return config, None

    @http.route("/ht", auth="public", type="http", methods=["GET"])
    def fetch_data(self):
        """Fetches the list of available models and returns them as a JSON response."""
        config, error_resp = self._get_config_or_error()
        if error_resp:
            return error_resp

        start_time = datetime.now()
        method_start_time = time.time()

        try:
            model_records = request.env["ir.model"].sudo().search([])
            result = {model.model: model.name for model in model_records}

            end_time = datetime.now()
            duration = time.time() - method_start_time
            record_count = len(model_records)

            _logger.info(f"Fetched {record_count} models in {duration:.2f}s")

            # Log successful operation
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": "ir.model",
                        "operation_type": "fetch_models_list",
                        "record_count": record_count,
                        "success_count": record_count,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "success",
                        "message": f"Successfully fetched {record_count} models",
                        "timestamp": f"{duration:.2f}s",
                        "initiated_at": start_time,
                        "completed_at": end_time,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(
                json.dumps(result), content_type="application/json", status=200
            )

        except Exception as e:
            _logger.exception("Error fetching models list")

            end_time = datetime.now()
            duration = time.time() - method_start_time

            # Log failed operation
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": "ir.model",
                        "operation_type": "fetch_models_list",
                        "record_count": 0,
                        "success_count": 0,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "failure",
                        "error_message": str(e),
                        "timestamp": f"{duration:.2f}s",
                        "initiated_at": start_time,
                        "completed_at": end_time,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(
                json.dumps({"error": str(e)}),
                content_type="application/json",
                status=500,
            )

    @http.route(
        "/get_model_fields", auth="public", type="http", csrf=False, methods=["POST"]
    )
    def get_model_fields(self, **params):
        """Fetches the list of ACTUAL STORED fields that can be fetched from the database."""
        config, error_resp = self._get_config_or_error()
        if error_resp:
            return error_resp

        start_time = datetime.now()
        method_start_time = time.time()
        model_name = None

        try:
            _logger.info("=== get_model_fields endpoint called ===")

            data = json.loads(request.httprequest.data.decode("utf-8"))
            model_name = data.get("model")

            if not model_name:
                error_msg = "No model provided"

                # Log bad request
                try:
                    end_time = datetime.now()
                    duration = time.time() - method_start_time
                    request.env["cr.data.processing.log"].sudo().create(
                        {
                            "table_name": "Unknown",
                            "operation_type": "fetch_model_fields",
                            "record_count": 0,
                            "success_count": 0,
                            "failed_count": 0,
                            "partial_count": 0,
                            "status": "failure",
                            "error_message": error_msg,
                            "timestamp": f"{duration:.2f}s",
                            "initiated_at": start_time,
                            "completed_at": end_time,
                        }
                    )
                    request.env.cr.commit()
                except Exception as log_error:
                    _logger.error(f"Failed to create log entry: {str(log_error)}")

                return Response(
                    json.dumps({"error": error_msg}),
                    content_type="application/json",
                    status=400,
                )

            cr = request.env.cr
            table_name_db = model_name.replace(".", "_")

            # Get actual database columns
            cr.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """,
                (table_name_db,),
            )
            db_columns = set(row[0] for row in cr.fetchall())

            _logger.info(f"Found {len(db_columns)} database columns for {model_name}")

            # Get field metadata from Odoo
            cr.execute(
                """
                SELECT name, field_description, ttype, store
                FROM ir_model_fields
                WHERE model = %s AND store = true
            """,
                (model_name,),
            )

            formatted_fields = []

            for field_name, field_label, field_type, is_stored in cr.fetchall():
                # Only include fields that actually exist in the database
                if field_name in db_columns:
                    # Exclude binary fields
                    if field_type != "binary":

                        # Handle translation dictionary in field_label
                        label = field_label
                        if isinstance(label, dict):
                            # Try to get en_US, or fallback to first available value
                            label = label.get("en_US") or next(
                                iter(label.values()), field_name
                            )

                        formatted_fields.append(
                            {
                                "name": field_name,
                                "label": label or field_name,
                                "type": field_type,
                                "stored": True,
                            }
                        )

            # Sort by label for better UX
            formatted_fields.sort(key=lambda x: str(x["label"]))

            end_time = datetime.now()
            duration = time.time() - method_start_time
            field_count = len(formatted_fields)

            _logger.info(
                f"Returning {field_count} valid stored fields for {model_name}"
            )

            # Log successful operation
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": model_name,
                        "operation_type": "fetch_model_fields",
                        "record_count": field_count,
                        "success_count": field_count,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "success",
                        "message": f"Successfully fetched {field_count} fields for {model_name}",
                        "timestamp": f"{duration:.2f}s",
                        "initiated_at": start_time,
                        "completed_at": end_time,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(
                json.dumps(formatted_fields),
                content_type="application/json",
                status=200,
            )

        except Exception as e:
            _logger.exception(f"Error in get_model_fields")

            end_time = datetime.now()
            duration = time.time() - method_start_time

            # Log failed operation
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": model_name or "Unknown",
                        "operation_type": "fetch_model_fields",
                        "record_count": 0,
                        "success_count": 0,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "failure",
                        "error_message": str(e),
                        "timestamp": f"{duration:.2f}s",
                        "initiated_at": start_time,
                        "completed_at": end_time,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(
                json.dumps({"error": str(e)}),
                content_type="application/json",
                status=500,
            )

    @http.route(
        "/get_table/<string:table>",
        auth="public",
        type="http",
        csrf=False,
        methods=["POST"],
    )
    def fetch_table_data(self, table):
        """Optimized table data fetching with direct SQL queries and caching."""
        config, error_resp = self._get_config_or_error()
        if error_resp:
            return error_resp

        method_start_time = time.time()
        initiated_at = datetime.now()

        _logger.info("=" * 50)
        _logger.info(f"Fetch request received for table: {table}")

        try:
            # Parse request parameters
            req_data = json.loads(request.httprequest.data.decode("utf-8"))
            target_fields = req_data.get("fields", [])
            limit = req_data.get("limit", 10000)
            offset = req_data.get("offset", 0)

            _logger.info(
                f"Parameters - Fields: {target_fields if target_fields else 'ALL'}, "
                f"Limit: {limit}, Offset: {offset}"
            )
            if target_fields and "id" not in target_fields:
                target_fields = ["id"] + target_fields
            # Generate cache key
            cache_key = hashlib.md5(
                f"{table}_{offset}_{limit}_{','.join(sorted(target_fields or []))}".encode()
            ).hexdigest()

            current_time = time.time()

            # Check cache
            if cache_key in _batch_cache:
                cached_result, timestamp = _batch_cache[cache_key]
                if current_time - timestamp < BATCH_CACHE_TTL:
                    _logger.info(f"✓ Returning cached data")
                    method_duration = time.time() - method_start_time
                    _logger.info(f"✓ Total time: {method_duration:.2f}s (CACHED)")
                    return Response(
                        json.dumps(cached_result),
                        status=200,
                        content_type="application/json",
                    )

            # Fetch using optimized SQL
            result = self._fetch_optimized_data(
                table, target_fields, limit, offset, initiated_at, config.company_id.id
            )

            # Check if result is an error
            if isinstance(result, dict) and "error" in result:
                # Log failed export
                method_duration = time.time() - method_start_time
                completed_at = datetime.now()

                try:
                    request.env["cr.data.processing.log"].sudo().create(
                        {
                            "table_name": table,
                            "operation_type": "odoo_to_sheet",
                            "record_count": 0,
                            "success_count": 0,
                            "failed_count": 0,
                            "partial_count": 0,
                            "status": "failure",
                            "error_message": result.get("error", "Unknown error"),
                            "timestamp": f"{method_duration:.2f}s",
                            "initiated_at": initiated_at,
                            "completed_at": completed_at,
                        }
                    )
                    request.env.cr.commit()
                except Exception as log_error:
                    _logger.error(f"Failed to create log entry: {str(log_error)}")

                return Response(
                    json.dumps(result), status=500, content_type="application/json"
                )

            # Cache the result
            _batch_cache[cache_key] = (result, current_time)

            # Clean expired cache
            expired_keys = [
                k
                for k, (_, t) in _batch_cache.items()
                if current_time - t >= BATCH_CACHE_TTL
            ]
            for k in expired_keys:
                del _batch_cache[k]

            method_duration = time.time() - method_start_time
            completed_at = datetime.now()
            record_count = len(result) if isinstance(result, list) else 0

            _logger.info(f"✓ Total request time: {method_duration:.2f}s")
            _logger.info("=" * 50)

            # Log successful export
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": table,
                        "operation_type": "odoo_to_sheet",
                        "record_count": record_count,
                        "success_count": record_count,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "success",
                        "message": f"Successfully exported {record_count} records",
                        "timestamp": f"{method_duration:.2f}s",
                        "initiated_at": initiated_at,
                        "completed_at": completed_at,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(
                json.dumps(result), status=200, content_type="application/json"
            )

        except Exception as e:
            _logger.exception(f"Error in fetch_table_data")
            method_duration = time.time() - method_start_time
            completed_at = datetime.now()
            _logger.info(f"✗ Failed after {method_duration:.2f}s")

            # Log exception
            try:
                request.env["cr.data.processing.log"].sudo().create(
                    {
                        "table_name": table,
                        "operation_type": "odoo_to_sheet",
                        "record_count": 0,
                        "success_count": 0,
                        "failed_count": 0,
                        "partial_count": 0,
                        "status": "failure",
                        "error_message": str(e),
                        "timestamp": f"{method_duration:.2f}s",
                        "initiated_at": initiated_at,
                        "completed_at": completed_at,
                    }
                )
                request.env.cr.commit()
            except Exception as log_error:
                _logger.error(f"Failed to create log entry: {str(log_error)}")

            return Response(json.dumps({"error": str(e)}), status=500)

    def _fetch_optimized_data(self, table, target_fields, limit, offset, initiated_at, company_id=None):
        """Fetch data using direct SQL queries - ONLY uses fields that exist in DB."""
        start_time = time.time()
        cr = request.env.cr
        table_name_db = table.replace(".", "_")

        # Get column information (cached)
        column_cache_key = table
        if column_cache_key not in _model_columns_cache:
            columns_start = time.time()

            # Get actual database columns FIRST
            cr.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """,
                (table_name_db,),
            )
            db_columns = [row[0] for row in cr.fetchall()]

            # Get field types AND relational info from Odoo
            cr.execute(
                """
                SELECT name, ttype, relation
                FROM ir_model_fields
                WHERE model = %s AND name = ANY(%s)
            """,
                (table, db_columns),
            )

            column_types = {}
            relational_fields = {}  # Store relational field info

            for row in cr.fetchall():
                field_name, field_type, relation = row
                column_types[field_name] = field_type

                # Store relational field metadata
                if field_type in ("many2one", "many2many", "one2many") and relation:
                    relational_fields[field_name] = {
                        "type": field_type,
                        "relation": relation,
                    }

            # Only include columns that exist in BOTH database AND Odoo metadata
            valid_columns = [col for col in db_columns if col in column_types]

            has_company = "company_id" in db_columns
            _model_columns_cache[column_cache_key] = (
                valid_columns,
                column_types,
                relational_fields,
                has_company,
            )
            columns_duration = time.time() - columns_start
            _logger.info(
                f"  Column cache built in {columns_duration:.2f}s - {len(valid_columns)} valid columns"
            )
        else:
            valid_columns, column_types, relational_fields, has_company = _model_columns_cache[
                column_cache_key
            ]
            _logger.info(f"  Using cached column info - {len(valid_columns)} columns")

        # Determine which columns to fetch based on user selection
        if target_fields:
            column_names = [col for col in target_fields if col in valid_columns]

            if not column_names:
                _logger.warning(
                    f"  Requested fields {target_fields} not found in valid columns"
                )
                _logger.warning(f"  Available columns: {valid_columns[:10]}...")
                return {
                    "error": f"Requested fields not found. Please use /get_model_fields to get valid field names."
                }

            invalid_fields = [f for f in target_fields if f not in valid_columns]
            if invalid_fields:
                _logger.warning(f"  Skipping invalid fields: {invalid_fields}")
        else:
            column_names = valid_columns

        if not column_names:
            return {"error": "No valid columns found"}

        _logger.info(
            f"  Fetching {len(column_names)} columns: {column_names[:5]}{'...' if len(column_names) > 5 else ''}"
        )

        # Build and execute SQL query
        columns_sql = sql.SQL(", ").join(map(sql.Identifier, column_names))

        fetch_start = time.time()
        if has_company and company_id:
            _logger.info(
                f"  Filtering table {table} by company ID {company_id}"
            )
            query = sql.SQL(
                """
                SELECT {}
                FROM {}
                WHERE company_id = %s OR company_id IS NULL
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            ).format(columns_sql, sql.Identifier(table_name_db))
            cr.execute(query, [company_id, limit, offset])
        else:
            query = sql.SQL(
                """
                SELECT {}
                FROM {}
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            ).format(columns_sql, sql.Identifier(table_name_db))
            cr.execute(query, [limit, offset])

        rows = cr.fetchall()
        fetch_duration = time.time() - fetch_start
        _logger.info(f"  SQL fetch: {fetch_duration:.2f}s ({len(rows)} rows)")

        # Fetch relational field names
        relational_data = self._fetch_relational_names(
            column_names, relational_fields, rows, table
        )

        # Serialize data
        serialize_start = time.time()
        result_data = []
        for row_idx, row in enumerate(rows):
            record_dict = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                field_type = column_types.get(col_name)

                # Check if this is a relational field with fetched names
                if col_name in relational_data and row_idx in relational_data[col_name]:
                    # Use the full "ID:Name" format for relational fields
                    record_dict[col_name] = relational_data[col_name][row_idx]
                else:
                    record_dict[col_name] = self._serialize_value(value, field_type)
            result_data.append(record_dict)

        serialize_duration = time.time() - serialize_start
        _logger.info(f"  Serialization: {serialize_duration:.2f}s")

        total_duration = time.time() - start_time
        _logger.info(f"✓ Data fetch completed in {total_duration:.2f}s")

        return result_data

    def _fetch_relational_names(
        self, column_names, relational_fields, rows, current_model
    ):
        """Fetch display names for relational fields."""
        relational_data = {}
        cr = request.env.cr

        for col_name in column_names:
            if col_name not in relational_fields:
                continue

            field_info = relational_fields[col_name]
            field_type = field_info["type"]
            related_model = field_info["relation"]
            related_table = related_model.replace(".", "_")
            col_index = column_names.index(col_name)

            try:
                # Get the rec_name for the related model
                rec_name = self._get_model_rec_name(related_model)

                # Check if the rec_name column exists in the related table
                cr.execute(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """,
                    (related_table, rec_name),
                )

                if not cr.fetchone():
                    _logger.warning(
                        f"Field {rec_name} not found in {related_table}, skipping"
                    )
                    continue

                if field_type == "many2one":
                    # Collect all IDs from this column
                    ids = set()
                    for row in rows:
                        val = row[col_index]
                        if val and isinstance(val, int):
                            ids.add(val)

                    if ids:
                        # Fetch names in one query
                        cr.execute(
                            sql.SQL(
                                """
                            SELECT id, {}
                            FROM {}
                            WHERE id = ANY(%s)
                        """
                            ).format(
                                sql.Identifier(rec_name), sql.Identifier(related_table)
                            ),
                            [list(ids)],
                        )

                        id_to_name = {row[0]: row[1] for row in cr.fetchall()}

                        # Map back to rows with format "ID:Name"
                        relational_data[col_name] = {}
                        for row_idx, row in enumerate(rows):
                            val = row[col_index]
                            if val and val in id_to_name:
                                display_name = (
                                    id_to_name[val] if id_to_name[val] else str(val)
                                )
                                relational_data[col_name][
                                    row_idx
                                ] = f"{val}:{display_name}"
                            elif val:
                                relational_data[col_name][row_idx] = str(val)
                            else:
                                relational_data[col_name][row_idx] = ""

                elif field_type in ("many2many", "one2many"):
                    # For many2many/one2many, handle array fields
                    relational_data[col_name] = {}

                    # Collect all unique IDs across all rows
                    all_ids = set()
                    for row in rows:
                        val = row[col_index]
                        if val and isinstance(val, list):
                            all_ids.update(val)

                    if all_ids:
                        # Fetch all names in one query
                        cr.execute(
                            sql.SQL(
                                """
                            SELECT id, {}
                            FROM {}
                            WHERE id = ANY(%s)
                        """
                            ).format(
                                sql.Identifier(rec_name), sql.Identifier(related_table)
                            ),
                            [list(all_ids)],
                        )

                        id_to_name = {row[0]: row[1] for row in cr.fetchall()}

                        # Map back to rows
                        for row_idx, row in enumerate(rows):
                            val = row[col_index]
                            if val and isinstance(val, list):
                                # Format as "ID1:Name1,ID2:Name2,ID3:Name3"
                                formatted_items = []
                                for item_id in val:
                                    display_name = id_to_name.get(item_id, str(item_id))
                                    if display_name:
                                        formatted_items.append(
                                            f"{item_id}:{display_name}"
                                        )
                                    else:
                                        formatted_items.append(str(item_id))
                                relational_data[col_name][row_idx] = ",".join(
                                    formatted_items
                                )
                            else:
                                relational_data[col_name][row_idx] = ""

            except Exception as e:
                _logger.warning(
                    f"Failed to fetch relational data for {col_name}: {str(e)}"
                )
                continue

        return relational_data

    def _get_model_rec_name(self, model_name):
        """Get the rec_name field for a model, fallback to 'name'."""
        try:
            model = request.env[model_name].sudo()
            # Check if model has _rec_name defined
            if hasattr(model, "_rec_name") and model._rec_name:
                return model._rec_name
            # Fallback to 'name' if it exists
            elif "name" in model._fields:
                return "name"
            # Last resort: use 'id'
            else:
                return "id"
        except Exception:
            return "name"  # Safe fallback

    def _serialize_value(self, value, field_type=None):
        """Efficiently serialize values for JSON."""
        if value is None or value is False:
            return ""
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, bool):
            return value
        elif isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore") if value else ""
        elif isinstance(value, tuple):
            # Many2one fields return (id, name) tuples
            return value[1] if len(value) > 1 else str(value[0])
        elif isinstance(value, list):
            # Many2many and One2many
            return ",".join(map(str, value)) if value else ""
        else:
            return str(value) if value else ""

    @http.route("/send_data", auth="public", type="http", csrf=False, methods=["POST"])
    def fetch_table_odoo_data(self, **params):
        """Handle data import from Google Sheets with column-wise fallback and detailed logging."""
        config, error_resp = self._get_config_or_error()
        if error_resp:
            return error_resp

        start_time = time.time()
        data = json.loads(request.httprequest.data.decode("utf-8"))
        initiated_at = datetime.now()

        if not data or "table" not in data or "data" not in data:
            return Response(
                json.dumps({"error": "Missing table or data in the request."}),
                status=400,
                content_type="application/json",
            )

        table = data.get("table")
        records_data = data.get("data")

        try:
            model = request.env[table].sudo()
        except KeyError:
            return Response(
                json.dumps({"error": f"Model {table} not found"}),
                status=404,
                content_type="application/json",
            )

        record_count = len(records_data) - 1
        headers = records_data[0]

        _logger.info(
            f"Starting data import for {table}: {record_count} records, columns: {headers}"
        )

        success_count = 0
        failed_count = 0
        partial_count = 0
        detailed_errors = []

        has_company = "company_id" in model._fields
        company_id = config.company_id.id if has_company else None

        for idx, row in enumerate(records_data[1:], 1):
            record_data = {headers[i]: value for i, value in enumerate(row)}
            processed_data, translations = self._prepare_data(record_data, model)
            record_id = (
                int(processed_data.get("id")) if processed_data.get("id") else None
            )

            existing_record = (
                model.search([("id", "=", record_id)], limit=1) if record_id else None
            )

            # Security check: do not allow modifying records from other companies
            if existing_record and has_company and existing_record.company_id and existing_record.company_id.id != company_id:
                failed_count += 1
                error_detail = {
                    "row": idx,
                    "record_id": record_id,
                    "operation": "update",
                    "error": f"Security: Record belongs to another company ({existing_record.company_id.name})"
                }
                detailed_errors.append(error_detail)
                _logger.info(f"Security block: Tried to update record ID {record_id} belonging to another company")
                continue

            # Multi-company enforcement for create/write
            if has_company:
                if existing_record:
                    # Never modify the company of an existing record
                    processed_data.pop("company_id", None)
                else:
                    processed_data["company_id"] = company_id

            # Create a savepoint before attempting the operation
            savepoint_name = f'record_{record_id or "new"}_{idx}'
            request.env.cr.execute(f"SAVEPOINT {savepoint_name}")

            existing_record = (
                model.search([("id", "=", record_id)], limit=1) if record_id else None
            )

            if existing_record:
                # TRY UPDATE WITH ALL COLUMNS
                try:
                    existing_record.write(processed_data)
                    self._apply_translations(existing_record, translations)
                    success_count += 1
                    request.env.cr.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    _logger.debug(f"✓ Successfully updated record ID {record_id}")
                except Exception as e:
                    # FALLBACK: Try column-by-column update
                    request.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    _logger.warning(
                        f"Full update failed for ID {record_id}, trying column-wise: {str(e)}"
                    )

                    column_errors = []
                    successful_columns = []

                    for field, value in processed_data.items():
                        if field == "id":  # Skip id field
                            continue

                        field_savepoint = f"{savepoint_name}_{field}"
                        request.env.cr.execute(f"SAVEPOINT {field_savepoint}")
                        try:
                            existing_record.write({field: value})
                            request.env.cr.execute(
                                f"RELEASE SAVEPOINT {field_savepoint}"
                            )
                            successful_columns.append(field)
                        except Exception as field_error:
                            request.env.cr.execute(
                                f"ROLLBACK TO SAVEPOINT {field_savepoint}"
                            )
                            column_errors.append(
                                {"field": field, "error": str(field_error)}
                            )
                            _logger.debug(
                                f"  ✗ Field '{field}' failed: {str(field_error)}"
                            )

                    if column_errors:
                        partial_count += 1
                        error_detail = {
                            "row": idx,
                            "record_id": record_id,
                            "operation": "update",
                            "successful_fields": successful_columns,
                            "failed_fields": column_errors,
                        }
                        detailed_errors.append(error_detail)
                        _logger.info(
                            f"⚠ Partial update for ID {record_id}: {len(successful_columns)} succeeded, {len(column_errors)} failed"
                        )
                    else:
                        success_count += 1
                        _logger.info(
                            f"✓ Column-wise update succeeded for ID {record_id}"
                        )
            else:
                # TRY CREATE WITH ALL COLUMNS
                try:
                    new_record = model.create(processed_data)
                    self._apply_translations(new_record, translations)
                    success_count += 1
                    request.env.cr.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                    _logger.debug(f"✓ Successfully created new record (row {idx})")
                except Exception as e:
                    # FALLBACK: Try column-by-column create
                    request.env.cr.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    _logger.warning(
                        f"Full create failed for row {idx}, trying column-wise: {str(e)}"
                    )

                    # For create, we need to try with subsets of fields
                    # Start with required fields only, then add optional ones
                    column_errors = []
                    successful_columns = []

                    # Try creating with minimal data first
                    minimal_data = {
                        k: v
                        for k, v in processed_data.items()
                        if k in ["name", "id"]
                        or model._fields.get(k, False)
                        and model._fields[k].required
                    }

                    field_savepoint = f"{savepoint_name}_minimal"
                    request.env.cr.execute(f"SAVEPOINT {field_savepoint}")

                    try:
                        new_record = model.create(minimal_data)
                        request.env.cr.execute(f"RELEASE SAVEPOINT {field_savepoint}")
                        successful_columns = list(minimal_data.keys())

                        # Now try to update with remaining fields one by one
                        remaining_data = {
                            k: v
                            for k, v in processed_data.items()
                            if k not in minimal_data
                        }

                        for field, value in remaining_data.items():
                            field_savepoint_update = f"{savepoint_name}_{field}"
                            request.env.cr.execute(
                                f"SAVEPOINT {field_savepoint_update}"
                            )
                            try:
                                new_record.write({field: value})
                                request.env.cr.execute(
                                    f"RELEASE SAVEPOINT {field_savepoint_update}"
                                )
                                successful_columns.append(field)
                            except Exception as field_error:
                                request.env.cr.execute(
                                    f"ROLLBACK TO SAVEPOINT {field_savepoint_update}"
                                )
                                column_errors.append(
                                    {"field": field, "error": str(field_error)}
                                )

                        if column_errors:
                            partial_count += 1
                            error_detail = {
                                "row": idx,
                                "record_id": new_record.id,
                                "operation": "create",
                                "successful_fields": successful_columns,
                                "failed_fields": column_errors,
                            }
                            detailed_errors.append(error_detail)
                            _logger.info(
                                f"⚠ Partial create for row {idx}: {len(successful_columns)} succeeded, {len(column_errors)} failed"
                            )
                        else:
                            success_count += 1
                            _logger.info(
                                f"✓ Column-wise create succeeded for row {idx}"
                            )

                    except Exception as minimal_error:
                        # Even minimal create failed
                        request.env.cr.execute(
                            f"ROLLBACK TO SAVEPOINT {field_savepoint}"
                        )
                        failed_count += 1
                        error_detail = {
                            "row": idx,
                            "record_id": None,
                            "operation": "create",
                            "error": f"Failed to create even with minimal data: {str(minimal_error)}",
                            "attempted_data": list(minimal_data.keys()),
                        }
                        detailed_errors.append(error_detail)
                        _logger.error(
                            f"✗ Complete failure for row {idx}: {str(minimal_error)}"
                        )

            # Log progress every 100 records
            if idx % 100 == 0:
                _logger.info(
                    f"Progress: {idx}/{record_count} processed (Success: {success_count}, Partial: {partial_count}, Failed: {failed_count})"
                )

        request.env.cr.commit()

        duration = time.time() - start_time
        completed_at = datetime.now()

        # Determine overall status
        if failed_count == 0 and partial_count == 0:
            status = "success"
        elif success_count == 0:
            status = "failure"
        else:
            status = "partial"

        # Create summary error message
        error_summary = f"Success: {success_count}, Partial: {partial_count}, Failed: {failed_count}"
        if detailed_errors:
            error_summary += f"\n\nDetailed Errors ({len(detailed_errors)} records):\n"
            for err in detailed_errors[:5]:  # Show first 5 in summary
                if "failed_fields" in err:
                    failed_field_names = [f["field"] for f in err["failed_fields"]]
                    error_summary += f"- Row {err['row']} (ID: {err.get('record_id', 'N/A')}): Failed fields: {', '.join(failed_field_names)}\n"
                else:
                    error_summary += (
                        f"- Row {err['row']}: {err.get('error', 'Unknown error')}\n"
                    )
            if len(detailed_errors) > 5:
                error_summary += f"... and {len(detailed_errors) - 5} more errors (see detailed_errors field)\n"

        _logger.info(f"Data import completed in {duration:.2f}s - {error_summary}")

        # Log to database
        try:
            request.env["cr.data.processing.log"].sudo().create(
                {
                    "table_name": table,
                    "operation_type": "sheet_to_odoo",
                    "record_count": record_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "partial_count": partial_count,
                    "status": status,
                    "message": error_summary if status == "success" else None,
                    "error_message": (
                        error_summary if status in ["failure", "partial"] else None
                    ),
                    "detailed_errors": (
                        json.dumps(detailed_errors, indent=2)
                        if detailed_errors
                        else None
                    ),
                    "timestamp": f"{duration:.2f}s",
                    "initiated_at": initiated_at,
                    "completed_at": completed_at,
                }
            )
            request.env.cr.commit()
        except Exception as log_error:
            _logger.error(f"Failed to create log entry: {str(log_error)}")

        return Response(
            json.dumps(
                {
                    "message": "Data processed",
                    "success_count": success_count,
                    "partial_count": partial_count,
                    "failed_count": failed_count,
                    "total_count": record_count,
                    "status": status,
                    "errors": detailed_errors[:10],  # Limit to first 10 in response
                }
            ),
            status=200,
            content_type="application/json",
        )

    def _parse_translation_dict(self, value):
        """
        Detect and parse a translation dict from a raw value.
        Handles both dicts and their string representations.
        Returns the parsed dict if it looks like {lang_code: translation},
        or None if it is a plain value.
        """
        import ast

        if isinstance(value, dict):
            candidate = value
        elif isinstance(value, str):
            value = value.strip()
            if not (value.startswith("{") and value.endswith("}")):
                return None
            try:
                candidate = ast.literal_eval(value)
            except Exception:
                return None
        else:
            return None

        # A translation dict has string keys that look like locale codes (e.g. 'en_US', 'de_DE')
        if (
            isinstance(candidate, dict)
            and candidate
            and all(isinstance(k, str) and len(k) >= 2 for k in candidate)
        ):
            return candidate
        return None

    def _apply_translations(self, record, translations):
        """
        Write per-language translations to a record using Odoo's translation mechanism.
        `translations` is  {field_name: {lang_code: translated_value}}
        """
        if not translations:
            return
        # Collect all unique language codes across all fields
        all_langs = set()
        for lang_map in translations.values():
            all_langs.update(lang_map.keys())

        for lang_code in all_langs:
            lang_vals = {
                field: lang_map[lang_code]
                for field, lang_map in translations.items()
                if lang_code in lang_map and lang_map[lang_code] not in (None, "")
            }
            if not lang_vals:
                continue
            try:
                record.with_context(lang=lang_code).write(lang_vals)
                _logger.debug(
                    f"Applied translations for lang '{lang_code}': {list(lang_vals.keys())}"
                )
            except Exception as e:
                _logger.warning(
                    f"Failed to apply translations for lang '{lang_code}': {e}"
                )

    def _prepare_data(self, record_data, model):
        """Prepares record data by converting field values to appropriate types."""
        prepared = {}
        translations = {}

        for field_name, field_value in record_data.items():
            # Skip empty values
            if field_value == "" or field_value is None:
                continue

            field = model._fields.get(field_name)
            if not field:
                continue

            try:
                if field.type == "many2one":
                    prepared[field_name] = self._prepare_many2one(field_value)
                elif field.type == "many2many":
                    prepared[field_name] = self._prepare_many2many(field_value)
                elif field.type == "one2many":
                    prepared[field_name] = self._prepare_one2many(field_value)
                elif field.type in ["date", "datetime"]:
                    prepared[field_name] = self._prepare_date(field_value)
                elif field.type == "float":
                    prepared[field_name] = float(field_value) if field_value else 0.0
                elif field.type == "integer":
                    prepared[field_name] = int(field_value) if field_value else 0
                elif field.type == "boolean":
                    prepared[field_name] = (
                        bool(field_value)
                        if field_value not in ["", "0", "False", "false"]
                        else False
                    )
                elif field.type in ["char", "text", "html"]:
                    trans_dict = self._parse_translation_dict(field_value)
                    if trans_dict:
                        default_val = trans_dict.get("en_US") or next(
                            iter(trans_dict.values()), ""
                        )
                        prepared[field_name] = str(default_val) if default_val else ""
                        translations[field_name] = trans_dict
                    else:
                        prepared[field_name] = str(field_value)
                elif field.type == "monetary":
                    prepared[field_name] = float(field_value) if field_value else 0.0
                else:
                    prepared[field_name] = field_value
            except Exception as e:
                _logger.warning(f"Failed to prepare field {field_name}: {str(e)}")
                continue

        return prepared, translations

    def _prepare_many2one(self, value, comodel_name=None):
        """Convert many2one value to ID from 'ID:Name' format."""
        if isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return value
        elif isinstance(value, str):
            value = value.strip()
            if not value:
                return False

            # Parse "ID:Name" format
            if ":" in value:
                try:
                    return int(value.split(":", 1)[0])
                except ValueError:
                    return False

            # Parse plain integer
            if value.isdigit():
                return int(value)

            # Check old "ID,Name" format for backward compatibility
            if "," in value:
                try:
                    return int(value.split(",")[0].strip())
                except ValueError:
                    return False

            return False

        return False

    def _prepare_many2many(self, value, comodel_name=None):
        """Convert many2many value to IDs from 'ID1:Name1,ID2:Name2' format."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False

            # Split by comma: "1:ABC,2:DEF,3:XYZ"
            items = [item.strip() for item in value.split(",") if item.strip()]
            ids = []

            for item in items:
                # Parse "ID:Name" format
                if ":" in item:
                    try:
                        ids.append(int(item.split(":", 1)[0]))
                    except ValueError:
                        continue
                # Parse plain integer
                elif item.isdigit():
                    ids.append(int(item))

            return [(6, 0, ids)] if ids else False

        elif isinstance(value, list):
            ids = [v for v in value if isinstance(v, int)]
            return [(6, 0, ids)] if ids else False

        return False

    def _prepare_one2many(self, value, comodel_name=None):
        """Convert one2many value to IDs from 'ID1:Name1,ID2:Name2' format."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False

            # Split by comma: "1:ABC,2:DEF,3:XYZ"
            items = [item.strip() for item in value.split(",") if item.strip()]
            ids = []

            for item in items:
                # Parse "ID:Name" format
                if ":" in item:
                    try:
                        ids.append(int(item.split(":", 1)[0]))
                    except ValueError:
                        continue
                # Parse plain integer
                elif item.isdigit():
                    ids.append(int(item))

            return [(6, 0, ids)] if ids else False

        elif isinstance(value, list):
            ids = [v for v in value if isinstance(v, int)]
            return [(6, 0, ids)] if ids else False

        return False

    def _prepare_date(self, value):
        if isinstance(value, str) and value:
            try:
                value = value.rstrip("Z").replace("T", " ")
                if "." in value:
                    value = value.split(".")[0]
                return fields.Datetime.from_string(value)
            except:
                return False
        return False
