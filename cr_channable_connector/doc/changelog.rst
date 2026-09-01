18.0.0.0(Date: 11th June,2026)
-------------------------------

- migrated module from version 19.0

18.0.0.1(Date: 10th Aug,2026)
-------------------------------

- Update existing Odoo orders seamlessly during bulk sync processes.
- Automatic Odoo order cancellation and credit note creation when a bulk sync detects a cancelled status in Channable.
- Added 'Schedule Sync' smart button to the Channable Marketplace dashboard for easy sync interval configuration.
- Removed 'Sync State' smart button because similar functionality like 'Sync Order'.

18.0.0.2(Date: 24th Aug,2026)
-------------------------------

- Set sale_channel_id on sales orders dynamically based on country and FBB suffix (Belgium: 28, Netherlands: 29, Belgium with -FBB: 33, Netherlands with -FBB: 32).
- Added 'Import Orders From Date/Time' setting on Marketplace configuration to permanently restrict both manual and automatic (cron) sync from importing orders created prior to that date and time.
- Set sales order name to 'BL' or 'LVB' (for FBB orders) + Market Reference number.
- Sync Channable order memo dynamically to a custom Odoo field labeled 'Comments' (falling back to 'comments') instead of the standard note field.
- Map Channable API address components (street + house_number + house_number_ext) combined to Odoo street field during partner creation (falling back to address1).
- Automatically update and sync address, name, and phone details on existing billing and shipping partners when details differ, preventing cache bypass.
- Assign configured Marketplace Tags directly to imported Sales Orders (sale.order.tag_ids).
- Cast incoming address metadata (house number, phone, zip code) to strings to prevent 'int' object strip crashes.