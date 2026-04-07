# iCloud Calendar — CalDAV Sync Setup Guide
### Creyox Technologies · Odoo CalDAV Sync Module

---

## Prerequisites

Before you begin, make sure you have:
- An active **Apple ID** with iCloud enabled
- **Two-Factor Authentication (2FA)** enabled on your Apple ID (required by Apple for app-specific passwords)
- Admin access to your Odoo instance
- The **cr_odoo_caldav_sync** module installed and enabled in Odoo

---

## Step 1 — Generate an App-Specific Password

iCloud **does not allow** your regular Apple ID password to be used with CalDAV clients. You must generate a dedicated app-specific password.

1. Open a browser and go to: **https://appleid.apple.com**
2. Sign in with your Apple ID email and password
3. Complete the 2FA verification if prompted
4. Under the **Sign-In and Security** section, click **App-Specific Passwords**
5. Click the **+ (plus)** button or **Generate an App-Specific Password**
6. Enter a label such as `Odoo CalDAV` and click **Create**
7. Apple will display the password in the format: `xxxx-xxxx-xxxx-xxxx`
8. **Copy this password immediately** — it will not be shown again

> ⚠️ **Important:** This app-specific password is what you will use as the **Password** field in Odoo. Never use your main Apple ID password.

---

## Step 2 — Find Your iCloud Account ID

Your CalDAV URL requires a numeric **account ID** that is unique to your Apple ID. Follow these steps to find it.

### Option A — Using Terminal (Mac)

Open **Terminal** and run the following command. Replace the email and password with your own:

```bash
curl -u "your@apple.com:xxxx-xxxx-xxxx-xxxx" \
  -X PROPFIND \
  -H "Depth: 0" \
  -H "Content-Type: application/xml" \
  --data '<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/></D:prop></D:propfind>' \
  https://caldav.icloud.com/
```

Or as a single line:

```bash
curl -u "your@apple.com:xxxx-xxxx-xxxx-xxxx" -X PROPFIND -H "Depth: 0" -H "Content-Type: application/xml" --data '<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:current-user-principal/></D:prop></D:propfind>' https://caldav.icloud.com/
```

Look for a response like this:

```xml
<current-user-principal>
  <href>/19083106969/principal/</href>
</current-user-principal>
```

The number in the href (e.g. `19083106969`) is your **iCloud Account ID**.

### Option B — Using Windows (Command Prompt or PowerShell)

If you are on Windows, you can use **curl** from Command Prompt:

```cmd
curl -u "your@apple.com:xxxx-xxxx-xxxx-xxxx" -X PROPFIND -H "Depth: 0" -H "Content-Type: application/xml" --data "<?xml version=\"1.0\"?><D:propfind xmlns:D=\"DAV:\"><D:prop><D:current-user-principal/></D:prop></D:propfind>" https://caldav.icloud.com/
```

---

## Step 3 — Find Your Calendar Collection URL

Once you have your account ID, list all available calendars to find the exact URL for the calendar you want to sync.

Run this command (replace `19083106969` with your account ID):

```bash
curl -u "your@apple.com:xxxx-xxxx-xxxx-xxxx" \
  -X PROPFIND \
  -H "Depth: 1" \
  -H "Content-Type: application/xml" \
  --data '<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:displayname/><D:resourcetype/></D:prop></D:propfind>' \
  https://caldav.icloud.com/19083106969/calendars/
```

You will get a response listing all your calendars. Look for entries with `<calendar/>` in their `resourcetype`. Example response:

```xml
<response>
  <href>/19083106969/calendars/7251F093-DBB1-4610-A43A-014716CFFE44/</href>
  <propstat>
    <prop>
      <displayname>Work</displayname>
      <resourcetype><collection/><calendar/></resourcetype>
    </prop>
  </propstat>
</response>

<response>
  <href>/19083106969/calendars/DB5153D8-61B0-4E9C-8E7F-207DA2135E4D/</href>
  <propstat>
    <prop>
      <displayname>Home</displayname>
      <resourcetype><collection/><calendar/></resourcetype>
    </prop>
  </propstat>
</response>
```

### Choosing the right calendar

| Calendar Name | Use for Sync? |
|---|---|
| **Home** | ✅ Yes — standard event calendar |
| **Work** | ✅ Yes — standard event calendar |
| Reminders | ❌ No — this is for the iOS Reminders app, not events |
| inbox | ❌ No — system collection, not a calendar |
| outbox | ❌ No — system collection, not a calendar |
| notification | ❌ No — system collection, not a calendar |

Your final **CalDAV Calendar URL** is:

```
https://caldav.icloud.com/<YOUR_ACCOUNT_ID>/calendars/<CALENDAR_UUID>/
```

Example:
```
https://caldav.icloud.com/19083106969/calendars/DB5153D8-61B0-4E9C-8E7F-207DA2135E4D/
```

---

## Step 4 — Enable CalDAV Sync in Odoo Settings

