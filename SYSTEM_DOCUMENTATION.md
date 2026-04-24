# System Documentation

## 1. System Overview
This project is an ICT Management System (`ICT-MS`) built with Django. It is a web-based operations platform for registering ICT assets, assigning them to users or visitors, tracking their location and maintenance state, handling help desk tickets, generating management reports, and receiving GPS telemetry from tracker devices attached to portable equipment.

The system solves a common institutional problem: ICT departments often keep asset records, maintenance records, software inventories, user ownership, and support tickets in separate spreadsheets or disconnected tools. That creates weak audit trails, poor accountability, inconsistent status data, and slow incident resolution. `ICT-MS` centralizes those concerns in one application so the ICT office can answer questions such as:

- What assets exist, where are they, and who is using them?
- Which assets are overdue for return, in maintenance, or approaching warranty expiry?
- Which tickets are overdue, assigned, resolved, or escalated?
- Which software products are deployed on which assets?
- What is the current book value of each asset?
- Which tracked assets have reported recent GPS coordinates?

The system is primarily:

- A Django server-rendered web application
- An operations dashboard and records management platform
- A lightweight IoT-integrated system through GPS tracker ingestion
- A reporting and audit support tool
- A notification-enabled workflow system with optional SMS delivery

Key user-facing features include:

- Custom email-based authentication with role-based access control
- Asset registration, categorization, typing, depreciation, and location history
- Dynamic asset attributes per category
- Software catalog and installed software tracking for computer assets
- Asset assignment and return tracking with visitor-compatible assignee fields
- Maintenance record tracking and maintenance scheduling
- Help desk ticketing with triage, assignment, workflow transitions, comments, attachments, and resolution records
- Report generation for tickets, asset inventory, departments, locations, assignments, maintenance, software, depreciation, and audits
- GPS tracker device registration and coordinate ingestion
- Optional SMS alerts for ticket creation, ticket assignment, and overdue asset assignments

Scope note:

- This documentation focuses on first-party application code, migrations, templates, and custom front-end behavior.
- Bundled third-party assets under `static/assets/js/plugins`, `static/assets/css/plugins`, `static/assets/images`, and `node_modules` are treated as dependencies, not original business logic.

## 2. System Architecture
At a high level, the system follows a classic Django client-server architecture with modular domain apps.

- Client layer:
  - Server-rendered HTML templates
  - HTMX-enhanced partial updates for ticket queues, ticket panels, asset list filtering, and GPS refresh cards
  - Small amounts of inline JavaScript and one custom app JS file for asset software selection
  - Leaflet plus OpenStreetMap tiles for map display on asset GPS pages

- Application layer:
  - `accounts`: authentication, departments, user/role management
  - `core`: dashboard, role decorators, shared utility functions
  - `assets`: the main domain model for inventory, location history, assignments, software, depreciation, audits, and maintenance records
  - `maintenance`: formal maintenance logs and schedules used mainly through admin and dashboard analytics
  - `tickets`: help desk and fault management workflow
  - `reports`: operational and audit reporting with CSV/PDF export
  - `iot_monitoring`: tracker device registry and GPS telemetry ingestion
  - `notifications`: in-app alerts/notifications and SMS delivery/logging
  - `checkouts`: an older checkout/geofence subsystem that remains installed but is only partially aligned with the current asset schema

- Data layer:
  - SQLite database by default (`db.sqlite3`)
  - Normalized relational model using Django ORM
  - Rich migration history showing evolution from a simpler asset schema into the current inventory model

- Integration layer:
  - Easy Send SMS HTTP API for outbound SMS
  - GPS tracker HTTP endpoint for telemetry ingestion
  - Leaflet/OpenStreetMap for browser map rendering
  - QR code generation through the `qrcode` library

### Text Architecture Diagram
```text
+---------------------------+
| Users                     |
| Admin / Help Desk / Tech  |
| Dept User / Management    |
+-------------+-------------+
              |
              v
+---------------------------+
| Django Web UI             |
| Templates + HTMX + JS     |
+-------------+-------------+
              |
              v
+---------------------------------------------------+
| Django Application Layer                          |
|                                                   |
| accounts  -> auth, roles, departments             |
| core      -> dashboard, decorators                |
| assets    -> assets, locations, assignments,      |
|              software, depreciation, audits       |
| maintenance-> schedules, maintenance logs         |
| tickets   -> incident/ticket workflow             |
| reports   -> analytics + CSV/PDF export           |
| iot_monitoring -> tracker devices + GPS readings  |
| notifications  -> alerts + SMS                    |
| checkouts      -> legacy checkout/geofence logic  |
+-------------+-------------------------------------+
              |
              v
+---------------------------+
| SQLite Database           |
| Django ORM models         |
+---------------------------+

External inputs/services:

GPS Tracker Device ---> /iot/gps/ingest/ ---> iot_monitoring
Easy Send SMS API <--- notifications.sms
Leaflet/OpenStreetMap <--- asset GPS detail page
QR Code Library <--- asset QR endpoint
```

### Architectural Observations
- The current production path is strongly centered on `assets`, `tickets`, `reports`, `notifications`, and `iot_monitoring`.
- `maintenance` and `assets` both contain maintenance-related models. The design appears intentional but layered: `assets.MaintenanceRecord` supports end-user CRUD, while `maintenance.MaintenanceLog` and `MaintenanceSchedule` support more formal maintenance operations and dashboard/admin views.
- `checkouts` represents an older portable-asset model. Its presence is important historically, but it is not exposed through project URLs and still expects legacy asset fields that no longer exist in `assets.models.Asset`.

## 3. System Workflow (Step-by-Step)
### 3.1 Authentication and Entry
1. A user visits `/` or `/login/`.
2. Django serves `LoginView` with `accounts.forms.EmailAuthenticationForm`.
3. Authentication uses the custom `accounts.User` model where email is the username.
4. On success, the user is redirected to `/dashboard/`.

### 3.2 Dashboard and Operational Snapshot
1. `core.views.landing_page` aggregates counts and recent records from assets, tickets, maintenance, audits, assignments, and software.
2. The dashboard displays current workload, asset status distribution, ticket priority pressure, overdue work, warranty alerts, and latest audit summary.
3. This page acts as an executive and operational landing page rather than a simple menu.

### 3.3 Asset Registration and Update Flow
1. Admins or technicians open `/assets/create/` or `/assets/<id>/update/`.
2. `assets.forms.AssetForm` loads categories, types, departments, locations, purchases, software catalog options, and category-specific attribute definitions.
3. When the asset category changes, HTMX requests `/assets/asset-type-field/` to rebuild category-dependent form fields.
4. On save:
   - the `Asset` record is stored
   - a `AssetDepreciation` record is created or updated when cost and depreciation inputs exist
   - `AssetLocationHistory` is appended when the selected location changes
   - `InstalledSoftware` rows are synchronized for computer assets
   - `AssetAttributeValue` rows are synchronized for dynamic category attributes
5. Related signals update derived asset status when assignments or maintenance records change.

### 3.4 Assignment Flow
1. An operator creates an `AssetAssignment`.
2. The form validates date order and ensures only one active assignment exists per asset.
3. The assignment stores both optional `user` linkage and manual assignee identity/contact fields, allowing the system to track staff and non-staff assignees.
4. `assets.signals.assignment_status_handler` recalculates the asset status.
5. Reports and detail pages surface active assignments and overdue returns.

