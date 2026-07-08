18.0.0.0(Date: 24th April,2026)
-------------------------------

- Synchronize events with Google, Zoho, iCloud, Radicale, and Nextcloud servers.

18.0.0.1(Date: 12th June,2026)
-------------------------------
 
- Added functionality of batch wise sync to reduce the sync time.

18.0.0.2(Date: 24th June,2026)
-------------------------------

- customization for client
- Enabled batch-wise sync for Project Tasks, Maintenance Requests, and Field Service Orders.
- Automatically delete synced Nextcloud events when a Project Task is unscheduled (dates cleared) in Odoo.

18.0.0.3(Date: 26th June,2026)
------------------------------

For Maintenance sync:
- add Equipment name to the calendar event subject
- add Technician to the calendar event description
- canceled/deleted maintenance tasks are not removed from the synced calendar
 
For Field Service:
- add order type to calendar event subject
- add location address instead of location name to calendar event address
- add description to calendar event description
- add team to calendar event description
- add assigned technician to calendar event description
- add URL of order to calendar event description
- canceled/deleted orders are not removed from the synced calendar

18.0.0.4(Date: 30th June,2026)
------------------------------
- sync fsm order and set event title in order_name - order_type format

18.0.0.5(Date: 3rd July,2026)
-----------------------------
- Secure CalDAV passwords with symmetric database encryption.
- allowing password updates via confirmation checkbox.
- added translation po file