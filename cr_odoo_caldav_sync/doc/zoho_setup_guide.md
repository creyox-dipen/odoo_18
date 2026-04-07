# Zoho Calendar CalDAV Sync Setup Guide

This guide provides step-by-step instructions for syncing your Zoho Calendar with Odoo using the CalDAV protocol.

## Prerequisites

1.  **Zoho Account**: A valid Zoho account (e.g., mail.zoho.in or mail.zoho.com).
2.  **CalDAV Enabled**: CalDAV must be allowed for your Zoho account (enabled by default for most accounts).

## Step 1: Generate an App-Specific Password (MANDATORY)

Zoho requires an App-Specific Password for third-party integrations like Odoo. **Your regular login password will not work.**

1.  Log in to your **Zoho Accounts** dashboard (accounts.zoho.in).
2.  Go to **Security** > **App Passwords**.
3.  Click **Generate New Password**.
4.  Enter an App Name (e.g., "Odoo CalDAV Sync") and click **Generate**.
5.  **Copy the password.** You will need this for the Odoo setup.

## Step 2: Configure Zoho Calendar in Odoo

1.  Log in to Odoo as an Administrator or with Calendar access.
2.  Go to **Calendar** > **Reporting** (or **Configuration**) > **CalDAV Accounts**.
3.  Click **Create** or edit your existing Zoho account.
4.  Set the following fields:
    *   **Name**: A descriptive name (e.g., "Zoho Calendar")
    *   **Server Type**: Select **Zoho Calendar**.
    *   **Username**: Your full Zoho email address (e.g., `user@zoho.in`).
    *   **Password**: Paste the **App-Specific Password** from Step 1.
    *   **Sync Direction**: Select **Bidirectional** (recommended).

## Step 3: Find and Set your CalDAV URL

1.  Log in to your **Zoho Calendar** web interface (calendar.zoho.in).
2.  On the left sidebar, find the calendar you wish to sync. 
3.  Click the **... (More options)** ellipsis next to the calendar name.
4.  Select **Settings** or **Edit Calendar**.
5.  In the settings popup, go to the **CalDAV** tab.
6.  Look for the **CalDAV URL**. It typically looks like:
    `https://calendar.zoho.in/caldav/zz08021230899b4daf8781e216.../events/`
7.  **Copy this URL** and paste it into the **CalDAV URL** field in Odoo.

## Step 4: Finalize and Test Sync

1.  In Odoo, click **Save**.
2.  Click the **Sync Now** button to perform the initial synchronization.
3.  Check the **CalDAV Sync Logs** tab (or menu) to monitor the progress.

### Important Note on Synchronization

*   **Initial Pull**: Odoo will pull all upcoming events from Zoho.
*   **Initial Push**: Odoo will push any upcoming local events to Zoho.
*   **Conflict Handling**: If an ETag conflict occurs (e.g., you viewed the event in Zoho), Odoo is configured to automatically recover and retry the update once.

## Troubleshooting

*   **Authentication Failed**: Double-check that you are using an **App-Specific Password**, not your regular login password.
*   **404 Not Found**: Verify that the CalDAV URL is copied exactly from your Zoho Calendar settings.
*   **Sync Not Reflecting**: Ensure that the **Sequence** and **Last-Modified** headers are being sent. Our implementation automatically handles this for Zoho.