### 3.5 Maintenance Flow
There are two related maintenance flows.

- Asset maintenance record flow:
  1. Operators create an `assets.MaintenanceRecord`.
  2. The form enforces completion-date rules.
  3. Signals push the asset into or out of `maintenance` status depending on open/in-progress records.

- Formal maintenance log/schedule flow:
  1. Admin users create `maintenance.MaintenanceLog` or `MaintenanceSchedule` records in the admin interface.
  2. `maintenance.signals` create or refresh follow-up schedules when `next_maintenance_date` is provided.
  3. The same signals also recalculate the asset’s current operational status.

### 3.6 Ticketing Flow
1. A department user, technician, help desk user, or admin creates a fault ticket.
2. `tickets.forms.FaultTicketCreateForm` validates department/asset alignment and auto-enables `is_asset_fault` for hardware tickets.
3. `FaultTicket.save()` computes SLA due dates and milestone timestamps.
4. Help desk or admin staff triage and assign the ticket through the workflow panel.
5. Assigned technicians or authorized operators add comments, attachments, workflow notes, and resolution data.
6. If the issue requires physical repair on an asset, `ticket_create_maintenance` creates an `assets.MaintenanceRecord` directly from the ticket.
7. Resolution data creates a `TicketResolution` record and marks the ticket `RESOLVED`.
8. Signals may send SMS notifications on ticket creation and assignment.

### 3.7 Reporting Flow
1. Users open `/reports/`.
2. The reports index shows available report types and summary counts.
3. Each report view builds a queryset, computes summary statistics, and renders an HTML table/report page.
4. The same report can be exported as:
   - CSV using `_csv_response`
   - PDF using the project’s custom `_build_pdf_bytes` generator

### 3.8 GPS Tracking Flow
1. A tracker device sends coordinates to `/iot/gps/ingest/` using device ID, API key, latitude, longitude, and optional telemetry.
2. `iot_monitoring.views.gps_ingest` validates credentials and payload values.
3. A `GPSReading` is created and the linked `TrackerDevice.last_seen_at` is updated.
4. Asset detail pages read the active tracker and recent readings through `assets.views._asset_gps_context`.
5. HTMX refreshes the GPS card and GPS map partial every 20 seconds.
6. Leaflet renders recent path points in the browser.

### 3.9 Notification and SMS Flow
1. Operational events create in-app `Notification` or `Alert` records.
2. Ticket signals send SMS to admins when a ticket is created and to assignees when a ticket is assigned.
3. A management command scans overdue assignments and sends one SMS reminder per recipient/object/day.
4. Every SMS attempt is written to `SMSNotificationLog`, whether sent, failed, or skipped.

## 4. Codebase Breakdown
### 4.1 File: `manage.py`
- Purpose: Django command entry point.
- Why used: boots the project for `runserver`, `migrate`, `test`, `check`, and custom commands.
- Key function:
  - `main()`: sets `DJANGO_SETTINGS_MODULE` to `config.settings` and delegates to Django CLI.

### 4.2 File: `requirements.txt`
- Purpose: Python dependency manifest.
- Why used: defines framework, UI, filtering, REST, imaging, and SMS-supporting dependencies.
- Important notes:
  - `Django`, `django-cors-headers`, `crispy` packages, `django-jazzmin`, `djangorestframework`, and `pillow` are pinned.
  - `qrcode` is intentionally listed unpinned and noted as potentially missing from the current virtual environment even though `assets.views.asset_qr_code` imports it.
  - `python-decouple` is listed but not used in the current settings module.

### 4.3 File: `package.json`
- Purpose: front-end package manifest.
- Why used: manages the local HTMX dependency.
- Main content:
  - dependency on `htmx.org`
  - `sync:htmx` script copies the minified HTMX bundle from `node_modules` into `static/assets/js/plugins/`

### 4.4 File: `config/settings.py`
- Purpose: central application configuration.
- Why used: controls Django runtime behavior, installed apps, auth model, static/media paths, REST defaults, Jazzmin admin skin, CORS, and SMS integration settings.
- Important settings and logic:
  - `_env_bool()` and `_env_list()` read environment variables in a simple reusable way.
  - `INSTALLED_APPS` enables the project’s modular structure.
  - `AUTH_USER_MODEL = 'accounts.User'` makes the custom email-based user model authoritative.
  - `DATABASES` defaults to SQLite.
  - `STATICFILES_DIRS`, `STATIC_ROOT`, and `MEDIA_ROOT` support uploaded ticket attachments and other media.
  - `REST_FRAMEWORK` is configured, but no public DRF API routes are currently exposed.
  - `CORS_ALLOWED_ORIGINS` exists mainly to support IoT device/browser interactions.
  - `EASY_SEND_SMS_*` values configure optional SMS delivery.
- Interaction:
  - used by every app
  - consumed directly by `notifications.sms`
  - referenced by auth, templates, static/media handling, and admin UI

### 4.5 File: `config/urls.py`
- Purpose: project URL router.
- Why used: exposes the system’s web entry points.
- Main wiring:
  - `/admin/` -> Django admin
  - `/`, `/login/`, `/logout/` -> authentication
  - `/dashboard/` -> `core.views.landing_page`
  - `/iot/` -> IoT GPS ingest routes
  - `/users/` -> account/department management
  - `/assets/` -> inventory and asset operations
  - `/tickets/` -> help desk ticketing
  - `/reports/` -> reporting
- Observation:
  - No URL include exists for `checkouts`, `maintenance`, or `notifications`; those apps operate through admin, signals, commands, or internal calls.

### 4.6 File: `config/asgi.py`, `config/wsgi.py`, and package marker files
- `config/asgi.py`: ASGI application bootstrap for async-capable deployment.
- `config/wsgi.py`: WSGI application bootstrap for traditional deployment.
- `config/__init__.py`: package marker with no business logic.

### 4.7 File: `accounts/models.py`
- Purpose: authentication and organizational structure.
- Classes:
  - `Department`: stores department name/code and is referenced by users, assets, tickets, and reports.
  - `UserManager`:
    - `create_user()`: normalizes email, hashes password, creates user.
    - `create_superuser()`: forces staff/superuser/admin role.
  - `User`: custom auth model using email as the login field.
- Why used:
  - roles are the system’s main authorization primitive
  - departments connect users to assets and tickets
- Important properties on `User`:
  - `is_admin`, `is_technician`, `is_help_desk`, `is_department_user`, `is_management`
  - these properties are consumed by decorators, permissions, view logic, and templates

### 4.8 File: `accounts/forms.py`
- Purpose: authentication and admin-facing user/department forms.
- Classes:
  - `EmailAuthenticationForm`: replaces username input with email input for login.
  - `UserManagementFormMixin`:
    - standardizes field order and styling
    - sorts department choices
    - `_sync_staff_flag()` keeps `is_staff` aligned with role
  - `UserCreateForm`:
    - password confirmation validation through `clean_password2()`
    - hashes new passwords in `save()`
  - `UserUpdateForm`:
    - optional password change through `new_password1/new_password2`
    - `clean_new_password2()` enforces confirmation
  - `DepartmentForm`: standard department CRUD form.
- Interaction:
  - used by `accounts.views`
  - login form is used by `config.urls` in the customized `LoginView`

