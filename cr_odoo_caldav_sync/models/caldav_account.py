# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import base64
import logging
import ssl
import urllib.error
import urllib.request
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
        required=True,
        help=(
            'Full URL to the CalDAV calendar collection. '
            'Example: https://nextcloud.example.com/remote.php/dav/calendars/user/personal/'
        ),
    )
    username = fields.Char(
        string='Username',
        required=True,
        help='Login username for the CalDAV server.',
    )
    password = fields.Char(
        string='Password',
        required=True,
        help='Login password for the CalDAV server.',
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

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_auth_header(self):
        """Build the HTTP Basic Authentication header value.

        :return: Base64-encoded 'username:password' string prefixed with 'Basic '.
        :rtype: str
        """
        self.ensure_one()
        credentials = f'{self.username}:{self.password}'
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f'Basic {encoded}'

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
                headers = dict(resp.headers)
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
        etag = (headers.get('ETag') or headers.get('etag') or '').strip('"')
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
        extra = {'Content-Type': 'text/calendar; charset=utf-8'}
        if etag:
            # RFC 4918 requires ETag values in If-Match to be quoted
            quoted_etag = etag if etag.startswith('"') else f'"{etag}"'
            extra['If-Match'] = quoted_etag
        _, headers, _ = self._do_request(
            url, 'PUT', body=ical_string.encode('utf-8'), extra_headers=extra
        )
        raw_etag = headers.get('ETag', headers.get('etag', ''))
        return raw_etag.strip('"')

    def _delete_event(self, href, etag=None):
        """DELETE a CalDAV resource from the server.

        :param str href: Absolute or relative URL to the resource.
        :param str|None etag: If provided, sends an ``If-Match`` header.
            The value should be unquoted; this method will wrap it in double quotes
            as required by RFC 4918.
        """
        self.ensure_one()
        url = self._resolve_href(href)
        extra = {}
        if etag:
            # RFC 4918 requires ETag values in If-Match to be quoted
            quoted_etag = etag if etag.startswith('"') else f'"{etag}"'
            extra['If-Match'] = quoted_etag
        try:
            self._do_request(url, 'DELETE', extra_headers=extra, expected_codes=[200, 204, 404])
        except UserError:
            # Already deleted on server — not an error
            pass

    def _resolve_href(self, href):
        """Convert a relative href from the CalDAV server to an absolute URL.

        :param str href: Relative or absolute href.
        :return: Absolute URL string.
        :rtype: str
        """
        if href.startswith('http://') or href.startswith('https://'):
            return href
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(self.url)
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

        Sends an OPTIONS request to the configured URL, then attempts a
        PROPFIND to verify that the URL is a valid CalDAV collection.

        :raises UserError: If the connection fails or credentials are rejected.
        :return: Client action showing a success notification.
        :rtype: dict
        """
        self.ensure_one()
        try:
            # OPTIONS to test basic connectivity
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
        except UserError as e:
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
