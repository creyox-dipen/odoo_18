# Google Calendar OAuth 2.0 Setup Guide

This guide provides step-by-step instructions for configuring Google Cloud Console and Odoo to sync calendar events via OAuth 2.0.

---

## Phase 1: Google Cloud Console Configuration

### 1.1 Create a New Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on the **Project Dropdown** at the top left (next to the "Google Cloud" logo).
3. In the "Select a project" window, click the **New Project** button at the top right.
4. **Project name**: Enter something descriptive like `Odoo CalDAV Sync`.
5. Click the **Create** button at the bottom.
6. Wait for the notification and ensure the project is selected in the top dropdown.

### 1.2 Enable Required APIs

You MUST enable **two** separate APIs for this sync to work:

1. Click the **Navigation Menu** (three horizontal lines ≡) at the top left.
2. Go to **APIs & Services > Library**.
3. In the search box "Search for APIs & Services", type `Google Calendar API`.
4. Click on the first result and click the blue **Enable** button.
5. Go back to the **Library** (Navigation Menu > APIs & Services > Library).
6. Search for `CalDAV API`.
7. Click on the result and click the blue **Enable** button.
   _Note: If you skip the CalDAV API, you will get a "403 Access Not Configured" error in Odoo._

### 1.3 Configure OAuth Consent Screen

1. Go to **Navigation Menu > APIs & Services > OAuth consent screen**.
2. **User Type**: Select **External**.
3. Click the **Create** button.
4. **Step 1: App Information**:
   - **App name**: `Odoo CalDAV Sync`
   - **User support email**: Choose your email from the dropdown.
   - **Developer contact information**: Enter your email address.
   - Click **Save and Continue** at the bottom.
5. **Step 2: Scopes**:
   - Go to **Data Access** Menu.
   - Click the **Add or Remove Scopes** button.
   - A sidebar will open. In the "Filter" box, type `Calendar`.
   - Find the scope and check the box for: `.../auth/calendar` (See, edit, share, and permanently delete all calendars).
   - Scroll to the bottom of the sidebar and click **Update**.
   - Back on the Scopes page, scroll down and click **Save and Continue**.
6. **Step 3: Test Users**:
   - Go to **Audience** menu.
   - Under the "Test users" section, click the **+ Add Users** button.
   - Enter your Gmail address (the one you will use to sync).
   - Click the **Add** button.
   - Click **Save and Continue** at the bottom.
7. **Step 4: Summary**:
   - Review your settings and click **Back to Dashboard** at the bottom.

### 1.4 Create OAuth 2.0 Client ID Credentials

1. Go to **Navigation Menu > APIs & Services > Credentials**.
2. Click the **+ Create Credentials** button at the top and select **OAuth client ID**.
3. **Application type**: From the dropdown, select **Web application**.
4. **Name**: `Odoo CalDAV Client`.
5. **Authorized redirect URIs**:
   - Scroll down to the bottom section and click the **+ Add URI** button.
   - Enter your Odoo callback URL exactly. It must follow this pattern:  
     `http://<YOUR_DOMAIN_OR_IP>:<PORT>/caldav/google/callback`  
     _Example: `http://localhost:8042/caldav/google/callback`_
6. Click the **Create** button.
7. A window will appear with your **Client ID** and **Client Secret**.
   - **Important**: Copy both values now. You will need to paste them into Odoo's settings.

---

## Phase 2: Odoo Global Configuration

### 2.1 Set System Parameters

1. In Odoo, go to **Settings > Technical > System Parameters** (ensure Developer Mode is ON).
2. Use the search box to find the key `web.base.url`.
3. Check its value. It MUST match the protocol, domain, and port you used in the Google Redirect URI (e.g., `http://localhost:8042`).

### 2.2 Configure Module Settings

1. Go to **Settings > CalDAV Sync**.
2. Scroll to the "Google Calendar Integration" section.
3. Paste the **Google Client ID** and **Google Client Secret** you copied from Phase 1.
4. Click the **Save** button in the header.

---

## Phase 3: User Account Authorization

### 3.1 Create CalDAV Account Record

1. Go to **Calendar > Configuration > CalDAV Accounts**.
2. Click the **New** button.
3. **Account Name**: `My Google Calendar`.
4. **Server Type**: Select **Google Calendar**.
5. **Owner**: Select your internal Odoo user.
6. Click **Save**. Initially, you will see a yellow banner: _"This Google Calendar account has not been authorized yet..."_

### 3.2 Perform Authorization Flow

1. Click the **Authorize with Google** button in the top status bar.
2. A new window will open to Google's sign-in page. Select your Google account.
3. If you see "Google hasn't verified this app":
   - Click the **Advanced** link at the bottom left.
   - Click **Go to Odoo CalDAV Sync (unsafe)**.
4. On the permission screen, check the box for "See, edit, share, and permanently delete all calendars..."
5. Click **Continue**.
6. You will be redirected back to your Odoo account form.

### 3.3 Verify Verification Status

1. Your account form should now show a green banner: `✓ Authorized (Token Valid)`.
2. The **CalDAV Calendar URL** field will have been automatically populated for you.
3. Click the **Test Connection** button.
4. If successful, you will see a notification: _"Successfully connected to the CalDAV server!"_
5. Click **Sync Now** to start your first synchronization.