### 4.9 File: `accounts/views.py`
- Purpose: web CRUD for users and departments.
- Why used: provides admin-only management UI for system actors and organizational units.
- Main functions:
  - `user_list()`: search/filter/paginate users and compute role statistics.
  - `user_detail()`: show one managed user.
  - `user_create()`, `user_update()`, `user_delete()`: full user lifecycle management, including self-delete protection.
  - `department_list()`: list departments with user and asset counts.
  - `department_detail()`: show a department with recent users and assets.
  - `department_create()`, `department_update()`, `department_delete()`: department CRUD.
- Interaction:
  - protected by `login_required` and `core.decorators.admin_required`
  - uses `messages` for UI feedback
  - feeds `accounts` templates

### 4.10 File: `accounts/urls.py`
- Purpose: namespaced routes for user and department management.
- Why used: decouples account management URLs from project root URLs.

### 4.11 File: `accounts/admin.py`
- Purpose: custom Django admin integration for the custom user model.
- Classes:
  - `UserCreationForm` and `UserChangeForm`: admin-only forms for password handling.
  - `DepartmentAdmin`: searchable and sortable department admin.
  - `UserAdmin`: full replacement for Django’s default admin user class.
- Interaction:
  - makes the custom `accounts.User` manageable through Django admin
  - uses `select_related('department')` for efficiency

### 4.12 File: `accounts/tests.py`
- Purpose: verifies login/logout and admin-only user/department management.
- Test classes:
  - `LoginViewTests`
  - `UserManagementViewTests`
  - `DepartmentManagementViewTests`
- Why used: protects authentication flow, access control, and CRUD behavior.

### 4.13 File: `accounts/migrations/*.py`
- `0001_initial.py`: creates `Department` and `User`.
- `0002_alter_user_role.py`: adds the `HELP_DESK` role, which later becomes central to ticket triage.
- `__init__.py`: package marker.

### 4.14 File: `core/views.py`
- Purpose: dashboard aggregation and rendering.
- Key helper functions:
  - `_safe_count()`: defensive count wrapper to avoid startup/migration-time DB errors.
  - `_safe_list()`: defensive queryset materialization helper.
  - `_percentage()`: percent formatting for dashboard bars.
  - `landing_page()`: main dashboard view.
- Why used:
  - concentrates dashboard queries in one location
  - builds operational context for management and ICT staff
- Interaction:
  - reads from `accounts`, `assets`, `maintenance`, and `tickets`
  - renders `templates/dashboard.html`

### 4.15 File: `core/decorators.py`
- Purpose: reusable role-based access decorators.
- Functions:
  - `admin_required()`
  - `admin_or_technician_required()`
  - `department_user_required()`
- Why used:
  - centralizes role checks
  - converts unauthorized access into `PermissionDenied`
- Observation:
  - `department_user_required()` exists but is not currently used by view code.

### 4.16 File: `core/context_processors.py`
- Purpose: reusable asset count injection for templates.
- Function:
  - `asset_stats()`: returns total/available/maintenance counts plus backward-compatible keys.
- Observation:
  - this context processor is defined but not registered in `TEMPLATES['OPTIONS']['context_processors']` in `config/settings.py`, so it is currently inactive.

### 4.17 File: `core/tests.py`, `core/models.py`, `core/admin.py`, `core/apps.py`, and marker files
- `core/tests.py`: verifies that anonymous users see login, dashboard is protected, and authenticated users see the dashboard.
- `core/models.py`: placeholder, currently no models.
- `core/admin.py`: placeholder, currently no admin registrations.
- `core/apps.py`: declares `CoreConfig`.
- `core/__init__.py` and `core/migrations/__init__.py`: package markers.

### 4.18 File: `assets/models.py`
- Purpose: core asset-management domain model.
- Querysets and models:
  - `AssetCategoryQuerySet.ordered_choices()`: convenient ordering helper.
  - `AssetCategory`: top-level classification; includes `is_computer_category` to activate software/UI behavior.
  - `AssetType`: subtype within a category; enforces category-specific typing.
  - `Supplier`: procurement source.
  - `AssetPurchase`: procurement transaction metadata.
  - `Asset`:
    - central inventory record
    - validates category/type compatibility in `clean()`
    - derives `current_assignment`, `current_location_record`, `current_location`, `current_value`, and `is_computer`
  - `Location`: structured physical location
  - `AssetLocationHistory`: audit trail of moves
  - `AssetAssignment`:
    - tracks issuance/return
    - supports both linked users and manually recorded assignees
    - validates required assignee identity data and date order
  - `MaintenanceRecord`: operational maintenance record exposed in user-facing asset pages
  - `Software`: software catalog item
  - `InstalledSoftware`: link between computer assets and software titles
  - `AssetAttribute`: category-defined dynamic schema field
  - `AssetAttributeValue`: per-asset value for dynamic attributes
  - `AssetDepreciation`: one-to-one depreciation ledger
  - `AssetAudit`: audit session header
  - `AssetAuditItem`: per-asset audit result
  - `AssetActivityLog`: timeline/audit log entry
- Why used:
  - this file contains the system’s most important data structures
  - nearly every other app reads from it
- Interactions:
  - `tickets.FaultTicket` links to `Asset` and `Location`
  - `iot_monitoring.TrackerDevice` links to `Asset`
  - `notifications.Alert` optionally links to `Asset`
  - `reports.views` aggregates almost every model defined here

### 4.19 File: `assets/forms.py`
- Purpose: form-layer orchestration for asset-related CRUD and dynamic UI behavior.
- Main classes and logic:
  - `AssetForm`:
    - adds non-model fields for location, software, and depreciation
    - dynamically loads category-specific `AssetAttribute` definitions
    - `attribute_field_name()` standardizes dynamic field names
    - `_coerce_boolean_attribute_value()`, `_get_attribute_initial_value()`, `_build_attribute_field()`, `_add_attribute_fields()`, `_serialize_attribute_value()` support dynamic attribute rendering and storage
    - `clean_asset_tag()` keeps asset tags unique
    - `clean()` validates depreciation inputs, software/category compatibility, and defaulting logic
    - `save()` synchronizes `AssetDepreciation`, `AssetLocationHistory`, `InstalledSoftware`, and `AssetAttributeValue`
  - `AssetAssignmentForm`: validates assignment dates and enforces single active assignment per asset.
  - `MaintenanceRecordForm`: enforces completion date when status becomes completed.
  - `LocationForm`, `SoftwareForm`: standard CRUD wrappers.
  - `AssetFilterForm`: asset list filter surface.
  - `AssetAttributeValueForm`: minimal value editor.
- Why used:
  - keeps complex asset business rules out of views
  - powers the dynamic category-sensitive asset form

### 4.20 File: `assets/views.py`
- Purpose: user-facing inventory module.
- Helper functions:
  - `_is_htmx()`: detects HTMX requests.
  - `_asset_gps_context()`: merges active tracker, latest reading, map points, and OpenStreetMap URL into one context object.
- Main view groups:
  - Asset views:
    - `asset_list()`
    - `asset_detail()`
    - `asset_gps_tracking_card()`
    - `asset_gps_map_panel()`
    - `asset_create()`
    - `asset_type_field()`
    - `asset_update()`
    - `asset_delete()`
    - `asset_qr_code()`
  - Software views:
    - `software_list()`, `software_detail()`, `software_create()`, `software_update()`, `software_delete()`
  - Category/location views:
    - `category_list()`
    - `location_list()`, `location_detail()`, `location_create()`, `location_update()`, `location_delete()`
  - Assignment views:
    - `assignment_list()`, `assignment_detail()`, `assignment_create()`, `assignment_update()`, `assignment_delete()`
  - Maintenance views:
    - `maintenance_list()`, `maintenance_detail()`, `maintenance_create()`, `maintenance_update()`, `maintenance_delete()`
