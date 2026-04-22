# CalDAV Sync — Nextcloud Testing Guide

> **Module:** CalDAV Sync for Odoo 18  
> **Provider:** TheGood.Cloud (Nextcloud)  
> **Last Updated:** April 2026

---

## Part 1 — Nextcloud Account Setup

### Step 1 — Sign Up

1. Go to **https://nextcloud.com/sign-up**
2. Click **"change provider"** dropdown
3. Select **"TheGood.Cloud"** (avoid Tab.Digital — it has Cloudflare blocking)
4. Enter your email address
5. Check **"I agree to the Terms of service"**
6. Click **"Sign up →"**
7. **Immediately** open your email inbox and click the verification link

> ⚠️ If you don't verify immediately, the account gets disabled and you cannot re-register with the same email.

---

### Step 2 — Log In to Nextcloud

- Login URL: **https://use22.thegood.cloud**
- Enter your email and password

---

### Step 3 — Create a Test Calendar

1. Click **"Calendar"** in the top navigation bar
2. In the left sidebar, click **"+"** next to **Calendars**
3. Type `OdooTest` and press **Enter**
4. Hover over the `OdooTest` calendar → click **"⋯"** (three dots)
5. Click **"Copy private link"**
6. Save the URL — it will look like:
   ```
   https://use22.thegood.cloud/remote.php/dav/calendars/YOUR_EMAIL/odootest/
   ```

---

### Step 4 — Generate an App Password

1. Click your **profile icon** (top right corner)
2. Click **"Settings"**
3. In the left menu, click **"Security"**
4. Scroll down to **"App passwords"** section
5. In the text field, type `OdooSync`
6. Click **"Create new app password"**
7. **Copy the generated password immediately** — it is shown only once

> Example format: `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`

---

## Part 2 — Odoo CalDAV Account Configuration

### Step 5 — Open CalDAV Settings in Odoo

1. Login to your Odoo instance
2. Go to **Settings** (top menu)
3. Search for **"CalDAV"** in the search bar
4. Click **"Manage CalDAV Accounts"**

---

### Step 6 — Create a New CalDAV Account

Click **"New"** and fill in the following fields:

| Field | Value |
|---|---|
| **Account Name** | `Nextcloud Test` |
| **Server Type** | `Nextcloud` |
| **URL** | CalDAV URL from Step 3 |
| **Username** | Your Nextcloud email (e.g. `you@gmail.com`) |
| **Password** | App Password from Step 4 |
| **Owner** | Your Odoo user |
| **Sync Direction** | `Bidirectional` |
| **Send Invitation Emails** | ✅ Enabled (if you want email notifications) |

Click **"Save"**

---

### Step 7 — Test the Connection

1. Click the **"Test Connection"** button in the form header
2. Expected result: ✅ **"Connection Successful"** notification

**If you get HTTP 403 error code 1010:**
- This means Cloudflare is blocking the request
- Switch to a different provider (not Tab.Digital)
- See Part 3 — Troubleshooting

---

## Part 3 — Troubleshooting

### Error: HTTP 403 — error code 1010

**Cause:** Cloudflare is blocking automated requests (common with Tab.Digital)

**Fix:** Use **TheGood.Cloud** instead of Tab.Digital as your Nextcloud provider

---

### Error: Account Disabled

**Cause:** Email was not verified after sign-up

**Fix:**
- You cannot re-register with the same email if the account exists
- Use a different email address and sign up again
- Or contact TheGood.Cloud support to re-enable the account

---

### Events Not Syncing

| Symptom | Fix |
|---|---|
| Events not pushing to Nextcloud | Check sync direction is not set to `CalDAV → Odoo only` |
| Events not pulling to Odoo | Click **Sync Now** manually, check Sync Logs |
| Duplicate events | Check if same UID exists in both systems |
| Recurring events not syncing | Run `pip install vobject --break-system-packages` on the Odoo server |

---

### Check Sync Logs

After any sync, go to:
**CalDAV Account form → click "Sync Logs" stat button**

Check:
- **Status**: Success / Partial / Failed
- **Pushed / Pulled / Deleted** counts
- **Details** field for error messages

---

## Part 4 — Quick Reference

### Important URLs

| Purpose | URL |
|---|---|
| Nextcloud Sign Up | https://nextcloud.com/sign-up |
| Nextcloud Login | https://use22.thegood.cloud |
| Nextcloud Calendar | https://use22.thegood.cloud/apps/calendar |
| Nextcloud Settings | https://use22.thegood.cloud/settings/user |
| Nextcloud Security (App Passwords) | https://use22.thegood.cloud/settings/user/security |

---

### CalDAV URL Format

```
https://use22.thegood.cloud/remote.php/dav/calendars/YOUR_EMAIL/CALENDAR_SLUG/
```

**Example:**
```
https://use22.thegood.cloud/remote.php/dav/calendars/dipen.creyox@gmail.com/odoo-test-calendar/
```

---

### Credentials Used in Testing

| Field | Value |
|---|---|
| **Nextcloud Provider** | TheGood.Cloud |
| **Nextcloud Login URL** | https://use22.thegood.cloud |
| **Nextcloud Username** | `dipen.creyox@gmail.com` |
| **CalDAV Calendar URL** | `https://use22.thegood.cloud/remote.php/dav/calendars/dipen.creyox@gmail.com/odoo-test-calendar/` |
| **App Password** | Generate fresh one from Security settings |

> ⚠️ Always generate a **new App Password** from Nextcloud Security settings. Never use your main account password.

---

### Configuration Checklist

- [ ] Nextcloud account created and email verified
- [ ] `OdooTest` calendar created in Nextcloud
- [ ] CalDAV URL copied from calendar settings
- [ ] App Password generated from Security settings
- [ ] CalDAV Account created in Odoo with correct credentials
- [ ] Test Connection passes ✅
