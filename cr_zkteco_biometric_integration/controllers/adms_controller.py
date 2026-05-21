# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import pytz
import re
from datetime import datetime
from odoo import http, fields
from odoo.http import request

# try:
#     from zk import ZK
#     HAS_PYZK = True
# except ImportError:
#     HAS_PYZK = False
#     _pyzk_warned = False

_logger = logging.getLogger(__name__)


class AdmsController(http.Controller):
    """
    ADMS (Attendance Data Management System) HTTP controller for ZKTeco devices.

    ZKTeco biometric devices supporting the ADMS protocol push attendance records
    to this endpoint in real-time as users punch in or out.

    Protocol overview:
        - Device sends POST to /iclock/cdata?SN=<serial>&table=ATTLOG&Key=<key>
        - Request body contains tab-separated attendance lines
        - Each line: user_id  timestamp  verify  status  work_code  reserved
        - Odoo validates the device, parses the lines, and returns plain "OK"
    """

    @http.route(
        "/iclock/getrequest",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def adms_getrequest(self, **kwargs):
        serial = (kwargs.get("SN") or "").strip()
        # Try finding Key case-insensitively
        comm_key = ""
        for k, v in kwargs.items():
            if k.lower() == "key":
                comm_key = str(v).strip()
                break

        _logger.info("ADMS: Heartbeat (GET) from SN=%s. Params: %s", serial, kwargs)

        device = (
            request.env["biometric.device"]
            .sudo()
            .search([("serial_number", "=", serial)], limit=1)
        )
        if not device:
            return request.make_response("OK", headers=[("Content-Type", "text/plain")])

        if device.password and device.communication_key != comm_key:
            _logger.warning(
                "ADMS: Key Mismatch for SN=%s. Expected: '%s', Received: '%s'",
                serial,
                device.communication_key,
                comm_key,
            )
            return request.make_response(
                "ERROR: Invalid key",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        # Notify if device was offline (> 10 mins) and just came back
        if device.last_seen:
            from datetime import datetime, timedelta

            if (datetime.now() - device.last_seen) > timedelta(minutes=10):
                device._notify_admin(notification_type="online")
        elif not device.last_seen:
            # First time seeing a discovered device heartbeat
            device._notify_admin(notification_type="online")

        # Check for pending commands for this device
        # Fetch the oldest pending commands (Batch of 5 to speed up processing)
        commands = (
            request.env["biometric.device.command"]
            .sudo()
            .search(
                [("device_id", "=", device.id), ("status", "=", "pending")],
                order="id asc",
                limit=5,
            )
        )

        if commands:
            # Build multi-line response: C:ID:COMMAND
            resp_lines = []
            for cmd in commands:
                resp_lines.append("C:%s:%s" % (cmd.id, cmd.command_text))

            resp_body = "\n".join(resp_lines)
            _logger.info("ADMS: Sending command to device SN=%s: %s", serial, resp_body)
            return request.make_response(
                resp_body, headers=[("Content-Type", "text/plain")]
            )

        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    @http.route(
        "/iclock/devicecmd",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def adms_devicecmd(self, **kwargs):
        """
        Endpoint for the device to report the result of command executions.
        Handles both single-line (ID=1&Return=0) and multi-line responses.
        """
        serial = (kwargs.get("SN") or "").strip()
        # Try finding Key case-insensitively
        comm_key = ""
        for k, v in kwargs.items():
            if k.lower() == "key":
                comm_key = str(v).strip()
                break

        raw_body = request.httprequest.get_data(as_text=True) or ""
        _logger.info("ADMS: Command result from SN=%s. Params: %s", serial, kwargs)

        device = (
            request.env["biometric.device"]
            .sudo()
            .search([("serial_number", "=", serial)], limit=1)
        )
        if device and device.password and device.communication_key != comm_key:
            _logger.warning(
                "ADMS: Key Mismatch in devicecmd for SN=%s. Expected: '%s', Received: '%s'",
                serial,
                device.communication_key,
                comm_key,
            )
            return request.make_response(
                "ERROR: Invalid key",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        # Split by newline in case the device returns results for multiple commands at once
        lines = [line.strip() for line in raw_body.split("\n") if line.strip()]

        for line in lines:
            params = {}
            for part in line.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()

            cmd_id = params.get("ID")
            return_code = params.get("Return")

            if cmd_id:
                try:
                    command = (
                        request.env["biometric.device.command"]
                        .sudo()
                        .browse(int(cmd_id))
                    )
                    if command.exists():
                        # Return code 0 usually means success in ADMS
                        # Return=0: command success (fingerprint enrolled)
                        # Return=2: face enrolled successfully (ZKTeco sends 2 for face via ENROLL_FP FID=111)
                        status = "success" if return_code in ("0", "2") else "failed"
                        command.write(
                            {
                                "status": status,
                                "response_text": line,
                            }
                        )
                except Exception as e:
                    _logger.error(
                        "ADMS: Error processing devicecmd for SN=%s: %s", serial, e
                    )

        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    # ---------------------------------------------------------
    # HEARTBEAT + HANDSHAKE
    # ---------------------------------------------------------
    @http.route(
        "/iclock/cdata",
        type="http",
        auth="public",  # must be same auth on both — use public
        methods=["GET", "POST"],
        csrf=False,
    )
    def adms_cdata(self, **kwargs):
        serial = (kwargs.get("SN") or "").strip()
        # Try finding Key case-insensitively
        comm_key = ""
        for k, v in kwargs.items():
            if k.lower() == "key":
                comm_key = str(v).strip()
                break

        table = (kwargs.get("table") or "").strip()
        options = (kwargs.get("options") or "").strip()

        _logger.info(
            "ADMS: Request from SN=%s method=%s table=%s. Params: %s",
            serial,
            request.httprequest.method,
            table,
            kwargs,
        )

        # ── GET: Handshake ────────────────────────────────────────────────────
        if request.httprequest.method == "GET":
            # print("adms handshake hit")

            if not serial:
                return request.make_response(
                    "ERROR", headers=[("Content-Type", "text/plain")]
                )

            device = (
                request.env["biometric.device"]
                .sudo()
                .search([("serial_number", "=", serial)], limit=1)
            )

            # Auto-discovery: Create device if it doesn't exist
            if not device:
                _logger.info(
                    "ADMS: New device discovered SN=%s. Auto-creating...", serial
                )
                device = (
                    request.env["biometric.device"]
                    .sudo()
                    .create(
                        {
                            "name": f"Discovered Device: {serial}",
                            "serial_number": serial,
                            "state": "draft",
                            "active": True,
                            "last_seen": fields.Datetime.now(),
                        }
                    )
                )
                # Notify admin about new discovery
                device._notify_admin(notification_type="discovered")

            if not device or device.state != "confirmed":
                _logger.warning(
                    "ADMS: Device SN=%s is pending approval or unknown", serial
                )
                return request.make_response(
                    "ERROR: Device pending approval",
                    headers=[("Content-Type", "text/plain")],
                )

            device.sudo().write({"last_seen": fields.Datetime.now()})

            body = (
                "\n".join(
                    [
                        f"GET OPTION FROM: {serial}",
                        "ATTLOGStamp=0",
                        "OPERLOGStamp=0",
                        "ATTPHOTOStamp=0",
                        f"ErrorDelay={device.heartbeat_delay * 2}",
                        f"Delay={device.heartbeat_delay}",
                        "TransTimes=00:00;14:05",
                        "TransInterval=1",
                        "TransFlag=TransData AttLog OpLog AttPhoto Photo",
                        "Realtime=1",
                        "Encrypt=None",
                    ]
                )
                + "\n"
            )

            return request.make_response(body, headers=[("Content-Type", "text/plain")])

        # ── POST: Attendance push ─────────────────────────────────────────────
        # print("adms post hit")

        device = (
            request.env["biometric.device"]
            .sudo()
            .search([("serial_number", "=", serial)], limit=1)
        )

        # Auto-discovery also handles POST if handshake was skipped
        if not device:
            _logger.info(
                "ADMS: New device discovered via POST SN=%s. Auto-creating...", serial
            )
            device = (
                request.env["biometric.device"]
                .sudo()
                .create(
                    {
                        "name": f"Discovered Device: {serial}",
                        "serial_number": serial,
                        "state": "draft",
                        "active": True,
                        "last_seen": fields.Datetime.now(),
                    }
                )
            )
            # Notify admin about new discovery
            device._notify_admin(notification_type="discovered")

        if not device or device.state != "confirmed":
            _logger.warning("ADMS: Device SN=%s is pending approval or unknown", serial)
            return request.make_response(
                "ERROR: Device pending approval",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        if device.password and device.communication_key != comm_key:
            return request.make_response(
                "ERROR: Invalid communication key",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        table_upper = table.upper()
        raw_body = request.httprequest.data.decode("utf-8")
        lines = [ln.strip() for ln in raw_body.splitlines() if ln.strip()]
        _logger.info(
            "ADMS: Received table=%s with %d lines of data from SN=%s",
            table_upper,
            len(lines),
            serial,
        )
        _logger.debug("ADMS: Raw Body: %s", raw_body)

        if table_upper == "ATTLOG":
            _logger.info(
                "ADMS: Processing %d ATTLOG line(s) from SN=%s", len(lines), serial
            )
            for line in lines:
                self._process_attlog_line(device, line)

            # Automatic Post-Sync Cleanup
            if device.auto_clear_log:
                _logger.info(
                    "ADMS: Auto-clearing logs for SN=%s after successful sync", serial
                )
                request.env["biometric.device.command"].sudo().create(
                    {
                        "device_id": device.id,
                        "command_text": "CLEAR LOG",
                    }
                )
        elif table_upper in ["USER", "USERINFO"]:
            _logger.info(
                "ADMS: Processing %d USER info line(s) from SN=%s", len(lines), serial
            )
            self._process_user_data(device, raw_body)
        elif table_upper == "OPERLOG":
            _logger.info("ADMS: Processing OPERLOG from SN=%s", serial)
            # Some devices (like yours) send biometric data inside OPERLOG!
            for line in lines:
                if line.startswith("FP "):
                    clean_line = line[3:]
                    self._process_template_data(device, clean_line, "finger")
                elif line.startswith("FACE "):
                    clean_line = line[5:]
                    self._process_template_data(device, clean_line, "face")
                elif line.startswith("USER "):
                    clean_line = line[5:]
                    self._process_user_data(device, clean_line)
        elif table_upper in [
            "FINGERTMP",
            "FP",
            "TEMPLATEV10",
            "TEMPLATEV9",
            "FINGERPRINT",
        ]:
            _logger.info(
                "ADMS: Processing %d Fingerprint template(s) from SN=%s",
                len(lines),
                serial,
            )
            self._process_template_data(device, raw_body, "finger")
        elif table_upper in ["FACETMP", "FACE", "FACETEMPLATE"]:
            _logger.info(
                "ADMS: Processing %d Face template(s) from SN=%s", len(lines), serial
            )
            self._process_template_data(device, raw_body, "face")
        elif table_upper in ["ATTPHOTO", "PHOTO", "USERPIC", "USERPHOTO", "PERS_PIC"]:
            _logger.info("ADMS: Processing %d Photo(s) from SN=%s", len(lines), serial)
            self._process_photo_data(device, raw_body)
        else:
            _logger.warning(
                "ADMS: Received UNKNOWN table '%s' from SN=%s. Data: %s",
                table_upper,
                serial,
                raw_body[:100],
            )

        device.sudo().write({"last_seen": fields.Datetime.now()})
        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    @http.route(
        "/iclock/fdata",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def adms_fdata(self, **kwargs):
        """
        Endpoint for File Data (Photos on SpeedFace firmware).
        """
        serial = (kwargs.get("SN") or "").strip()
        # Try finding Key case-insensitively
        comm_key = ""
        for k, v in kwargs.items():
            if k.lower() == "key":
                comm_key = str(v).strip()
                break

        table = (kwargs.get("table") or "").strip()
        raw_data = request.httprequest.data

        _logger.info(
            "ADMS: File data request from SN=%s table=%s. Params: %s",
            serial,
            table,
            kwargs,
        )

        device = (
            request.env["biometric.device"]
            .sudo()
            .search([("serial_number", "=", serial)], limit=1)
        )
        if device and device.password and device.communication_key != comm_key:
            _logger.warning(
                "ADMS: Key Mismatch in fdata for SN=%s. Expected: '%s', Received: '%s'",
                serial,
                device.communication_key,
                comm_key,
            )
            return request.make_response(
                "ERROR: Invalid key",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        if table.upper() == "ATTPHOTO" and raw_data:
            try:
                body_head = raw_data[:500].decode("utf-8", errors="ignore")
                pin = ""
                # SpeedFace format: PIN=20260504151344-1.jpg
                pin_filename_match = re.search(r"PIN=[^-\n]+-(\d+)\.jpg", body_head)
                if pin_filename_match:
                    pin = pin_filename_match.group(1)

                if pin:
                    employee = (
                        request.env["hr.employee"]
                        .sudo()
                        .search([("device_user_id", "=", pin)], limit=1)
                    )
                    if employee:
                        marker = b"CMD=uploadphoto"
                        if marker in raw_data:
                            # Extract binary JPEG after marker, skipping potential metadata junk
                            search_start = raw_data.find(marker) + len(marker)
                            image_start = raw_data.find(b"\xff\xd8", search_start)
                            if image_start == -1:
                                image_start = search_start  # Fallback

                            # Find the most recent attendance log for this user to attach the photo
                            log = (
                                request.env["biometric.attendance.log"]
                                .sudo()
                                .search(
                                    [
                                        ("device_user_id", "=", pin),
                                        ("device_id.serial_number", "=", serial),
                                    ],
                                    order="timestamp desc",
                                    limit=1,
                                )
                            )
                            if log:
                                import base64

                                image_b64 = base64.b64encode(
                                    raw_data[image_start:]
                                ).decode("utf-8")
                                log.sudo().write({"image": image_b64})
                                _logger.info(
                                    "ADMS: Photo saved to Attendance Log for PIN=%s",
                                    pin,
                                )
                            else:
                                _logger.warning(
                                    "ADMS: Photo received for PIN=%s but no attendance log found to attach it to.",
                                    pin,
                                )
            except Exception as e:
                _logger.error("ADMS: Failed to process fdata photo: %s", e)

        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _process_photo_data(self, device, raw_body):
        """
        Parses Photo data from the device and updates the Employee profile.
        Format: PIN=1\tFileName=1.jpg\tSize=... \tContent=...
        """
        import base64

        lines = [ln.strip() for ln in raw_body.splitlines() if ln.strip()]
        for line in lines:
            params = self._parse_adms_line(line)
            pin = params.get("PIN") or params.get("UserPin")
            if pin:
                pin = str(pin).split(" ")[0]
            # The photo content can be in 'Content' or sometimes the entire body is the photo
            content = params.get("Content") or params.get("TMP")

            if pin and content:
                employee = (
                    request.env["hr.employee"]
                    .sudo()
                    .search([("device_user_id", "=", pin)], limit=1)
                )
                if employee:
                    try:
                        # Some devices send data with headers, some raw base64
                        # We try to clean it if it has common base64 issues
                        image_data = content.strip()

                        # Validate if it's base64
                        try:
                            base64.b64decode(image_data, validate=True)
                        except:
                            # If not valid base64, it might be raw binary (less common in ADMS text lines)
                            # but we'll try to encode it just in case
                            image_data = base64.b64encode(
                                image_data.encode("utf-8")
                            ).decode("utf-8")

                        # Find the most recent attendance log for this user to attach the photo
                        log = (
                            request.env["biometric.attendance.log"]
                            .sudo()
                            .search(
                                [
                                    ("device_user_id", "=", pin),
                                    (
                                        "device_id.serial_number",
                                        "=",
                                        device.serial_number,
                                    ),
                                ],
                                order="timestamp desc",
                                limit=1,
                            )
                        )
                        if log:
                            log.sudo().write({"image": image_data})
                            _logger.info(
                                "ADMS: Photo saved to Attendance Log for PIN=%s", pin
                            )
                        else:
                            _logger.warning(
                                "ADMS: Photo received for PIN=%s but no attendance log found to attach it to.",
                                pin,
                            )
                    except Exception as e:
                        _logger.error(
                            "ADMS: Failed to process photo for PIN=%s: %s", pin, e
                        )

    def _parse_attlog_timestamp(self, ts_str, device_tz_name):
        """
        Parse a device-local timestamp string and convert it to a UTC datetime.

        ZKTeco devices send timestamps as "YYYY-MM-DD HH:MM:SS" in the device's
        local timezone. This method attaches the timezone and converts to UTC.

        Args:
            ts_str (str): Raw timestamp string from the ATTLOG line.
            device_tz_name (str): pytz timezone name configured on the device record.

        Returns:
            datetime: Timezone-aware UTC datetime, or None if parsing fails.
        """
        try:
            naive_dt = datetime.strptime(ts_str.strip(), "%Y-%m-%d %H:%M:%S")
            device_tz = pytz.timezone(device_tz_name or "UTC")
            local_dt = device_tz.localize(naive_dt, is_dst=False)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            _logger.info(
                "ADMS: Timestamp conversion — device_tz=%s raw='%s' → UTC='%s'",
                device_tz_name,
                ts_str.strip(),
                utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )
            return utc_dt
        except Exception as e:
            _logger.warning("ADMS: Failed to parse timestamp '%s': %s", ts_str, e)
            return None

    def _get_or_create_employee(self, device, device_user_id):
        """
        Look up an hr.employee by device_user_id.  If none is found, attempt
        to resolve the user's real name from the ZKTeco device via pyzk and
        then automatically create a new employee record.

        The name resolution order is:
            1. Real name fetched from the device via pyzk.
            2. Fallback: ``"Biometric User <device_user_id>"``.

        Args:
            device (biometric.device): The Odoo device record.  Used to open
                a pyzk connection when a new employee must be created.
            device_user_id (str): The user ID as sent by the ZKTeco device.

        Returns:
            hr.employee: Existing or newly created employee record.
        """
        Employee = request.env["hr.employee"].sudo()
        employee = Employee.search([("device_user_id", "=", device_user_id)], limit=1)
        if not employee:
            _logger.info(
                "ADMS: Auto-creating employee for device_user_id=%s", device_user_id
            )
            # Try to fetch the real name stored on the device
            # real_name = self._fetch_user_name_from_device(device, device_user_id)
            employee_name = "Biometric User %s" % device_user_id

            employee = Employee.create(
                {
                    "name": employee_name,
                    "device_user_id": device_user_id,
                }
            )
            _logger.info(
                "ADMS: Created employee name='%s' device_user_id=%s. Requesting full details from device...",
                employee_name,
                device_user_id,
            )

            # Automatically request full details (Name, Role, Templates) from device
            Command = request.env["biometric.device.command"].sudo()
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY UserInfo PIN={device_user_id}",
                }
            )
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY FingerTmp PIN={device_user_id}",
                }
            )
            Command.create(
                {
                    "device_id": device.id,
                    "command_text": f"DATA QUERY Face PIN={device_user_id}",
                }
            )
        return employee

    # -------------------------------------------------------------------------
    # pyzk Voice Helpers
    # -------------------------------------------------------------------------

    # def _play_device_voice(self, device, voice_index):
    #     """
    #     Connect to the ZKTeco device via pyzk and play a built-in voice prompt.
    #
    #     Useful voice indexes:
    #         0  = Thank You
    #         2  = Access Denied
    #         3  = Invalid ID
    #         4  = Please try again
    #         9  = Duplicated punch
    #
    #     Args:
    #         device (biometric.device): The device record (must have device_ip set).
    #         voice_index (int): Index of the built-in voice message to play.
    #     """
    #     if not HAS_PYZK or not device.device_ip:
    #         return
    #
    #     zk = ZK(
    #         device.device_ip,
    #         port=device.device_port or 4370,
    #         timeout=5,
    #         password=0,
    #         force_udp=False,
    #         ommit_ping=True,
    #     )
    #     conn = None
    #     try:
    #         conn = zk.connect()
    #         conn.test_voice(index=voice_index)
    #     except Exception as exc:
    #         _logger.warning(
    #             "ADMS: Failed to play voice (index=%s) on device SN=%s: %s",
    #             voice_index, device.serial_number, exc,
    #         )
    #     finally:
    #         if conn:
    #             try:
    #                 conn.disconnect()
    #             except Exception:
    #                 pass

    # def _play_device_voice_async(self, device, voice_index):
    #     """
    #     Fire-and-forget wrapper around ``_play_device_voice``.
    #
    #     Launches the pyzk connection in a daemon thread so the ADMS HTTP
    #     response is not blocked by the device round-trip.
    #
    #     Args:
    #         device (biometric.device): The device record.
    #         voice_index (int): Built-in voice index to play.
    #     """
    #     thread = threading.Thread(
    #         target=self._play_device_voice,
    #         args=(device, voice_index),
    #         daemon=True,
    #     )
    #     thread.start()

    # -------------------------------------------------------------------------
    # Attendance Processing
    # -------------------------------------------------------------------------

    def _process_attendance(self, device, employee, utc_dt, punch_type):
        """
        Create or update an ``hr.attendance`` record based on the explicit
        punch type reported by the ZKTeco device.

        Punch type mapping (from ATTLOG status field):
            ``"in"``  — status 0 (Check In) or 4 (Overtime In)
            ``"out"`` — status 1 (Check Out) or 5 (Overtime Out)

        Rules:
            - ``"in"``  → always creates a new ``check_in`` record.
            - ``"out"`` → finds the most-recent open record (``check_out`` is
              False) and sets its ``check_out``.
              If no open record exists the punch is invalid: voice index 4
              ("Please try again") is played on the device asynchronously and
              the method returns ``False`` to signal the caller to skip saving.

        Args:
            device (biometric.device): The device record (used for voice playback).
            employee (hr.employee): The employee record.
            utc_dt (datetime): UTC-naive punch datetime.
            punch_type (str): ``"in"`` or ``"out"``.

        Returns:
            bool: ``True`` if an attendance record was written, ``False`` if the
            punch was invalid and was deliberately skipped.
        """
        return employee._process_biometric_punch(device, utc_dt, punch_type)

    def _process_attlog_line(self, device, line):
        """
        Parse a single tab-separated ATTLOG line, resolve the punch type from
        the status field, and create both the raw attendance log and the
        ``hr.attendance`` record.

        ATTLOG line format (tab-separated, 0-indexed):
            [0] user_id   [1] timestamp   [2] verify   [3] status
            [4] work_code [5..] reserved

        Status codes handled:
            0  = Check In      → punch_type ``"in"``
            1  = Check Out     → punch_type ``"out"``
            4  = Overtime In   → punch_type ``"in"``
            5  = Overtime Out  → punch_type ``"out"``
            other             → logged and skipped (no ``hr.attendance`` record)

        Args:
            device (biometric.device): The device record that sent this line.
            line (str): One raw ATTLOG line string.
        """
        # Status code → punch_type mapping
        PUNCH_TYPE_MAP = {
            0: "in",  # Check In
            1: "out",  # Check Out
            4: "in",  # Overtime In
            5: "out",  # Overtime Out
        }

        parts = line.split("\t")
        if len(parts) < 2:
            _logger.warning("ADMS: Malformed ATTLOG line (too few fields): %r", line)
            return

        device_user_id = parts[0].strip()
        ts_str = parts[1].strip()
        verify_state = parts[2].strip() if len(parts) > 2 else ""
        verify_mode = parts[3].strip() if len(parts) > 3 else ""

        if not device_user_id or not ts_str:
            _logger.warning("ADMS: Empty user_id or timestamp in line: %r", line)
            return

        # Resolve punch type from status code
        try:
            status_code = int(verify_state)
        except (ValueError, TypeError):
            status_code = -1

        punch_type = PUNCH_TYPE_MAP.get(status_code)

        # Get or auto-create employee (needed for 'both' logic)
        employee = self._get_or_create_employee(device, device_user_id)

        # Override punch type based on device settings
        if device.used_for == "in":
            punch_type = "in"
            verify_state = "0"  # Force Check-in code in logs
        elif device.used_for == "out":
            punch_type = "out"
            verify_state = "1"  # Force Check-out code in logs
        elif device.used_for == "both" and not device.status_code_based:
            # If not status code based, we guess: In if no open attendance, Out otherwise
            open_attendance = (
                request.env["hr.attendance"]
                .sudo()
                .search(
                    [
                        ("employee_id", "=", employee.id),
                        ("check_out", "=", False),
                    ],
                    limit=1,
                )
            )
            punch_type = "out" if open_attendance else "in"
            verify_state = "1" if open_attendance else "0"

        if punch_type is None:
            _logger.info(
                "ADMS: Unsupported punch status=%r for device_user_id=%s — "
                "attendance record will not be created",
                status_code,
                device_user_id,
            )

        # Convert timestamp to UTC
        utc_dt = self._parse_attlog_timestamp(ts_str, device.timezone)
        if not utc_dt:
            return

        # Build unique key for deduplication
        utc_ts_str = fields.Datetime.to_string(utc_dt)
        unique_key = f"{device.serial_number}_{device_user_id}_{utc_ts_str}"

        # Skip duplicates
        Log = request.env["biometric.attendance.log"].sudo()
        if Log.search([("unique_key", "=", unique_key)], limit=1):
            _logger.debug("ADMS: Duplicate punch skipped — unique_key=%s", unique_key)
            return

        # Get or auto-create employee
        employee = self._get_or_create_employee(device, device_user_id)

        # Create raw attendance log
        try:
            Log.create(
                {
                    "device_id": device.id,
                    "device_user_id": device_user_id,
                    "employee_id": employee.id,
                    "timestamp": utc_dt,
                    "verify_state": verify_state,
                    "raw_data": line,
                    "unique_key": unique_key,
                    "status": "new",
                }
            )
            _logger.info(
                "ADMS: Created attendance log for unique_key=%s employee=%s",
                unique_key,
                employee.name,
            )
        except Exception as e:
            _logger.error(
                "ADMS: Failed to create attendance log for unique_key=%s: %s",
                unique_key,
                e,
            )
            return

        # Skip hr.attendance processing for unsupported status codes
        if punch_type is None:
            Log.search([("unique_key", "=", unique_key)]).write({"status": "processed"})
            return

        # Process hr.attendance record
        try:
            success = self._process_attendance(device, employee, utc_dt, punch_type)
            log_status = "processed" if success else "failed"
            Log.search([("unique_key", "=", unique_key)]).write({"status": log_status})
        except Exception as e:
            _logger.error(
                "ADMS: Failed to process hr.attendance for employee=%s unique_key=%s: %s",
                employee.name,
                unique_key,
                e,
            )
            Log.search([("unique_key", "=", unique_key)]).write({"status": "failed"})

    def _process_user_data(self, device, raw_body):
        """
        Parses USER table data from ADMS.
        """
        lines = [ln.strip() for ln in raw_body.splitlines() if ln.strip()]
        _logger.info("🚀🚀🚀 lines : %s", lines)
        for line in lines:
            params = self._parse_adms_line(line)
            _logger.info("🚀🚀🚀 ADMS: Processing UserInfo line params: %s", params)
            pin = params.get("PIN") or params.get("UserPin")
            if pin:
                pin = str(pin).split(" ")[0]
            if pin:
                # Ensure employee exists (Auto-create if missing)
                employee = self._get_or_create_employee(device, pin)

                vals = {}
                # Sync Name from device to Odoo (If name on device is different, update Odoo)
                new_name = params.get("Name")
                if new_name and employee.name != new_name:
                    _logger.info(
                        "ADMS: Updating employee name from device: %s -> %s",
                        employee.name,
                        new_name,
                    )
                    vals["name"] = new_name

                # Sync Privilege/Role from device to Odoo
                pri = (
                    params.get("Pri")
                    or params.get("Privilege")
                    or params.get("UserRole")
                )
                if pri is not None:
                    pri_str = str(pri)
                    # If it's a standard role, sync it.
                    # If it's a CUSTOM role (1, 2, 3...), set Odoo field to EMPTY (False).
                    target_pri = pri_str if pri_str in ["0", "14"] else False

                    if employee.biometric_privilege != target_pri:
                        _logger.info(
                            "ADMS: Privilege sync for user PIN=%s, setting Odoo to %s (Device has custom role %s)",
                            pin,
                            target_pri,
                            pri,
                        )
                        vals["biometric_privilege"] = target_pri

                if vals:
                    employee.sudo().write(vals)
                else:
                    _logger.info("ADMS: Data synced for existing user PIN=%s", pin)

    def _process_template_data(self, device, raw_body, template_type):
        """
        Parses biometric templates (FINGERTMP or FACETMP).
        """
        lines = [ln.strip() for ln in raw_body.splitlines() if ln.strip()]
        Template = request.env["biometric.user.template"].sudo()
        for line in lines:
            params = self._parse_adms_line(line)
            pin = params.get("PIN") or params.get("UserPin")
            if pin:
                pin = str(pin).split(" ")[0]
            tmp = params.get("Tmp") or params.get("Template") or params.get("TMP")
            idx = (
                params.get("FingerID")
                or params.get("FaceID")
                or params.get("FID")
                or "0"
            )

            if not pin and "TMP=" in line:
                pin_match = re.search(r"PIN=(\d+)", line)
                idx_match = re.search(r"FID=(\d+)", line)
                tmp_match = re.search(r"TMP=([A-Za-z0-9+/=]+)", line)
                if pin_match and idx_match and tmp_match:
                    pin = pin_match.group(1)
                    idx = idx_match.group(1)
                    tmp = tmp_match.group(1)
                    template_type = "face" if "FACE" in line else "finger"

            if pin and tmp:
                employee = self._get_or_create_employee(device, pin)
                if employee:
                    # Deduplicate
                    existing = Template.search(
                        [
                            ("employee_id", "=", employee.id),
                            ("type", "=", template_type),
                            ("finger_index", "=", int(idx)),
                        ],
                        limit=1,
                    )

                    if not existing:
                        Template.create(
                            {
                                "employee_id": employee.id,
                                "type": template_type,
                                "template_data": tmp,
                                "finger_index": int(idx),
                            }
                        )
                        _logger.info(
                            "ADMS: Biometric %s fetched and SAVED for user PIN=%s index=%s",
                            template_type,
                            pin,
                            idx,
                        )
                    else:
                        _logger.info(
                            "ADMS: Biometric %s already exists for user PIN=%s index=%s",
                            template_type,
                            pin,
                            idx,
                        )
                else:
                    _logger.warning(
                        "ADMS: Received template for PIN=%s but no employee found in Odoo",
                        pin,
                    )

    def _parse_adms_line(self, line):
        """Helper to parse tab-separated Key=Value pairs."""
        params = {}
        for part in line.split("\t"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()
        return params