- Why used:
  - this file is the main operational interface for inventory staff
  - integrates HTMX partial updates, QR code generation, and GPS display

### 4.21 File: `assets/signals.py`
- Purpose: derived asset state maintenance.
- Functions:
  - `refresh_asset_status(asset)`: precedence logic is maintenance first, assignment second, otherwise available.
  - `maintenance_status_handler()`: refreshes status after maintenance record create/update/delete.
  - `assignment_status_handler()`: refreshes status after assignment create/update/delete.
- Why used:
  - prevents manual status drift between records and asset master state

### 4.22 File: `assets/urls.py`
- Purpose: namespaced URL map for all asset-related operations.
- Why used: groups asset, software, location, assignment, maintenance, GPS partial, and QR code routes.

### 4.23 File: `assets/admin.py`
- Purpose: rich Django admin coverage for the entire asset domain.
- Important classes:
  - inline classes for location history, assignments, maintenance, installed software, attributes, activity logs, depreciation, and audit items
  - `AssetCategoryAdmin`, `AssetTypeAdmin`, `SupplierAdmin`, `AssetPurchaseAdmin`
  - `AssetAdmin`: high-value admin with status badges, inlines, and current snapshot display methods
  - `LocationAdmin`, `AssetLocationHistoryAdmin`, `AssetAssignmentAdmin`, `MaintenanceRecordAdmin`
  - `SoftwareAdmin`, `InstalledSoftwareAdmin`
  - `AssetAttributeAdmin`, `AssetAttributeValueAdmin`, `AssetDepreciationAdmin`
  - `AssetAuditAdmin`, `AssetAuditItemAdmin`, `AssetActivityLogAdmin`
- Why used:
  - exposes almost the full operational model through Django admin for power users and data stewardship

### 4.24 File: `assets/tests.py`
- Purpose: regression coverage for the inventory subsystem.
- Coverage areas:
  - model validation and computed properties
  - depreciation creation/update
  - location history behavior
  - signal-driven asset status changes
  - software synchronization
  - dynamic category attributes
  - HTMX asset list and category-field behavior
  - software/location/assignment/maintenance CRUD views
- Observation:
  - this is one of the strongest test files in the project and documents intended behavior very well.

### 4.25 File: `assets/migrations/*.py`
- `0001_initial.py`: original asset/category schema.
- `0002_enhanced_asset_management.py`: introduces a richer legacy asset model, computer asset detail model, installed software, location/status history, and servicing fields.
- `0003_software_catalog.py`: moves from per-computer installed software definitions to a shared software catalog.
- `0004_asset_geofence_enabled_asset_geofence_latitude_and_more.py`: adds portable-asset, checkout, and GPS/geofence fields to `Asset`.
- `0005_assetactivitylog_assetassignment_assetattribute_and_more.py`:
  - major refactor into the current normalized model
  - creates `AssetType`, `Location`, `AssetAssignment`, `InstalledSoftware`, `AssetDepreciation`, `AssetAudit`, `AssetActivityLog`, and more
  - migrates legacy data from old fields/models
  - removes checkout/geofence-related fields from `Asset`
- `0006_make_asset_type_location_and_software_name_required.py`: tightens required fields.
- `0007_backfill_asset_depreciation_records.py`: auto-creates depreciation ledgers for historical assets with cost/date data.
- `0008_alter_assetcategory_name.py`: normalizes category names into canonical buckets.
- `0009_assetassignment_condition_at_issue_and_more.py`: adds assignment purpose and condition fields.
- `0010_assetassignment_assignee_contact_and_more.py`: adds visitor-compatible assignee metadata and backfills from linked users.
- `0011_alter_assetdepreciation_salvage_value.py`: renames the salvage value label to “End-of-Life Value”.
- `0012_assetcategory_is_computer_category_and_more.py`: introduces `is_computer_category` and removes DB-level category-choice restriction.
- Why used:
  - the migration history is essential for understanding why `checkouts` now mismatches the live asset schema.

### 4.26 File: `assets/static/assets/js/asset_computer_inline.js`
- Purpose: legacy admin-side JavaScript for toggling old computer-specific inline forms.
- Why used: originally supported the pre-refactor `ComputerAsset` admin workflow.
- Observation:
  - because `ComputerAsset` was removed in later migrations, this file now appears legacy and not part of the current user-facing form flow.

### 4.27 File: `maintenance` app files
- `maintenance/models.py`:
  - `MaintenanceLog`: formal service record with status, performer, cost, parts, and follow-up date
  - `MaintenanceSchedule`: planned maintenance task with overdue detection
- `maintenance/signals.py`:
  - `_sync_follow_up_schedule()`: auto-creates or updates follow-up schedules
  - `_refresh_asset_status()`: aligns asset master status with open maintenance state and active assignments
  - `sync_asset_status_and_service_dates()` and `refresh_asset_status_after_log_delete()` wire the logic to signals
- `maintenance/admin.py`:
  - strong admin UX for both logs and schedules with badges and bulk actions
- `maintenance/views.py`:
  - placeholder; no public views are currently implemented here
- `maintenance/tests.py`:
  - verifies that maintenance logs drive asset status and schedule creation
- `maintenance/apps.py` and marker files:
  - register the app and import signals in `ready()`
- `maintenance/migrations/0001_initial.py` and `0002_enhanced_maintenance_log.py`:
  - create the app models and later add status/completion metadata and backfill `completed_at`
- Design note:
  - this app overlaps conceptually with `assets.MaintenanceRecord`, so it should be documented as a complementary but separate maintenance subsystem.

### 4.28 File: `iot_monitoring/models.py`
- Purpose: the current GPS tracking data model.
- Classes:
  - `TrackerDevice`: binds a physical tracker to an asset and stores API key, status, and `last_seen_at`.
  - `GPSReading`:
    - stores coordinates and telemetry
    - `clean()` validates latitude, longitude, and battery bounds
    - `_to_decimal()` safely coerces numeric values
- Why used:
  - provides the live GPS path used on asset detail pages
  - replaces the older asset-bound GPS design previously embedded directly in `Asset`

### 4.29 File: `iot_monitoring/views.py`
- Purpose: machine-facing GPS ingest endpoint.
- Helper functions:
  - `_request_data()`: reads GET or POST parameters
  - `_parse_decimal()`, `_parse_float()`, `_parse_int()`: telemetry parsing helpers
  - `_parse_recorded_at()`: supports absent timestamps, unix timestamps, and ISO datetime values
- Main view:
  - `gps_ingest()`:
    - `csrf_exempt`
    - accepts GET or POST
    - authenticates tracker by `device_id` and API key
    - validates telemetry
    - stores a `GPSReading`
    - updates tracker `last_seen_at`
    - returns plain `OK`
- Why used:
  - this is the project’s main hardware integration point

### 4.30 File: `iot_monitoring` support files
- `iot_monitoring/urls.py`: exposes `/gps/ingest/`.
- `iot_monitoring/admin.py`: admin views for tracker devices and GPS readings.
- `iot_monitoring/tests.py`: verifies ingest security/validation and asset GPS partial rendering.
- `iot_monitoring/apps.py`: app registration.
- `iot_monitoring/migrations/0001_initial.py`: creates tracker and GPS reading tables.
- `iot_monitoring/__init__.py` and `migrations/__init__.py`: package markers.

