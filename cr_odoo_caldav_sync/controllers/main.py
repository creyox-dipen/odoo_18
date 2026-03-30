# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import json
import logging
import urllib.parse
import urllib.request
import urllib.error
from datetime import timedelta

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_CALENDAR_CALDAV_BASE = 'https://apidata.googleusercontent.com/caldav/v2/'


class CalDAVGoogleOAuthController(http.Controller):
    """Handles the Google OAuth 2.0 callback for CalDAV account authorization.

    When the user clicks 'Authorize with Google' on a CalDAV account, they are
    redirected to Google's consent screen. After approval, Google calls this
    controller with an authorization code. The controller exchanges the code for
    access and refresh tokens and stores them on the CalDAV account.
    """

    @http.route('/caldav/google/callback', type='http', auth='user', website=False)
    def google_oauth_callback(self, code=None, state=None, error=None, **kwargs):
        """Handle the redirect callback from Google's OAuth 2.0 consent screen.

        :param str code: Authorization code returned by Google on success.
        :param str state: Account ID passed as state in the original auth request.
        :param str error: Error string returned by Google if the user denied access.
        :return: HTTP redirect back to the CalDAV account form in Odoo.
        :rtype: werkzeug.wrappers.Response
        """
        if error:
            _logger.warning('Google OAuth callback returned error: %s', error)
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')

        if not code or not state:
            _logger.error('Google OAuth callback: missing code or state parameter.')
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')

        try:
            account_id = int(state)
        except (ValueError, TypeError):
            _logger.error('Google OAuth callback: invalid state value "%s".', state)
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')

        account = request.env['caldav.account'].sudo().browse(account_id)
        if not account.exists() or account.server_type != 'google':
            _logger.error('Google OAuth callback: account id=%s not found or not Google type.', account_id)
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')

        icp = request.env['ir.config_parameter'].sudo()
        client_id = icp.get_param('cr_odoo_caldav_sync.google_client_id')
        client_secret = icp.get_param('cr_odoo_caldav_sync.google_client_secret')
        base_url = icp.get_param('web.base.url', '').rstrip('/')
        redirect_uri = f'{base_url}/caldav/google/callback'

        # Exchange the authorization code for tokens
        post_data = urllib.parse.urlencode({
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }).encode('utf-8')

        req = urllib.request.Request(GOOGLE_TOKEN_URL, data=post_data, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            _logger.error('Google token exchange failed for account %s: %s', account.name, body)
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')
        except Exception as e:
            _logger.error('Google token exchange error for account %s: %s', account.name, e)
            return request.redirect('/odoo/action-cr_odoo_caldav_sync.action_caldav_account')

        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = int(token_data.get('expires_in', 3600))

        if not refresh_token:
            _logger.warning(
                'Google did not return a refresh_token for account %s. '
                'This may happen if the account was already authorized. '
                'Re-authorizing with prompt=consent should fix this.',
                account.name
            )

        write_vals = {
            'google_access_token': access_token,
            'google_access_token_expiry': fields.Datetime.now() + timedelta(seconds=expires_in),
        }
        if refresh_token:
            write_vals['google_refresh_token'] = refresh_token

        # Always set the correct Google Calendar v2 CalDAV URL for OAuth accounts
        # The legacy www.google.com/calendar/dav/... URL does NOT work with OAuth Bearer tokens
        owner_email = account.user_id.email or account.user_id.login or ''
        if owner_email:
            correct_url = f'{GOOGLE_CALENDAR_CALDAV_BASE}{owner_email}/events/'
            if account.url != correct_url:
                write_vals['url'] = correct_url
                _logger.info('Auto-set Google CalDAV URL to %s for account "%s".', correct_url, account.name)

        account.write(write_vals)
        _logger.info(
            'Google OAuth 2.0 authorization successful for account "%s" (id=%s). '
            'Refresh token stored: %s',
            account.name, account.id, bool(refresh_token)
        )

        # Redirect back to the list of CalDAV accounts
        # The user can click on their account to see the green "Authorized" banner
        return request.redirect(f'/odoo/action-cr_odoo_caldav_sync.action_caldav_account')
