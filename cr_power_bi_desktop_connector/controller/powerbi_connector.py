# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import http
from odoo.http import request, Response
import json
from datetime import datetime
from psycopg2 import sql
import hashlib
import time
import csv
import io
import base64
import pandas as pd


class PowerBIConnectorController(http.Controller):

    @http.route("/powerbi/embed_token/<int:report_id>", type="json", auth="user")
    def get_embed_token(self, report_id, **kwargs):
        report = request.env["powerbi.report"].browse(report_id)
        if not report.exists():
            return {"error": "Report not found"}
        try:
            token = report.config_id._get_embed_token(
                report.report_id, report.workspace_id.workspace_id
            )
            return {
                "token": token,
                "embed_url": report.embed_url,
                "report_id": report.report_id,
            }
        except Exception as e:
            return {"error": str(e)}

    @http.route(
        "/api/get_table_names", type="http", auth="public", methods=["GET"], csrf=False
    )
    def get_table_names(self, token=None):
        """Returns Name Of Models."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            validate_start = time.time()
            if not self._validate_token(token):
                self._log_data_processing(
                    table_name="N/A",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="Invalid or missing access token",
                )
                validate_duration = time.time() - validate_start
                method_duration = time.time() - method_start_time
                return Response(
                    json.dumps({"error": "Invalid or missing access token"}),
                    content_type="application/json",
                    status=401,
                )
            validate_duration = time.time() - validate_start

            fetch_start = time.time()
            model_names = request.env["ir.model"].sudo().search([]).mapped("name")
            fetch_duration = time.time() - fetch_start

            self._log_data_processing(
                table_name="All Tables",
                record_count=len(model_names),
                status="success",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
            )

            response_data = {"tableNames": model_names}
            response = Response(
                json.dumps(response_data), content_type="application/json", status=200
            )
            method_duration = time.time() - method_start_time
            return response

        except Exception as e:
            method_duration = time.time() - method_start_time
            self._log_data_processing(
                table_name="N/A",
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message=str(e),
            )
            return Response(
                json.dumps({"error": str(e)}),
                content_type="application/json",
                status=500,
            )

    @http.route(
        "/api/execute_sql_query",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_query_data(self, token=None, query=None, batch_number=None):
        """Returns data fetched from SQL query with batch processing."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if not token:
                self._log_data_processing(
                    table_name="SQL Query",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="Access token is required.",
                )
                method_duration = time.time() - method_start_time
                return self._json_response(
                    {"error": "Access token is required."}, status=400
                )

            if not query:
                self._log_data_processing(
                    table_name="SQL Query",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="SQL query is required.",
                )
                method_duration = time.time() - method_start_time
                return self._json_response(
                    {"error": "SQL query is required."}, status=400
                )

            user_id = self._validate_token(token)
            if not user_id:
                self._log_data_processing(
                    table_name="SQL Query",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="Invalid or expired token.",
                )
                method_duration = time.time() - method_start_time
                return self._json_response(
                    {"error": "Invalid or expired token."}, status=401
                )

            fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
            result = fetcher.fetch_query_data(query, batch_number)

            if "error" in result:
                fetcher._log_data_processing(
                    table_name="SQL Query",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message=result["error"],
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return self._json_response({"error": result["error"]}, status=500)

            method_duration = time.time() - method_start_time
            return self._json_response(
                {
                    "success": True,
                    "csvData": result["csvData"],
                    "columnNames": result["columnNames"],
                    "columnTypes": result["columnTypes"],
                    "batch_number": result["batch_number"],
                    "total_batches": result["total_batches"],
                    "status": result["status"],
                    "record_count": result.get("record_count", 0),
                }
            )

        except Exception as e:
            method_duration = time.time() - method_start_time
            fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
            fetcher._log_data_processing(
                table_name="SQL Query",
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message=str(e),
                batch_number=batch_number,
            )
            return self._json_response(
                {"error": f"Failed to execute query: {str(e)}"}, status=500
            )

    @http.route(
        "/api/get_table_data", type="http", auth="public", methods=["GET"], csrf=False
    )
    def get_table_data(self, table_name, token=None, batch_number=None):
        """Returns data of table by calling model method."""
        method_start_time = time.time()
        initiated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if not self._validate_token(token):
                fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
                fetcher._log_data_processing(
                    table_name=table_name,
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="Invalid or missing access token",
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return Response(
                    json.dumps({"error": "Invalid or missing access token"}),
                    content_type="application/json",
                    status=401,
                )

            if not table_name:
                fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
                fetcher._log_data_processing(
                    table_name="N/A",
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message="Table name is required",
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return Response(
                    json.dumps({"error": "Table name is required"}),
                    content_type="application/json",
                    status=400,
                )

            fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
            result = fetcher.fetch_table_data(table_name, batch_number)

            if "error" in result:
                fetcher._log_data_processing(
                    table_name=table_name,
                    record_count=0,
                    status="failure",
                    timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    initiated_at=initiated_at,
                    error_message=result["error"],
                    batch_number=batch_number,
                )
                method_duration = time.time() - method_start_time
                return Response(
                    json.dumps({"error": result["error"]}),
                    content_type="application/json",
                    status=404 if "not found" in result["error"].lower() else 500,
                )

            method_duration = time.time() - method_start_time
            return Response(
                json.dumps(
                    {
                        "csvData": result["csvData"],
                        "columnNames": result["columnNames"],
                        "columnTypes": result["columnTypes"],
                        "batch_number": result["batch_number"],
                        "total_batches": result["total_batches"],
                        "status": result["status"],
                        "record_count": result.get("record_count", 0),  # FIXED: was missing
                    }
                ),
                status=200,
                content_type="application/json",
            )

        except Exception as e:
            method_duration = time.time() - method_start_time
            fetcher = request.env["cr.power.bi.data.fetcher"].sudo()
            fetcher._log_data_processing(
                table_name=table_name,
                record_count=0,
                status="failure",
                timespan=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                initiated_at=initiated_at,
                error_message=str(e),
                batch_number=batch_number,
            )
            return Response(
                json.dumps({"error": f"An error occurred: {str(e)}"}),
                content_type="application/json",
                status=500,
            )

    def _json_response(self, data, status=200):
        """Converts Data to JSON Response."""
        return Response(
            json.dumps(data), status=status, content_type="application/json"
        )

    def _validate_token(self, token):
        """Validates Request Or Authenticates the Request."""
        configs = request.env["cr.power.bi.configuration"].sudo().search([])
        if not configs:
            return False
        return any(config.cr_access_token == token for config in configs)

    def _get_concrete_children(self, abstract_model_name, cr):
        """Returns Concrete Children For Abstract Models."""
        concrete_models = []
        for model_name, model_class in request.env.items():
            if getattr(model_class, "_abstract", False) or getattr(
                model_class, "_transient", False
            ):
                continue
            if abstract_model_name in getattr(model_class, "_inherit", []):
                concrete_models.append(model_name)
        return concrete_models

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
        """Logs the Data."""
        request.env["cr.data.processing"].sudo().create(
            {
                "table_name": table_name,
                "record_count": record_count,
                "status": status,
                "error_message": error_message,
                "timestamp": timespan,
                "initiated_at": initiated_at,
                "batch_number": batch_number,
            }
        )