### 4.31 File: `notifications/models.py`
- Purpose: internal notification and alert persistence plus SMS audit logging.
- Classes:
  - `Notification`: per-user in-app notification.
  - `Alert`: asset-related alert with severity and acknowledgement workflow.
  - `SMSNotificationLog`: durable SMS attempt ledger keyed by event type, recipient, phone number, related object, and date.
- Why used:
  - supports both operational awareness and auditability of outbound messaging

### 4.32 File: `notifications/sms.py`
- Purpose: SMS delivery service abstraction.
- Main components:
  - `SMSResult`: lightweight result object returned by send operations.
  - `normalize_phone_number()`: strips formatting, applies default country code rules, and standardizes storage.
  - `_message_type()`: chooses ASCII vs Unicode provider type.
  - `_extract_provider_message_id()`: parses provider response IDs.
  - `_send_sms_request()`: raw HTTP POST to Easy Send SMS.
  - `send_sms_to_number()`: full orchestration including validation, feature toggle checks, missing-setting checks, provider call, exception handling, and logging.
  - `send_sms_to_user()`: convenience wrapper.
  - `sms_already_sent()`: duplicate-prevention check for one event/object/phone/day.
  - `_record_sms_result()`: persists `SMSNotificationLog`.
- Why used:
  - centralizes all SMS behavior so signals and commands remain simple

### 4.33 File: `notifications/management/commands/send_overdue_sms_notifications.py`
- Purpose: scheduled reminder command for overdue assignments.
- Key logic:
  - finds active assignments whose `expected_return` is before today
  - chooses the best phone candidate from linked user or manual assignee contact
  - skips duplicates using `sms_already_sent()`
  - sends a personalized overdue reminder
  - prints run summary counts
- Why used:
  - supports daily automated operations outside interactive web requests

### 4.34 File: `notifications` support files
- `notifications/admin.py`: admin views and bulk actions for notifications, alerts, and SMS logs.
- `notifications/tests.py`: verifies ticket SMS, assignment-overdue SMS, phone normalization, and duplicate prevention.
- `notifications/views.py`: placeholder, currently unused.
- `notifications/apps.py`: app registration.
- `notifications/migrations/0001_initial.py`: creates `Notification` and `Alert`.
- `notifications/migrations/0002_smsnotificationlog.py`: adds durable SMS logging.
- `notifications/__init__.py`, management package markers, and migration markers: structural files only.

### 4.35 File: `tickets/models.py`
- Purpose: help desk domain model.
- Key function:
  - `generate_ticket_id()`: builds human-readable IDs like `TKT-YYYY-XXXXXX`.
- Main classes:
  - `FaultTicket`:
    - stores incident/request metadata, linked asset/location/department, workflow actors, priority, impact, SLA due date, and milestone timestamps
    - `clean()` enforces asset-fault rules and department/asset consistency
    - `_target_due_date()` computes SLA resolution target from priority
    - `response_due_at`, `resolution_time`, `response_time`, `is_open`, `is_overdue`, `can_create_maintenance` are derived properties
    - `mark_first_response()` stamps first response time
    - `save()` performs lifecycle timestamp management and auto-fills location/due date
  - `TicketResolution`: structured resolution record tied one-to-one to a ticket
  - `TicketComment`: chronological ticket updates
  - `TicketAttachment`: uploaded evidence/documents
- Why used:
  - provides the project’s incident management capability

### 4.36 File: `tickets/forms.py`
- Purpose: form-layer workflow and validation for tickets.
- Classes and logic:
  - `BaseTicketForm`:
    - builds the ticket creation/update form
    - limits asset choices to the selected department
    - uses HTMX attributes on department field to reload the asset field
    - `clean_department()` preserves department-user scoping
    - `clean()` validates asset/department consistency, hardware ticket rules, and auto-fills location
    - `save()` ensures location is inherited from the asset when needed
  - `FaultTicketCreateForm`: currently just aliases base behavior.
  - `TicketWorkflowForm`:
    - enforces assignment requirements for active states
    - prevents `requires_maintenance` on non-asset tickets
    - prevents resolving without a `TicketResolution`
    - auto-triages/assigns status in `save()`
  - `TicketResolutionForm`: structured resolution input
  - `TicketCommentForm`: simple comment form
  - `TicketAttachmentForm`: upload form
  - `TicketFilterForm`: ticket queue search/filter UI, with department/assignee filters visible only to supervisory roles

### 4.37 File: `tickets/permissions.py`
- Purpose: all ticket authorization logic in one place.
- Key functions:
  - `is_ticket_supervisor()`
  - `can_view_all_tickets()`
  - `can_create_tickets()`
  - `can_triage_tickets()`
  - `can_manage_tickets()`
  - `can_workflow_ticket()`
  - `can_comment_on_ticket()`
  - `can_upload_ticket_attachment()`
  - `ticket_queryset_for_user()`: central visibility filter used by ticket list and report scope
  - `enforce_ticket_*` helpers: raise `PermissionDenied` consistently
- Why used:
  - separates role policy from view code
  - keeps ticket access rules explicit and reusable

### 4.38 File: `tickets/views.py`
- Purpose: the main ticket UI and HTMX workflow engine.
- Helper functions:
  - `_is_htmx()`
  - `_base_ticket_queryset()`
  - `_queue_definitions()`
  - `_apply_queue_filter()`
  - `_build_queue_cards()`
  - `_ticket_stats()`
  - `_apply_ticket_filters()`
  - `_render_attachment_panel()`
  - `_ticket_resolution()`
  - `_render_comments_panel()`
  - `_render_workflow_panel()`
  - `_render_resolution_panel()`
- Main views:
  - `ticket_list()`: filtered and role-scoped queue page with HTMX partial rendering
  - `ticket_detail()`: full ticket workspace
  - `ticket_create()`: create help desk ticket
  - `ticket_asset_field()`: HTMX endpoint for department-specific asset picker
  - `ticket_update()`: conditional edit surface
  - `ticket_workflow_panel()` and `ticket_workflow_update()`
  - `ticket_resolution_panel()` and `ticket_resolution_update()`
  - `ticket_comments_panel()` and `ticket_comment_create()`
  - `ticket_attachment_panel()` and `ticket_attachment_upload()`
  - `ticket_create_maintenance()`: bridge into `assets.MaintenanceRecord`
- Why used:
  - this file implements the end-to-end interactive ticket workflow

### 4.39 File: `tickets/signals.py`
- Purpose: SMS side effects for ticket events.
- Functions:
  - `_ticket_summary()`: shortens ticket content for SMS.
  - `stash_previous_ticket_state()`: remembers previous assignment before save.
  - `send_ticket_sms_notifications()`: sends SMS to admins on creation and to new assignees on assignment.
- Why used:
  - keeps notifications decoupled from core ticket save logic

### 4.40 File: `tickets` support files
- `tickets/urls.py`: namespaced ticket route map.
- `tickets/admin.py`: Django admin for tickets, resolutions, comments, attachments, and status/priority actions.
- `tickets/tests.py`: verifies visibility rules, queue filters, workflow updates, resolution behavior, attachments, and maintenance creation.
- `tickets/apps.py`: imports signals in `ready()`.
- `tickets/migrations/0001_initial.py`: creates initial ticket, comment, and attachment models.
- `tickets/migrations/0002_faultticket_location.py`: adds location linkage.
- `tickets/migrations/0003_ticketresolution_faultticket_due_date_and_more.py`: introduces richer workflow fields and structured resolutions.
- `tickets/__init__.py` and migration markers: structural only.