1. Log in to Odoo as an **Administrator**
2. Go to **Settings** from the main menu
3. Scroll down to find the **CalDAV Sync** section
4. Enable the **Enable CalDAV Sync** toggle
5. Click **Save**

> The CalDAV Accounts menu will now be visible under Settings.

---

## Step 5 — Create a CalDAV Account in Odoo

1. Go to **Settings → Technical → CalDAV Accounts**
   - Or click **Manage CalDAV Accounts** from the Settings page
2. Click **New** to create a new account
3. Fill in the fields as follows:

| Field | Value |
|---|---|
| **Account Name** | Any descriptive name, e.g. `Apple iCloud - Home` |
| **Server Type** | Select **Apple iCloud** |
| **CalDAV Calendar URL** | The full URL from Step 3, e.g. `https://caldav.icloud.com/19083106969/calendars/DB5153D8.../` |
| **Username** | Your Apple ID email, e.g. `your@apple.com` |
| **Password** | The app-specific password from Step 1, e.g. `xxxx-xxxx-xxxx-xxxx` |
| **Owner** | The Odoo user whose calendar should be synced |
| **Sync Direction** | `Bidirectional` (or `CalDAV → Odoo only` for safe initial testing) |
| **Send Invitation Emails** | Leave **disabled** unless you want Odoo to send invites on import |
| **Auto-create Contacts** | Enable if you want unknown attendees auto-created as Odoo contacts |

4. Click **Save**

---

## Step 6 — Test the Connection

1. On the CalDAV Account form, click the **Test Connection** button in the header
2. You should see a green notification: **"Connection Successful"**

If you see an error:
- **401 Unauthorized** → Wrong password. Make sure you are using the app-specific password, not your Apple ID password
- **403 Forbidden** → App-specific password may have expired. Generate a new one from Step 1
- **404 Not Found** → Wrong calendar URL. Re-run the curl command in Step 3 to find the correct path

---

## Step 7 — Run Your First Sync

1. On the CalDAV Account form, click **Sync Now**
2. A notification will appear showing how many events were pushed, pulled, and deleted
3. Go to **Calendar** in Odoo to verify events are appearing

> **Background sync:** After the first manual sync, the module automatically syncs every **15 minutes** via a scheduled cron job. You can adjust this interval by clicking the **Sync Schedule** button on the account form.

---

## Step 8 — Verify on Apple Devices

### On Mac
1. Open the **Calendar** app
2. Make sure iCloud calendars are visible in the left sidebar under the **iCloud** section
3. Press `Cmd + R` to refresh
4. Events pushed from Odoo should appear in the correct calendar (Home or Work)

### On iPhone / iPad
1. Open the **Calendar** app
2. Tap **Calendars** at the bottom
3. Make sure your iCloud calendar is checked
4. Pull down to refresh
5. Events pushed from Odoo should appear within 1–2 minutes

> ⚠️ **Note:** Make sure you create and edit events in the correct iCloud calendar (Home or Work), not in the **"On My Mac"** local calendar. Events in "On My Mac" are stored locally only and will not sync with Odoo.

---

## Sync Behaviour Reference

| Action | Result |
|---|---|
| Create event in Odoo → Sync | Event appears in Apple Calendar |
| Edit event in Odoo → Sync | Changes reflect in Apple Calendar |
| Edit single occurrence of recurring event in Odoo → Sync | Only that occurrence updates in Apple Calendar |
| Create event in Apple Calendar → Sync | Event appears in Odoo |
| Edit event in Apple Calendar → Sync | Changes reflect in Odoo |
| Delete event in Odoo → Sync | Event removed from Apple Calendar |
| Delete event in Apple Calendar → Sync | Event archived in Odoo |

---

## Troubleshooting

### Events not appearing after sync
- Check the **Sync Logs** on the CalDAV Account form (click the **Sync Logs** stat button)
- Make sure the event is in the correct iCloud calendar (the one whose URL is configured in Odoo)
- Try clicking **Sync Now** manually instead of waiting for the cron

### Event shows as "read only" in Apple Calendar
- This means the **ORGANIZER** in the pushed iCal does not match your Apple ID
- Make sure the **Username** field in the Odoo CalDAV account is set to your exact Apple ID email (e.g. `your@apple.com`)

### Recurring event updates all occurrences instead of one
- Make sure you are using the latest version of the module which supports `RECURRENCE-ID` overrides for iCloud

### App-specific password stopped working
- Apple app-specific passwords can be revoked. Go to **https://appleid.apple.com** → App-Specific Passwords and generate a new one, then update the Password field in your Odoo CalDAV account

---

## Security Notes

- The app-specific password is stored in Odoo's database. Ensure your Odoo instance uses HTTPS
- You can revoke the app-specific password at any time from **https://appleid.apple.com** without affecting your main Apple ID password
- It is recommended to create one app-specific password per integration (e.g. one for Odoo, one for Thunderbird) so they can be individually revoked

---

*Document generated by Creyox Technologies · cr_odoo_caldav_sync module*
