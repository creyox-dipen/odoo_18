18.0.0.0(Date: 11th June,2026)
-------------------------------

- migrated module from version 19.0

18.0.0.1(Date: 10th Aug,2026)
-------------------------------

- Update existing Odoo orders seamlessly during bulk sync processes.
- Automatic Odoo order cancellation and credit note creation when a bulk sync detects a cancelled status in Channable.
- Added 'Schedule Sync' smart button to the Channable Marketplace dashboard for easy sync interval configuration.
- Removed 'Sync State' smart button because similar functionality like 'Sync Order'.

18.0.0.2(Date: 2nd September,2026)
----------------------------------

- Automatically validate delivery pickings in Odoo when an order status changes or updates to 'shipped' in Channable during manual or bulk order synchronization.
- Removed redundant 'Sync Shipments' action button from Channable Marketplace dashboard as shipment tracking notifications are sent automatically upon delivery validation.
- Added 'Import Starting Date (Cron)' field on Channable Marketplace to scope scheduled automatic sync (cron) from a specific starting date, while maintaining standard manual order sync behavior.
- Updated Marketplace tags configuration to link with Sales Order Tags (`crm.tag`) and assign them directly to imported Sales Orders instead of Customer Partners.