### 4.41 File: `reports/views.py`
- Purpose: analytics and export subsystem.
- Core helper functions:
  - `_asset_inventory_queryset()`: annotates current location via subqueries
  - `_location_label()`
  - `_sum_decimal()`
  - `_display_value()`
  - `_format_duration()`
  - `_build_export_urls()`
  - `_csv_response()`
  - `_pdf_escape()`
  - `_build_pdf_bytes()`: hand-built PDF writer using raw PDF objects and text streams
  - `_pdf_response()`
  - `_report_filename()`
  - `_render_report()`: shared HTML/CSV/PDF switching logic
- Report views:
  - `reports_index()`
  - `ticket_report()`
  - `asset_inventory_report()`
  - `assets_by_department_report()`
  - `assets_by_location_report()`
  - `assigned_assets_report()`
  - `maintenance_report()`
  - `software_inventory_report()`
  - `depreciation_report()`
  - `audit_report()`
- Why used:
  - gives the system managerial and academic reporting value without introducing a separate BI stack

### 4.42 File: `reports` support files
- `reports/urls.py`: report route map.
- `reports/tests.py`: verifies login protection, content rendering, visibility scoping, and CSV/PDF exports.
- `reports/models.py`: placeholder; no report models are defined.
- `reports/admin.py`: placeholder; no admin models are registered.
- `reports/apps.py`: app registration.
- `reports/__init__.py` and migration markers: structural only.

### 4.43 File: `checkouts/models.py`
- Purpose: intended checkout, GPS, geofence, and history subsystem for portable assets.
- Classes:
  - `CheckoutRequest`: request/approval/return workflow with validation and generated request numbers
  - `GPSLocation`: checkout-linked location points with distance-from-geofence calculation
  - `GeofenceAlert`: alert records for exits, re-entry, low battery, and signal loss
  - `CheckoutHistory`: status transition log
- Important algorithms:
  - `CheckoutRequest._generate_request_number()`
  - `GPSLocation.calculate_distance_from_point()`: Haversine-based distance estimation
  - `GPSLocation.save()`: computes geofence state before persist
- Current-state observation:
  - this file still expects fields such as `is_portable`, `max_checkout_days`, `assigned_to`, `has_gps_tracker`, and geofence settings on `assets.Asset`
  - those fields were removed from the live asset schema in `assets` migration `0005`
  - the code is historically valuable but not fully compatible with the present model layer

### 4.44 File: `checkouts/signals.py`
- Purpose: side effects for checkout lifecycle and geofence alerts.
- Functions:
  - `_status_actor()`
  - `_notify_users()`: bulk-creates in-app notifications
  - `stash_previous_checkout_status()`
  - `handle_checkout_request_updates()`: creates history and notifications for approval/rejection/overdue flow
  - `check_geofence_events()`: creates `GeofenceAlert`, `notifications.Alert`, and notifications for geofence exits/entry and low battery
- Current-state observation:
  - logic is detailed and well structured, but it depends on the same legacy asset fields as the rest of the `checkouts` app.

### 4.45 File: `checkouts/admin.py`
- Purpose: full admin workflow for legacy checkout/geofence subsystem.
- Contents:
  - inlines for GPS locations, geofence alerts, and history
  - `CheckoutRequestAdmin` with badges, bulk actions, GPS status helpers, and lifecycle transitions
  - `GPSLocationAdmin`
  - `GeofenceAlertAdmin`
- Why used:
  - shows that the original checkout subsystem was designed to be operated mainly via Django admin

### 4.46 File: `checkouts/tests.py` and migration files
- `checkouts/tests.py`:
  - documents intended portable-asset behavior, geofence alert creation, and notification flow
  - however, it also creates `Asset` objects using fields that no longer exist in the current `assets.models.Asset`, which indicates schema drift
- `checkouts/migrations/0001_initial.py`:
  - captures the original checkout subsystem when checkout/geofence fields still lived on `Asset`
- `checkouts/apps.py`, `__init__.py`, and migration markers:
  - app registration and package structure

### 4.47 File: `templates/base.html`
- Purpose: global layout.
- Why used:
  - provides navigation, theme assets, dropdown user menu, footer, HTMX inclusion, and layout shell for every authenticated page
- Important interactions:
  - references user role properties directly in template conditionals
  - includes local `htmx.min.js`
  - links the dashboard, assets, tickets, reports, and admin-only user management

### 4.48 File: `templates/dashboard.html`
- Purpose: dashboard presentation layer.
- Why used:
  - turns `core.views.landing_page` context into a visually rich operations dashboard
- Important behavior:
  - custom styling for KPI cards and progress bars
  - embeds multiple chart placeholders and front-end chart configuration
  - surfaces tickets, maintenance, assignments, warranty alerts, and audit snapshot data

### 4.49 File: `templates/registration/login.html` and `templates/registration/register.html`
- `login.html`:
  - actual authentication template used by the configured `LoginView`
  - matches the email/password authentication flow
- `register.html`:
  - static sign-up screen template
  - no route or view currently references it
  - appears to be a theme-derived placeholder rather than an active registration feature

### 4.50 File: `templates/accounts/*.html`
- `user_list.html`: paginated admin user directory.
- `user_detail.html`: full view of one managed user.
- `user_form.html`: create/update wrapper.
- `user_confirm_delete.html`: deletion confirmation page.
- `department_list.html`: paginated department overview.
- `department_detail.html`: department summary with recent users/assets.
- `department_form.html`: department create/update page.
- `department_confirm_delete.html`: department deletion confirmation.
- `accounts/partials/user_form_fields.html`: reusable field fragment for user create/update forms.
- Why used:
  - these templates provide the full non-admin web interface for user and department administration.

### 4.51 File: `templates/assets/*.html`
- `asset_list.html`: wrapper around HTMX-powered asset register.
- `asset_detail.html`: detailed asset workspace with depreciation, assignments, software, history, activity, and GPS map integration.
- `asset_form.html`: asset create/update shell plus software picker JavaScript.
- `asset_confirm_delete.html`: delete confirmation.
- `software_list.html`, `software_detail.html`, `software_form.html`, `software_confirm_delete.html`: software catalog UI.
- `location_list.html`, `location_detail.html`, `location_form.html`, `location_confirm_delete.html`: location admin pages.
- `assignment_list.html`, `assignment_detail.html`, `assignment_form.html`, `assignment_confirm_delete.html`: assignment management pages.
- `maintenance_list.html`, `maintenance_detail.html`, `maintenance_form.html`, `maintenance_confirm_delete.html`: maintenance record pages.
- `category_list.html`: read-only category overview.

### 4.52 File: `templates/assets/partials/*.html`
- `asset_form_fields.html`: main asset form body, including depreciation section and HTMX category handling.
- `asset_category_fields.html`: category-dependent asset type field, software picker, and dynamic attribute fields.
- `asset_list_content.html` and `asset_list_results.html`: HTMX-updated asset filter/results fragments.
- `asset_gps_tracking_card.html`: live tracker status card refreshed every 20 seconds.
- `asset_gps_map_panel.html`: live map and recent reading table refreshed every 20 seconds.
- `assignment_form_fields.html`: reusable assignment form fragment.
- `maintenance_form_fields.html`: reusable maintenance form fragment.
- `asset_type_field.html`: appears unused in current view/template wiring; likely an older partial superseded by `asset_category_fields.html`.

