# Google Calendar OAuth 2.0 Setup Guide

This guide provides step-by-step instructions for configuring Google Cloud Console and Odoo to sync calendar events via OAuth 2.0.

## Phase 1: Google Cloud Console Configuration

### 1.1 Create a New Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on the project dropdown in the top bar and select **New Project**.
3. Name your project (e.g., `Odoo CalDAV Sync`) and click **Create**.

### 1.2 Enable Required APIs
You MUST enable **two** separate APIs:
1. Search for **Google Calendar API** and click **Enable**.
2. Search for **CalDAV API** and click **Enable**.
   *Note: If you skip the CalDAV API, you will get a 403 Access Not Configured error.*

### 1.3 Configure OAuth Consent Screen
1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** as the User Type and click **Create**.
3. **App Information**:
   - **App name**: `Odoo CalDAV Sync`
   - **User support email**: Your Gmail address.
   - **Developer contact info**: Your Gmail address.
4. Click **Save and Continue**.
5. **Scopes**:
   - Click **Add or Remove Scopes**.
   - Search for `calendar` and check `.../auth/calendar` (See, edit, share, and permanently delete all the calendars you can access using Google Calendar).
   - Click **Update** and then **Save and Continue**.
6. **Test Users**:
   - Click **Add Users**.
   - Enter your Gmail address (and any other accounts you want to test with).
   - Click **Save and Continue**.
7. Click **Back to Dashboard**.

### 1.4 Create OAuth 2.0 Client ID
1. Go to **APIs & Services > Credentials**.
2. Click **+ Create Credentials** and select **OAuth client ID**.
3. **Application type**: Select **Web application**.
4. **Name**: `Odoo CalDAV Client`.
5. **Authorized redirect URIs**:
   - Click **+ Add URI**.
   - Enter your Odoo callback URL. It must be in this format:  
     `http://<YOUR_DOMAIN_OR_IP>:<PORT>/caldav/google/callback`  
     *Example: `http://localhost:8042/caldav/google/callback`*
6. Click **Create**.
7. **Important**: Copy your **Client ID** and **Client Secret**. You will need these for the Odoo settings.

---

## Phase 2: Odoo Configuration

### 2.1 Set System Parameters
1. In Odoo, go to **Settings > Technical > System Parameters**.
2. Find the key `web.base.url`.
3. Ensure its value matches the domain and port used in the Google Redirect URI (e.g., `http://localhost:8042`).

### 2.2 Configure module Settings
1. Go to **Settings > CalDAV Sync**.
2. Enable **Enable CalDAV Sync**.
3. Paste the **Google Client ID** and **Google Client Secret** obtained in Phase 1.
4. Click **Save**.

---

## Phase 3: User Account Authorization

### 3.1 Create CalDAV Account
1. Go to **Calendar > Configuration > CalDAV Accounts**.
2. Click **New**.
3. **Account Name**: `My Google Calendar`.
4. **Server Type**: Select **Google Calendar**.
5. **Owner**: Select your user.
6. Click **Save**. A yellow banner will appear stating the account is not yet authorized.

### 3.2 Perform Authorization
1. Click the **Authorize with Google** button in the header.
2. You will be redirected to Google. Select your Google account.
3. If you see a "Google hasn't verified this app" warning, click **Advanced** and then **Go to <App Name> (unsafe)**.
4. Click **Continue/Allow** to grant permissions.
5. You will be redirected back to Odoo.

### 3.3 Verify and Sync
1. Open your CalDAV Account record.
2. A green banner should now show: `✓ Authorized (Token Valid)`.
3. The **CalDAV Calendar URL** should have been automatically updated to:  
   `https://apidata.googleusercontent.com/caldav/v2/<your-email>/events/`
4. Click **Test Connection**. It should succeed.
5. Click **Sync Now** to start downloading/uploading events.
