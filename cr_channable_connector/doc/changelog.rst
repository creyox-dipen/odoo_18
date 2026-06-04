19.0.0.2(Date: 4th June,2026)
-------------------------------

- Added dynamic shipping carrier/transporter mapping tables for auto-resolving delivery methods on imported orders.
- Added "Channable Order" smart button on Sales Orders for direct channable order redirection.
- Added instant Dark Mode toggle on Marketplace Kanban card dashboard with custom visual aesthetics.
- Added full support for restricted Company API tokens in the Connection Test action with clean error toast notifications.
- Fixed single order sync by ID to use individual `/orders/{order_id}` endpoints.
- Real-time product feed generation via secure GET endpoint.
- Custom mappings of product fields and attributes to XML tags.
- Order sync by creation dates and status filters (not_shipped, shipped, etc.).
- Auto-lookup and creation of Odoo customer records.
- Auto-confirmation of imported quotation orders.
- Auto-creation of invoices and payment registration.
- Auto-validation of stock pickings for pre-shipped orders.
- Real-time update of tracking codes and carrier names back to Channable.
- Automatic cancellation and credit note refunds for cancelled orders.
- Dedicated synchronization logging and error dashboard.