### 4.53 File: `templates/tickets/*.html`
- `ticket_list.html`: ticket workspace shell.
- `ticket_detail.html`: full ticket dashboard combining overview, workflow, resolution, comments, and attachments.
- `ticket_form.html`: ticket create/update shell.
- Why used:
  - these templates form the main operational help desk interface.

### 4.54 File: `templates/tickets/partials/*.html`
- `ticket_form_fields.html`: shared ticket form body.
- `ticket_asset_field.html`: HTMX-loaded asset field limited by department.
- `ticket_list_content.html` and `ticket_list_results.html`: queue cards, filters, pagination, and list table for HTMX updates.
- `workflow_panel.html`: assignment/triage/update controls and “Create Maintenance” action.
- `resolution_panel.html`: resolution editing and resolved-state display.
- `comments_panel.html`: comment timeline and entry form.
- `attachment_panel.html`: file upload panel with multipart HTMX submission.
- Why used:
  - these partials make ticket detail and ticket list highly interactive without building a separate JavaScript SPA.

### 4.55 File: `templates/reports/*.html` and `templates/reports/partials/export_actions.html`
- `index.html`: report catalog landing page.
- `ticket_report.html`: ticket analytics view.
- `asset_inventory.html`: asset register report.
- `assets_by_department.html`: department summary report.
- `assets_by_location.html`: location distribution report.
- `assigned_assets.html`: active assignment report.
- `maintenance_report.html`: maintenance activity report.
- `software_inventory.html`: software deployment report.
- `depreciation_report.html`: financial book-value report.
- `audit_report.html`: audit results report.
- `partials/export_actions.html`: reusable CSV/PDF download buttons.
- Why used:
  - these templates present management-ready views backed by the export subsystem.

### 4.56 File: Vendor static assets and package markers
- `__init__.py` files across apps: package markers with no business logic.
- `static/assets/js/plugins/*`, `static/assets/css/plugins/*`, theme bundles, icons, images, and `node_modules/*`:
  - provide UI framework, icons, charts, tables, editors, and HTMX distribution
  - are important operational dependencies but not original system logic
- Documentation decision:
  - they are intentionally summarized here rather than documented file-by-file.

## 5. Data Flow Explanation
### 5.1 Asset Data Flow
```text
User input -> AssetForm -> Asset model validation -> save Asset
           -> sync depreciation -> sync installed software
           -> sync dynamic attributes -> append location history
           -> asset detail/list/report/dashboard queries
```

### 5.2 Ticket Data Flow
```text
Ticket form -> FaultTicket -> SLA due date + timestamps
            -> workflow updates/comments/attachments/resolution
            -> optional maintenance record creation
            -> ticket reports + dashboard + SMS notifications
```

### 5.3 GPS Data Flow
```text
Tracker device -> /iot/gps/ingest/ -> TrackerDevice authentication
               -> GPSReading validation/save -> last_seen_at update
               -> assets.views._asset_gps_context
               -> HTMX GPS card + map panel
               -> Leaflet/OpenStreetMap rendering in browser
```

### 5.4 Notification Data Flow
```text
Domain event -> signal / management command -> notifications.sms
             -> provider request or skip/failure decision
             -> SMSNotificationLog persisted
             -> optional Notification / Alert records
```

### 5.5 Reporting Data Flow
```text
User opens report -> report queryset + aggregation
                  -> HTML template
                  -> optional export branch
                  -> CSV writer or custom PDF builder
```

### 5.6 Inter-Component Relationships
- `accounts.User` and `accounts.Department` sit at the center of permissions, ownership, and reporting.
- `assets.Asset` is the primary domain anchor for:
  - assignments
  - location history
  - maintenance
  - software installation
  - audits
  - tickets
  - tracker devices
  - alerts
- `FaultTicket` bridges user support workflow with physical asset maintenance.
- `reports.views` is the read-heavy layer that consolidates data across multiple apps.

## 6. Key Logic and Algorithms
### 6.1 Asset Depreciation
The system uses straight-line depreciation in `assets.models.AssetDepreciation`.

- Annual depreciation:
  - `(purchase_cost - salvage_value) / useful_life_years`
- Years used:
  - calculated using full year anniversaries from `start_date`
- Accumulated depreciation:
  - annual depreciation multiplied by years used
  - capped so it never exceeds the depreciable amount
- Current value:
  - `purchase_cost - accumulated_depreciation`
  - floored at `salvage_value`

Why this approach was likely chosen:

- it is simple, predictable, and academically defensible
- it maps well to institutional asset registers
- it avoids the complexity of declining-balance or tax-specific methods

### 6.2 Asset Status Resolution
Status is derived rather than trusted blindly.

- In `assets.signals.refresh_asset_status()`:
  - if there is open or in-progress maintenance, status becomes `maintenance`
  - else if there is an active assignment, status becomes `assigned`
  - else status becomes `available`
- In `maintenance.signals._refresh_asset_status()`:
  - in-progress `MaintenanceLog` entries are also considered

Why it matters:

- prevents contradictory records such as an asset being “available” while assigned or under repair

### 6.3 Ticket SLA and Workflow Timing
`FaultTicket` computes timing expectations from priority.

- Resolution SLA hours:
  - Critical: 8
  - High: 24
  - Medium: 72
  - Low: 120
- First response expectation hours:
  - Critical: 1
  - High: 4
  - Medium: 8
  - Low: 24

Lifecycle timestamps are stamped automatically when status/assignment/triage states change:

- `triaged_at`
- `first_response_at`
- `assigned_at`
- `resolved_at`
- `closed_at`

Why this approach was likely chosen:

- it supports service-level accountability without needing a separate workflow engine

### 6.4 Dynamic Asset Attributes
The system avoids hard-coding every technical field into `Asset`.

- `AssetAttribute` defines category-specific fields
- `AssetForm` builds form fields dynamically at runtime
- `AssetAttributeValue` stores values as serialized text

Why this approach was likely chosen:

- different asset categories need different metadata
- it reduces schema churn when new asset types appear

### 6.5 Software-to-Asset Restrictions
Installed software is allowed only on computer assets.

- `Asset.is_computer` depends on `AssetCategory.is_computer_category`
- `InstalledSoftware.clean()` and `AssetForm.clean()` enforce the rule

Why it matters:

- prevents nonsensical records such as software on projectors or furniture

### 6.6 GPS Validation and Timestamp Parsing
`iot_monitoring.views.gps_ingest()` accepts machine data but validates it carefully.

- coordinates are parsed as decimals
- accuracy/speed are parsed as floats
- battery is parsed as integer
- timestamps can be omitted, sent as unix epoch, or sent as ISO datetime
- `GPSReading.clean()` enforces latitude/longitude bounds and battery range

Why this matters:

- device integrations are noisy by nature
- validation protects both map display and long-term data quality

### 6.7 SMS Duplicate Prevention
The overdue-assignment SMS command prevents repeat spam.

- `notifications.sms.sms_already_sent()` checks:
  - event type
  - related object
  - normalized phone number
  - notification date
  - successful sent status

Why it matters:

