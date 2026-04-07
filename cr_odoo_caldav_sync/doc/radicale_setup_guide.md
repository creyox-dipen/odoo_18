# Radicale Setup Guide for CalDAV Synchronization

This guide provides step-by-step instructions for setting up **Radicale**, a simple and powerful open-source CalDAV/CardDAV server, to work with the Odoo CalDAV Sync module.

---

## 1. Installation

Radicale is built in Python. The easiest way to install it is via `pip`.

### On Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3-pip python3-setuptools
python3 -m pip install --upgrade radicale
```

### On Windows
1. Ensure Python is installed.
2. Open PowerShell or Command Prompt.
3. Run:
```powershell
python -m pip install --upgrade radicale
```

---

## 2. Basic Configuration

Radicale uses a configuration file typically located at:
- **Linux:** `/etc/radicale/config` or `~/.config/radicale/config`
- **Windows:** `%APPDATA%\radicale\config`

Create the folder and file if they don't exist. Add the following basic configuration:

```ini
[server]
# Listen on all interfaces, port 5232
hosts = 0.0.0.0:5232

[auth]
# Basic HTpasswd authentication
type = htpasswd
htpasswd_filename = /etc/radicale/users
htpasswd_encryption = plain

[storage]
# Where to store calendar data
filesystem_folder = /var/lib/radicale/collections
```

> [!NOTE]
> On Windows, adjust the paths for `htpasswd_filename` and `filesystem_folder` to valid local directories (e.g., `C:\Radicale\users` and `C:\Radicale\data`).

---

## 3. Creating Users

If using `htpasswd` authentication, you need to create the users file.

### Using `htpasswd` command (if installed):
```bash
htpasswd -c /etc/radicale/users myusername
```

### Manually:
Create the file and add entries in `username:password` format.
*Example:* `admin:admin123`

---

## 4. Starting the Server

Run Radicale from the terminal:
```bash
python3 -m radicale --debug
```

You can now access the web interface at `http://your-server-ip:5232` to verify it's running.

---

## 5. Integrating with Odoo

Once Radicale is running, follow these steps in Odoo:

1. Go to **Settings > CalDAV Synchronization > Accounts**.
2. Click **Create** and select **Server Type: Basic Auth (Generic CalDAV)**.
3. **URL:** Enter the full path to your Radicale calendar.
   - Format: `http://<your-server-ip>:5232/<username>/<calendar-id>/`
   - Example: `http://192.168.1.50:5232/admin/calendar/`
4. **Username & Password:** Enter the credentials created in Step 3.
5. Save and click **Test Connection**.

---

## 6. Troubleshooting

- **Firewall:** Ensure port `5232` is open on your server.
- **URL Slashes:** Most CalDAV clients (including Odoo) require the URL to end with a trailing slash (`/`).
- **HTTPS:** For production systems, it is highly recommended to run Radicale behind a reverse proxy (like Nginx) with an SSL certificate.
- **Empty Calendar:** If Odoo fails to sync, ensure the calendar exists in Radicale by creating it via the Radicale web interface first.

---

*Last Updated: April 2026*
