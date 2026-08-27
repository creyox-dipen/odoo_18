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

- Set sale_channel_id on sales orders dynamically based on country and FBB suffix (Belgium: 3, Netherlands: 4, Belgium with -FBB: 42, Netherlands with -FBB: 41).
- Set sales order name to 'BL' or 'LVB' (for FBB orders) + Market Reference number.
- Sync Channable order memo directly to the custom Odoo field x_studio_opmerkingen instead of the standard note field.
- Map Channable API address components (street + house_number + house_number_ext) combined to Odoo street field during partner creation.