- operations can schedule the command daily without flooding users

### 6.8 Report Export Generation
CSV export is conventional, but PDF export is hand-built.

- `_csv_response()` writes UTF-8 CSV with BOM for spreadsheet compatibility
- `_build_pdf_bytes()` manually constructs a PDF 1.4 document

Why this approach was likely chosen:

- avoids an extra PDF dependency
- works for tabular/academic output
- keeps deployment lightweight

Trade-off:

- the PDF layer is intentionally simple and not a full layout/reporting engine

### 6.9 Legacy Geofence Distance Logic
The older `checkouts` subsystem computes distance using a Haversine-style formula in `GPSLocation.calculate_distance_from_point()`.

Why it still matters in documentation:

- it shows the project previously targeted portable asset checkout and geofence enforcement
- it explains why geofence alert models and admin screens still exist even though the current `Asset` model has moved on

## 7. Configuration and Environment
### 7.1 Core Runtime Settings
- Framework: Django 6.0.2
- Database: SQLite by default
- Time zone in code: `UTC`
- Language: `en-us`
- Static files:
  - `STATIC_URL = /static/`
  - `STATICFILES_DIRS = [BASE_DIR / 'static']`
  - `STATIC_ROOT = BASE_DIR / 'staticfiles'`
- Media files:
  - `MEDIA_URL = /media/`
  - `MEDIA_ROOT = BASE_DIR / 'media'`

### 7.2 Security-Related Settings
- `SECRET_KEY` can be overridden through `DJANGO_SECRET_KEY`
- `DEBUG` is environment-driven via `DJANGO_DEBUG`
- `ALLOWED_HOSTS` has environment override support and defaults to localhost plus deployed hostnames
- `CSRF_TRUSTED_ORIGINS` defaults to the configured public domains

### 7.3 Authentication and Authorization
- custom auth model: `accounts.User`
- login URL: `login`
- login redirect URL: `dashboard`
- logout redirect URL: `login`
- role checks are performed through model properties plus decorators/permission helper modules

### 7.4 Third-Party Libraries in Active Use
- `django-jazzmin`: admin theming
- `crispy_forms` and `crispy_bootstrap4`: form rendering support
- `widget_tweaks`: template-level form styling flexibility
- `django-cors-headers`: CORS support
- `djangorestframework`: installed and configured, but not currently exposed through active API routes
- `pillow`: required for image-related file support in Django
- `qrcode`: required by asset QR code endpoint
- `htmx.org`: front-end partial update behavior

### 7.5 External Service Configuration
SMS configuration comes from:

- `EASY_SEND_SMS_ENABLED`
- `EASY_SEND_SMS_API_KEY`
- `EASY_SEND_SMS_SENDER_ID`
- `EASY_SEND_SMS_BASE_URL`
- `EASY_SEND_SMS_TIMEOUT`
- `EASY_SEND_SMS_DEFAULT_COUNTRY_CODE`

### 7.6 Environment and Deployment Observations
- The project is development-friendly because it runs on SQLite and uses Django’s built-in auth/session stack.
- It is not yet production-hardened for large-scale multi-user deployment:
  - SQLite is not ideal for heavy concurrent access
  - GPS maps depend on external CDN and OpenStreetMap resources
  - ticket attachments require media serving strategy outside debug mode

## 8. Integration Components (if any)
### 8.1 GPS Tracker Integration
- Current implementation:
  - tracker devices send telemetry to `/iot/gps/ingest/`
  - authentication uses `device_id` + API key
  - no firmware source code is stored in this repository
- Academic interpretation:
  - the repository contains the server-side IoT ingestion endpoint, not the embedded code for Arduino/GSM/GPS hardware

### 8.2 SMS Integration
- Easy Send SMS REST endpoint is called using Python’s standard `urllib`
- every attempt is logged to `SMSNotificationLog`
- current event types:
  - ticket created
  - ticket assigned
  - assignment overdue

### 8.3 Front-End Dynamic Integration
- HTMX:
  - asset list filtering
  - dynamic asset category/type fields
  - ticket queue filtering and pagination
  - ticket workflow, comment, attachment, and resolution panels
  - live GPS card/map refresh
- Leaflet/OpenStreetMap:
  - used on asset detail to render recent tracker positions

### 8.4 QR Code Integration
- `assets.views.asset_qr_code()` generates PNG QR codes
- content format:
  - `ICT-ASSET:<asset_tag>|<asset_name>|<location>`

### 8.5 Admin Integration
- Jazzmin gives the admin interface a branded, iconized appearance
- several installed apps, especially `maintenance`, `notifications`, and `checkouts`, rely on admin more than on public views

## 9. Strengths and Limitations
### Strengths
- Strong modular decomposition by domain app.
- Rich and normalized asset model with history, software, depreciation, and audits.
- Good use of role-based access control through user properties, decorators, and permission helpers.
- Ticket workflow is substantially more mature than a basic CRUD ticket list because it includes queue logic, HTMX panels, SLA timing, comments, attachments, and resolutions.
- Reporting is comprehensive and export-ready.
- IoT/GPS integration is lightweight and practical.
- SMS delivery is optional, logged, and duplicate-aware.
- The migration history clearly documents major architectural evolution.

### Limitations
- `checkouts` is a legacy subsystem that still references asset fields removed in `assets` migration `0005`. It should not be described as fully current without refactoring.
- `maintenance` and `assets` both define maintenance concepts, which may confuse maintainers unless responsibilities are documented carefully.
- Some files are placeholders or unused:
  - `maintenance/views.py`
  - `notifications/views.py`
  - `reports/models.py`
  - `reports/admin.py`
  - `core/context_processors.py` is defined but not registered
  - `templates/registration/register.html` is static and not routed
  - `templates/assets/partials/asset_type_field.html` appears orphaned
- `djangorestframework` and `django_filters` are installed, but the current application is mostly server-rendered and exposes no first-class REST API surface.
- `qrcode` is intentionally unpinned and may need installation before QR code generation works.
- GPS ingest is `csrf_exempt` and relies on shared API keys, which is pragmatic for devices but should be protected carefully in production.
- External map rendering depends on third-party network resources.
- SQLite is acceptable for development and academic demonstration, but limited for larger production workloads.

### Likely Design Decisions Behind the Implementation
- Server-rendered Django was likely chosen to keep the project easier to deploy and assess academically than a split SPA/API architecture.
- HTMX was likely adopted to add interactivity without the cost of a full front-end framework.
- The dynamic attribute system suggests the authors expected asset categories to evolve over time.
- Manual PDF creation suggests a deliberate effort to avoid large reporting dependencies.
- SMS logging and migration richness show attention to operational traceability.

## 10. Conclusion
`ICT-MS` is a substantial Django-based ICT operations system rather than a simple inventory CRUD application. Its strongest current capabilities are asset lifecycle management, help desk workflow, reporting, and GPS tracker ingestion. The codebase shows clear evidence of iterative improvement, especially in the migration path from an older asset/checkout model to the current normalized design.

For developers and reviewers, the most important architectural fact is that the live system revolves around `accounts`, `assets`, `tickets`, `reports`, `notifications`, and `iot_monitoring`, while `checkouts` represents an older subsystem that should be treated cautiously. For academic evaluation, the project demonstrates practical system integration across authentication, asset management, maintenance, incident response, analytics, optional SMS, and IoT telemetry, with a codebase that is large enough to show real design trade-offs and system evolution.
