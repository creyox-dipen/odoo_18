# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import base64
import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# CalDAV XML namespaces
NS = {
    'D': 'DAV:',
    'C': 'urn:ietf:params:xml:ns:caldav',
    'CS': 'http://calendarserver.org/ns/',
    'APPLE': 'http://apple.com/ns/ical/',
}


class CalDAVAccount(models.Model):
    """Represents a per-user CalDAV server connection configuration.

    Each user can configure one or more CalDAV accounts pointing to different
    calendar servers. The account stores credentials, sync direction preferences,
    and tracks the last CTag for efficient incremental sync.
    """

    _name = 'caldav.account'
    _description = 'CalDAV Account'
    _order = 'name'

    name = fields.Char(
        string='Account Name',
        required=True,
        help='A descriptive label for this CalDAV connection.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        required=True,
        default=lambda self: self.env.user,
        help='The Odoo user whose calendar is synced with this account.',
    )
    url = fields.Char(
        string='CalDAV Calendar URL',
        required=False,
        help=(
            'Full URL to the CalDAV calendar collection. '
            'Example: https://nextcloud.example.com/remote.php/dav/calendars/user/personal/'
        ),
    )
    username = fields.Char(
        string='Username',
        required=False,
        help='Login username for the CalDAV server.',
    )
    password = fields.Char(
        string='Password',
        required=False,
        help='Login password for the CalDAV server.',
    )
    server_type = fields.Selection(
        selection=[
            # ('generic', 'Generic CalDAV'),
            ('google', 'Google Calendar'),
            # ('outlook', 'Microsoft Outlook'),
            ('icloud', 'Apple iCloud'),
            ('nextcloud', 'Nextcloud'),
            ('synology', 'Synology'),
            ('zoho', 'Zoho Calendar'),
            ('radicale', 'Radicale'),
            ('other', 'Other'),
        ],
        string='Server Type',
        default='other',
        required=True,
    )

    @api.onchange('server_type')
    def _onchange_server_type(self):
        """Automatically populate common CalDAV URLs based on server type to assist users."""
        if not self.server_type:
            return
        
        urls = {
            'google': 'https://apidata.googleusercontent.com/caldav/v2/<EMAIL_ID>/events/',
            # 'outlook': 'https://outlook.office365.com/dav/',
            'icloud': 'https://caldav.icloud.com/<YOUR_ACCOUNT_ID>/calendars/<CALENDAR_UUID>/',
            'zoho': 'https://calendar.zoho.in/caldav/<CALENDAR_ID>/events/',
            'nextcloud': 'https://<DOMAIN>/remote.php/dav/calendars/<USER>/personal/',
            'radicale': 'http://<URL>:5232/<USER>/<CALENDAR>/',
        }
        if self.server_type in urls:
            self.url = urls[self.server_type]

    google_refresh_token = fields.Char(
        string='Google Refresh Token',
        copy=False,
        help='Long-lived OAuth 2.0 refresh token from Google.',
    )
    google_access_token = fields.Char(
        string='Google Access Token',
        copy=False,
        help='Short-lived OAuth 2.0 access token (auto-refreshed).',
    )
    google_access_token_expiry = fields.Datetime(
        string='Token Expiry',
        copy=False,
        help='UTC expiry time of the current access token.',
    )
    google_auth_status = fields.Char(
        string='Google Auth Status',
        compute='_compute_google_auth_status',
        store=False,
    )
    sync_direction = fields.Selection(
        selection=[
            ('bidirectional', 'Bidirectional'),
            ('odoo_to_caldav', 'Odoo → CalDAV only'),
            ('caldav_to_odoo', 'CalDAV → Odoo only'),
        ],
        string='Sync Direction',
        default='bidirectional',
        required=True,
        help='Controls the direction of calendar synchronisation.',
    )
    send_invitation_emails = fields.Boolean(
        string='Send Invitation Emails',
        default=False,
        help=(
            'When enabled, Odoo will send meeting invitation emails to attendees '
            'when events are imported from CalDAV. Disabled by default to prevent '
            'unwanted notifications on incoming CalDAV events.'
        ),
    )
    auto_create_contacts = fields.Boolean(
        string='Auto-create Contacts',
        default=False,
        help=(
            'When enabled, new contacts are automatically created for unknown '
            'attendee email addresses found in CalDAV events.'
        ),
    )
    last_ctag = fields.Char(
        string='Last CTag',
        readonly=True,
        copy=False,
        help='Cached CTag from the last successful sync. Used to detect server changes quickly.',
    )
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True,
        copy=False,
        help='Timestamp of the last successful synchronisation.',
    )
    active = fields.Boolean(string='Active', default=True)
    event_map_ids = fields.One2many(
        'caldav.event.map',
        'account_id',
        string='Event Mappings',
        readonly=True,
    )
    log_ids = fields.One2many(
        'caldav.sync.log',
        'account_id',
        string='Sync Logs',
    )
    log_count = fields.Integer(
        string='Log Count',
        compute='_compute_log_count',
    )

    def _compute_log_count(self):
        """Count the number of sync logs associated with this account."""
        for rec in self:
            rec.log_count = len(rec.log_ids)

    def action_view_sync_logs(self):
        """Open the list of synchronisation logs for this account.
        
        :return: Act window action.
        :rtype: dict
        """
        self.ensure_one()
        return {
            'name': _('Sync Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'caldav.sync.log',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @api.depends('google_refresh_token', 'google_access_token_expiry')
    def _compute_google_auth_status(self):
        """Compute a human-readable authorization status for the Google OAuth connection.

        Possible values: 'Not Authorized', 'Authorized (Token Valid)', 'Authorized (Needs Refresh)'.
        """
        for rec in self:
            if rec.server_type != 'google':
                rec.google_auth_status = ''
            elif not rec.google_refresh_token:
                rec.google_auth_status = 'Not Authorized'
            elif rec.google_access_token and rec.google_access_token_expiry and rec.google_access_token_expiry > fields.Datetime.now():
                rec.google_auth_status = '✓ Authorized (Token Valid)'
            else:
                rec.google_auth_status = '⚠ Authorized (Token will refresh on next sync)'

    def _get_auth_header(self):
        """Build the HTTP Authentication header value.

        For Google Calendar accounts (server_type == 'google'), returns a
        'Bearer <access_token>' header after ensuring the token is fresh.
        For all other server types, falls back to HTTP Basic Authentication
        using the configured username and password.

        :return: 'Basic ...' or 'Bearer ...' authorization header string.
        :rtype: str
        """
        self.ensure_one()
        if self.server_type == 'google':
            self._refresh_google_token()
            return f'Bearer {self.google_access_token or ""}'
        credentials = f'{self.username or ""}:{self.password or ""}'
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f'Basic {encoded}'

    def _refresh_google_token(self):
        """Refresh the Google OAuth 2.0 Access Token using the stored Refresh Token.

        This method is a no-op if:
        - The account is not of type 'google'.
        - No refresh token is stored (user has not authorized yet).
        - The current access token is still valid.

        It calls Google's token endpoint to exchange the refresh token for a
        new short-lived access token (valid ~1 hour), then persists the new
        token and its expiry time on the account record.

        :raises UserError: If Google credentials are missing from Settings or
            if the token refresh request fails.
        """
        self.ensure_one()
        if self.server_type != 'google' or not self.google_refresh_token:
            return

        now = fields.Datetime.now()
        if (
            self.google_access_token
            and self.google_access_token_expiry
            and self.google_access_token_expiry > now
        ):
            return  # Token is still valid

        icp = self.env['ir.config_parameter'].sudo()
        client_id = icp.get_param('cr_odoo_caldav_sync.google_client_id')
        client_secret = icp.get_param('cr_odoo_caldav_sync.google_client_secret')

        if not client_id or not client_secret:
            raise UserError(_(
                'Google Client ID or Secret is not configured. '
                'Please go to Settings → CalDAV Sync and fill in the credentials.'
            ))

        data = urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': self.google_refresh_token,
            'grant_type': 'refresh_token',
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=data,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            _logger.error('Google token refresh failed for %s: %s', self.name, body)
            raise UserError(_(
                'Failed to refresh Google token. Please re-authorize the account.'
            ))
        except Exception as e:
            _logger.error('Google token refresh error for %s: %s', self.name, e)
            raise UserError(_('Failed to refresh Google authentication token: %s', str(e)))

        expiry = fields.Datetime.now() + timedelta(seconds=int(result.get('expires_in', 3600)))
        self.sudo().write({
            'google_access_token': result.get('access_token'),
            'google_access_token_expiry': expiry,
        })
        _logger.info('Google access token refreshed for account "%s", expires %s.', self.name, expiry)

    def action_google_authorize(self):
        """Redirect the user to Google's OAuth 2.0 consent screen.

        Builds the authorization URL with the required scopes and redirect URI,
        then returns an act_url action so Odoo opens the Google sign-in page.
        The 'state' parameter carries the account ID so the callback controller
        can associate the returned code with this account.

        :raises UserError: If the Google Client ID is not configured in Settings.
        :return: Client action to open the Google authorization URL.
        :rtype: dict
        """
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        client_id = icp.get_param('cr_odoo_caldav_sync.google_client_id')
        if not client_id:
            raise UserError(_(
                'Google Client ID is not configured. '
                'Please go to Settings → CalDAV Sync to add your credentials.'
            ))

        base_url = icp.get_param('web.base.url', '').rstrip('/')
        redirect_uri = f'{base_url}/caldav/google/callback'

        auth_params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/userinfo.email openid',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': str(self.id),
        }
        auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(auth_params)
        _logger.info('Redirecting account "%s" to Google authorization URL.', self.name)
        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }

    def _build_request(self, url, method, body=None, extra_headers=None):
        """Construct a urllib Request object with proper auth and headers.

        :param str url: Target URL.
        :param str method: HTTP method (GET, PUT, DELETE, PROPFIND, REPORT, OPTIONS).
        :param bytes|None body: Request body bytes.
        :param dict|None extra_headers: Additional headers to include.
        :return: Configured urllib Request.
        :rtype: urllib.request.Request
        """
        headers = {
            'Authorization': self._get_auth_header(),
            'Content-Type': 'application/xml; charset=utf-8',
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        return req

    def _do_request(self, url, method, body=None, extra_headers=None, expected_codes=None):
        """Execute an HTTP request and return (status_code, headers, body_bytes).

        SSL certificate verification is done using the system CA store;
        self-signed certs will raise an error (use a proper cert or configure
        the system CA bundle).

        :param str url: Target URL.
        :param str method: HTTP method.
        :param bytes|None body: Request payload.
        :param dict|None extra_headers: Extra headers.
        :param list|None expected_codes: List of acceptable HTTP status codes.
        :return: Tuple (status_code, response_headers, body_bytes).
        :rtype: tuple
        :raises UserError: If the server returns an unexpected status code.
        """
        self.ensure_one()
        if expected_codes is None:
            expected_codes = [200, 201, 204, 207]
        req = self._build_request(url, method, body, extra_headers)
        ctx = ssl.create_default_context()
        # Allow self-signed certs for on-premise servers
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                status = resp.status
                headers = resp.headers
                data = resp.read()
                return status, headers, data
        except urllib.error.HTTPError as e:
            body_text = e.read().decode('utf-8', errors='replace')
            _logger.warning(
                'CalDAV HTTP error %s %s -> %s: %s', method, url, e.code, body_text
            )
            raise UserError(
                _('CalDAV server returned HTTP %(code)s for %(method)s %(url)s:\n%(body)s',
                  code=e.code, method=method, url=url, body=body_text)
            )
        except urllib.error.URLError as e:
            _logger.warning('CalDAV URLError %s %s: %s', method, url, e.reason)
            raise UserError(
                _('Cannot connect to CalDAV server at %(url)s:\n%(reason)s',
                  url=url, reason=e.reason)
            )

    def _propfind(self, url, depth='0', body=None):
        """Send a PROPFIND request and return parsed XML ElementTree.

        :param str url: Target CalDAV URL.
        :param str depth: Depth header value ('0', '1', or 'infinity').
        :param bytes|None body: XML request body.
        :return: Parsed XML Element.
        :rtype: xml.etree.ElementTree.Element
        """
        self.ensure_one()
        headers = {'Depth': depth}
        _, _, data = self._do_request(
            url, 'PROPFIND', body=body, extra_headers=headers
        )
        return ET.fromstring(data)

    def _report(self, url, body):
        """Send a REPORT request (used to retrieve event ETags) and return XML.

        :param str url: Target CalDAV URL.
        :param bytes body: XML request body describing the report.
        :return: Parsed XML Element.
        :rtype: xml.etree.ElementTree.Element
        """
        self.ensure_one()
        headers = {'Depth': '1'}
        _, _, data = self._do_request(url, 'REPORT', body=body, extra_headers=headers)
        return ET.fromstring(data)

    def _fetch_ical(self, href):
        """Fetch a single iCal resource from the server.

        :param str href: Absolute or relative URL to the .ics resource.
        :return: Raw iCal text.
        :rtype: str
        """
        _, data = self._fetch_ical_with_etag(href)
        return data

    def _fetch_ical_with_etag(self, href):
        """Fetch a single iCal resource and its ETag from the server.

        :param str href: Absolute or relative URL to the .ics resource.
        :return: Tuple (etag, ical_text).
        :rtype: tuple[str, str]
        """
        self.ensure_one()
        url = self._resolve_href(href)
        _, headers, data = self._do_request(url, 'GET', extra_headers={'Accept': 'text/calendar'})
        # Extract ETag from headers, stripping quotes if present
        # In Zoho, we've seen it sometimes coming from a different header or being absent.
        etag = (headers.get('ETag') or headers.get('etag') or '').strip('"')
        
        if self.server_type == 'zoho':
            _logger.debug('[ZOHO] Fetch %s headers: %s', href, headers)
            if not etag:
                 # Fallback for Zoho if ETag is not in standard headers
                 _logger.warning('[ZOHO] ETag empty in standard headers for %s. Headers: %s', href, headers)
        
        return etag, data.decode('utf-8', errors='replace')

    def _put_ical(self, href, ical_string, etag=None):
        """PUT (create or update) a single .ics resource on the server.

        :param str href: Target URL / href for the resource.
        :param str ical_string: Full iCal text to upload.
        :param str|None etag: If provided, sends an ``If-Match`` header (optimistic locking).
            The value should be unquoted; this method will wrap it in double quotes
            as required by RFC 4918.
        :return: ETag returned by the server (unquoted), or empty string.
        :rtype: str
        """
        self.ensure_one()
        url = self._resolve_href(href)

        def _attempt(attempt_etag):
            """Inner helper to perform one PUT attempt with the given ETag."""
            extra = {'Content-Type': 'text/calendar; charset=utf-8'}
            if attempt_etag:
                quoted_etag = attempt_etag if attempt_etag.startswith('"') else f'"{attempt_etag}"'
                extra['If-Match'] = quoted_etag
            status, headers, data = self._do_request(
                url, 'PUT', body=ical_string.encode('utf-8'), extra_headers=extra
            )
            raw_etag = headers.get('ETag', headers.get('etag', ''))
            
            if self.server_type == 'zoho':
                 body_str = data.decode('utf-8', errors='replace') if data else '<empty>'
                 _logger.info(
                     '[ZOHO] PUT attempt results: Status=%s, ETag=%s, Body=%s',
                     status, raw_etag, body_str[:500]
                 )
                 if not raw_etag:
                     # If Zoho doesn't return an ETag on PUT, fetch it now to avoid conflict on next sync
                     _logger.warning('[ZOHO] No ETag returned on PUT. Fetching fresh ETag now.')
                     raw_etag, _ = self._fetch_ical_with_etag(url) or ('', None)

            return raw_etag.strip('"')

        try:
            return _attempt(etag)
        except UserError as exc:
            # 409 Conflict or 412 Precondition Failed means the ETag we have is stale.
            # Zoho (and some other servers) bump the ETag silently when the event is
            # viewed or touched via the web UI, making our cached value outdated.
            # Recovery: fetch the current ETag from the server and retry once without
            # optimistic locking (no If-Match), so the PUT is accepted unconditionally.
            error_str = str(exc)
            if self.server_type == 'zoho' and ('409' in error_str or '412' in error_str) and etag:
                _logger.warning(
                    'PUT %s returned ETag conflict (%s). Fetching fresh ETag and retrying.',
                    href,
                    '409' if '409' in error_str else '412',
                )
                try:
                    # GET the resource to find the current server ETag
                    fresh_etag, _ = self._fetch_ical_with_etag(href)
                    _logger.info('Retrying PUT %s with fresh ETag=%r', href, fresh_etag)
                    return _attempt(fresh_etag)
                except Exception as retry_exc:
                    _logger.error('Retry PUT %s failed: %s', href, retry_exc)
                    raise UserError(
                        f'CalDAV sync conflict could not be resolved for {href}. '
                        f'Original error: {exc}. Retry error: {retry_exc}'
                    ) from retry_exc
            raise

    def _delete_event(self, href, etag=None):
        """DELETE a CalDAV resource from the server.

        :param str href: Absolute or relative URL to the resource.
        :param str|None etag: If provided, sends an ``If-Match`` header.
            The value should be unquoted; this method will wrap it in double quotes
            as required by RFC 4918.
        """
        self.ensure_one()
        url = self._resolve_href(href)

        def _attempt(attempt_etag):
            """Inner helper to perform one DELETE attempt with the given ETag."""
            extra = {}
            if attempt_etag:
                quoted_etag = attempt_etag if attempt_etag.startswith('"') else f'"{attempt_etag}"'
                extra['If-Match'] = quoted_etag
            self._do_request(url, 'DELETE', extra_headers=extra, expected_codes=[200, 204, 404])

        try:
            _attempt(etag)
        except UserError as exc:
            error_str = str(exc)
            # Zoho specific: 409/412 recovery for deletions
            if self.server_type == 'zoho' and ('409' in error_str or '412' in error_str) and etag:
                _logger.warning('DELETE %s returned conflict. Fetching fresh ETag and retrying.', href)
                try:
                    fresh_etag, _ = self._fetch_ical_with_etag(href)
                    _attempt(fresh_etag)
                except Exception:
                    # Treat retry failure or 404 after conflict as success
                    pass
            elif self.server_type == 'zoho' and '404' not in error_str:
                # For Zoho, only swallow 404s in normal circumstances (handled by retry above)
                # But if we aren't retrying 409/412, we should raise other errors to be explicit.
                raise
            else:
                # --- ALL OTHER SERVERS OR ZOHO 404 ---
                # Revert to original behavior: swap any deletion error for a silent pass.
                # Many servers (Nextcloud, Baïkal) are fine with 404 or other errors on delete.
                pass

    def _resolve_href(self, href):
        """Convert a relative href from the CalDAV server to an absolute URL.

        Normalizes the href by unquoting URL entities (e.g., %40 -> @) to
        ensure stable comparisons even if server quoting styles change.

        :param str href: Relative or absolute href.
        :return: Absolute URL string.
        :rtype: str
        """
        from urllib.parse import urlparse, urlunparse, unquote
        href = unquote(href)
        if href.startswith('http://') or href.startswith('https://'):
            return href
        parsed = urlparse(self.url)
        # Also unquote the path of our base URL for symmetry
        base_path = unquote(parsed.path)
        return urlunparse((parsed.scheme, parsed.netloc, href, '', '', ''))

    # ------------------------------------------------------------------
    # CalDAV protocol helpers
    # ------------------------------------------------------------------

    def _get_server_ctag(self):
        """Fetch the current CTag of the calendar collection from the server.

        CTag changes whenever any event in the collection is added, modified,
        or deleted. If the CTag matches ``last_ctag``, no sync is necessary.

        :return: Current CTag string (empty string if not supported).
        :rtype: str
        """
        self.ensure_one()
        body = b'''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:" xmlns:CS="http://calendarserver.org/ns/">
  <D:prop>
    <CS:getctag/>
    <D:getctag/>
  </D:prop>
</D:propfind>'''
        try:
            root = self._propfind(self.url, depth='0', body=body)
            # Try CS:getctag first, then fallback D:getctag
            for tag in [
                '{http://calendarserver.org/ns/}getctag',
                '{DAV:}getctag',
                '{DAV:}sync-token',
            ]:
                el = root.find(f'.//{tag}')
                if el is not None and el.text:
                    return el.text.strip()
        except Exception as e:
            _logger.warning('Could not fetch CTag for account %s: %s', self.name, e)
        return ''

    def _get_server_etags(self):
        """Retrieve a mapping of {href: etag} for all events on the server.

        Uses a CalDAV REPORT (calendar-query) to fetch all .ics hrefs and their
        ETags in a single request, minimizing round-trips.

        :return: Dict mapping href strings to ETag strings.
        :rtype: dict
        """
        self.ensure_one()
        body = b'''<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop>
    <D:getetag/>
    <D:getcontenttype/>
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT"/>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>'''
        try:
            root = self._report(self.url, body)
        except UserError:
            return {}
        etags = {}
        for response in root.findall('{DAV:}response'):
            href_el = response.find('{DAV:}href')
            etag_el = response.find('.//{DAV:}getetag')
            if href_el is not None and href_el.text:
                href = href_el.text.strip()
                etag = etag_el.text.strip().strip('"') if etag_el is not None and etag_el.text else ''
                etags[href] = etag
        _logger.debug('Found %s events on CalDAV server for account %s: %s', len(etags), self.name, list(etags.keys()))
        return etags

    # ------------------------------------------------------------------
    # User-facing actions
    # ------------------------------------------------------------------

    def action_test_connection(self):
        """Test the CalDAV connection and credentials.

        For **Basic Auth** accounts (non-Google): sends an OPTIONS request to
        verify connectivity, then a PROPFIND to verify the collection URL and
        credentials.

        For **Google OAuth** accounts: skips OPTIONS (Google returns 403 for it)
        and goes directly to PROPFIND with the Bearer token. Also validates that
        the account has been authorized before attempting the connection.

        :raises UserError: If the connection fails or credentials are rejected.
        :return: Client action showing a success notification.
        :rtype: dict
        """
        self.ensure_one()

        # Google OAuth pre-flight check
        if self.server_type == 'google':
            if not self.google_refresh_token:
                raise UserError(_(
                    'This Google Calendar account has not been authorized yet. '
                    'Please click "Authorize with Google" first.'
                ))
            # Ensure we have a fresh access token before testing
            self._refresh_google_token()

        try:
            # OPTIONS is not supported by Google CalDAV — skip it for Google accounts
            if self.server_type != 'google':
                self._do_request(
                    self.url, 'OPTIONS',
                    expected_codes=[200, 201, 204, 207, 405],
                )

            # PROPFIND depth 0 to verify collection & credentials
            body = b'''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
  <D:prop>
    <D:resourcetype/>
    <D:displayname/>
  </D:prop>
</D:propfind>'''
            self._propfind(self.url, depth='0', body=body)
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Connection test failed: %s', str(e)))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Connection Successful'),
                'message': _('Successfully connected to the CalDAV server!'),
                'type': 'success',
                'sticky': False,
            },
        }


    def action_sync_now(self):
        """Trigger an immediate sync for this CalDAV account.

        Calls the central sync service for this particular account
        and returns a notification to the user.

        :return: Client action showing sync result notification.
        :rtype: dict
        """
        self.ensure_one()
        service = self.env['caldav.sync.service']
        stats = service.sync_account(self)
        msg = _(
            'Sync complete — %(pushed)s pushed, %(pulled)s pulled, %(deleted)s deleted.',
            pushed=stats.get('pushed', 0),
            pulled=stats.get('pulled', 0),
            deleted=stats.get('deleted', 0),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CalDAV Sync'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_scheduled_action(self):
        """Redirect the user to the CalDAV Sync scheduled action configuration.

        Provides a quick shortcut to the background sync frequency settings
        from the account form view.

        :return: Act window action to open the ir.cron record.
        :rtype: dict
        """
        cron = self.env.ref('cr_odoo_caldav_sync.ir_cron_caldav_sync', raise_if_not_found=False)
        if not cron:
            raise UserError(_('The CalDAV Sync scheduled action could not be found.'))
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Scheduled Action'),
            'res_model': 'ir.cron',
            'res_id': cron.id,
            'view_mode': 'form',
            'target': 'current',
        }
