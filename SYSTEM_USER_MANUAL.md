# ICT-MS System User Manual

Prepared: May 11, 2026  
System: ICT Management System (ICT-MS)

## Contents

- [1. Purpose](#1-purpose)
- [2. User Roles](#2-user-roles)
- [3. Signing In and Out](#3-signing-in-and-out)
- [4. Main Navigation](#4-main-navigation)
- [5. Dashboard](#5-dashboard)
- [6. Asset Management](#6-asset-management)
- [7. Locations](#7-locations)
- [8. Software Catalog](#8-software-catalog)
- [9. Asset Assignments](#9-asset-assignments)
- [10. Maintenance Records](#10-maintenance-records)
- [11. Help Desk Tickets](#11-help-desk-tickets)
- [12. Reports](#12-reports)
- [13. User and Department Management](#13-user-and-department-management)
- [14. GPS Tracking](#14-gps-tracking)
- [15. Administration Area](#15-administration-area)
- [16. Recommended Daily Workflow](#16-recommended-daily-workflow)
- [17. Data Entry Guidelines](#17-data-entry-guidelines)
- [18. Troubleshooting](#18-troubleshooting)
- [19. Glossary](#19-glossary)

## 1. Purpose

ICT-MS is a web-based system for managing ICT assets, asset assignments, maintenance records, help desk tickets, software inventory, reports, and GPS tracking for registered assets.

This manual explains how users operate the system from the browser. It is intended for system administrators, help desk officers, ICT technicians, department users, and management viewers.

## 2. User Roles

Access to menus and actions depends on the role assigned to your account.

| Role | Main Responsibilities |
| --- | --- |
| System Administrator | Manage users, departments, locations, assets, assignments, maintenance records, software, reports, and system setup records in the admin area. |
| Help Desk Officer | View ticket queues, triage issues, assign tickets, update workflow status, add comments, upload attachments, and close help desk work. |
| ICT Technician | Register and update assets, handle assignments, log maintenance, work on assigned tickets, add resolutions, comments, and attachments. |
| Department User | Report ICT issues, follow up on submitted tickets, add comments or attachments when allowed, and view available operational records. |
| Management Viewer | View dashboard information, reports, and ticket status for oversight. Management users cannot create new tickets. |

If a button or menu item is missing, your account may not have permission for that action.

## 3. Signing In and Out

### Sign In

1. Open the ICT-MS site in a browser.
2. Enter your email address.
3. Enter your password.
4. Select **Login**.
5. After a successful login, the system opens the dashboard.

### Sign Out

1. Select the user icon in the top-right header.
2. Select **Sign Out**.
3. The system returns you to the login page.

## 4. Main Navigation

The left sidebar is the main navigation area.

| Menu | Use It To |
| --- | --- |
| Dashboard | View a live summary of ICT operations, assets, tickets, assignments, warranty alerts, and maintenance activity. |
| Assets > All Assets | Search, view, create, update, or delete ICT asset records depending on your role. |
| Assets > Assignments | Track assets issued to staff or visitors and record returns. |
| Assets > Maintenance | Log repairs, upgrades, inspections, and completion details. |
| Assets > Software | Maintain software catalog records and review installation usage. |
| Assets > Locations | Manage physical locations. This is available to administrators. |
| Tickets > All Tickets | View help desk queues, filter tickets, and open ticket details. |
| Tickets > Report Issue | Create a new ICT support ticket. This is hidden for management users. |
| Reports | Open and export operational reports. |
| Users | Manage users and departments. This is available to administrators. |

The top-right user menu gives quick access to Dashboard, Asset Register, Assignments, Tickets, Reports, Maintenance, and Sign Out. It also includes a theme selector for light, dark, and default display modes.

## 5. Dashboard

The dashboard is the first page after login. It gives a quick operational picture of the ICT environment.

Use the dashboard to monitor:

- Total registered assets and asset status distribution.
- Active assignments and overdue returns.
- Open, overdue, and recently resolved tickets.
- Maintenance activity and pending schedules.
- Warranty items expiring soon.
- Recent audit summary information.
- Shortcuts to assets, tickets, assignments, and reports.

Recommended practice: review the dashboard at the start of the day to identify overdue tickets, overdue assignments, warranty alerts, and open maintenance work.

## 6. Asset Management

Assets represent physical ICT items such as computers, printers, networking equipment, projectors, and other registered equipment.

### View Assets

1. Go to **Assets > All Assets**.
2. Use filters to narrow the list:
   - Search by asset tag, name, or serial number.
   - Category.
   - Asset type.
   - Department.
   - Status.
   - Active or inactive state.
3. Select **View** to open an asset detail page.

### Add an Asset

Only administrators and ICT technicians can add assets.

1. Go to **Assets > All Assets**.
2. Select **Add Asset**.
3. Fill in the asset details:
   - Asset tag.
   - Asset name.
   - Category.
   - Asset type.
   - Serial number, if available.
   - Department, if assigned to a department.
   - Purchase record, purchase date, purchase cost, and warranty expiry, if known.
   - Status.
   - Active checkbox.
4. Select the current location if the location is known.
5. If the selected category is a computer category, select installed software from the software catalog.
6. Enter depreciation information when needed:
   - Useful life in years.
   - End-of-life value.
   - Depreciation start date.
7. Select **Save Asset**.

After saving, the system opens the asset detail page.

### Edit an Asset

1. Open **Assets > All Assets**.
2. Select the asset.
3. Select **Edit Asset**.
4. Update the required fields.
5. Select **Save Asset**.

When the location changes, the system stores a new location history record. When computer software selections change, the installed software list is updated.

### Delete an Asset

Only administrators and ICT technicians can delete assets.

1. Open the asset detail page.
2. Select **Delete**.
3. Confirm deletion.

Use deletion carefully. If an asset has operational history, consider marking it inactive or retired instead of deleting it.

### Asset Detail Page

The asset detail page shows:

- Category, type, status, department, serial number, and current location.
- Current assignee, if assigned.
- Purchase cost, warranty expiry, and active state.
- Depreciation method, useful life, annual depreciation, accumulated depreciation, and current book value.
- GPS tracking details, if a tracker is linked.
- Location history.
- Assignment history.
- Maintenance history.
- Installed software for computer assets.

### Asset Status Meanings

| Status | Meaning |
| --- | --- |
| Available | The asset is ready for use and not currently assigned or in maintenance. |
| Assigned | The asset has an active assignment. |
| Maintenance | The asset has open or in-progress maintenance work. |
| Reserved | The asset is reserved and not freely available. |
| Retired | The asset is no longer in normal use. |
| Lost | The asset has been reported lost. |

## 7. Locations

Locations are physical places used for asset tracking, such as buildings, offices, rooms, stores, or labs.

Administrators can manage locations.

### Add a Location

1. Go to **Assets > Locations**.
2. Select **Add Location**.
3. Enter:
   - Location name.
   - Building.
   - Room.
   - Description.
4. Save the location.

### Edit or Delete a Location

1. Go to **Assets > Locations**.
2. Select **View**, **Edit**, or **Delete**.
3. Confirm the action where required.

A location cannot be deleted if it is still referenced by asset location history.

## 8. Software Catalog

The software catalog stores software titles that can be linked to computer assets.

### View Software

1. Go to **Assets > Software**.
2. Search by software name, version, or vendor.
3. Select **View** to see installation usage.

### Add Software

Administrators and ICT technicians can add software.

1. Go to **Assets > Software**.
2. Select **Add Software**.
3. Enter:
   - Name.
   - Version.
   - Vendor.
4. Save the record.

### Link Software to a Computer Asset

1. Open the computer asset.
2. Select **Edit Asset**.
3. Confirm the category is a computer category.
4. In the software section, select software from the catalog.
5. Select **Add Selected Software**.
6. Save the asset.

Software can only be recorded for assets in a computer category.

## 9. Asset Assignments

Assignments record which person has custody of an asset and whether it has been returned.

### View Assignments

1. Go to **Assets > Assignments**.
2. Use filters to search by asset, assignee, issuer, or purpose.
3. Filter by assignment state:
   - All assignments.
   - Active only.
   - Returned only.
4. Select **View** for assignment details.

### Create an Assignment

Administrators and ICT technicians can create assignments.

1. Go to **Assets > Assignments**.
2. Select **New Assignment**.
3. Enter:
   - Asset.
   - Assignee identifier, such as staff ID, national ID, or passport number.
   - Assignee name.
   - Assignee contact.
   - Assigned date.
   - Expected return date, if applicable.
   - Issued by.
   - Purpose.
   - Condition at issue.
   - Notes.
4. Save the assignment.

The system allows only one active assignment per asset. If an asset already has an active assignment, return the previous assignment before creating a new active one.

### Record a Return

1. Open the assignment.
2. Select **Edit Assignment**.
3. Enter the returned date.
4. Enter condition at return and any notes.
5. Save the assignment.

After return, the assignment status changes from active to returned.

## 10. Maintenance Records

Maintenance records track repairs, upgrades, and inspections.

### View Maintenance

1. Go to **Assets > Maintenance**.
2. Search by asset, issue, technician, or notes.
3. Filter by:
   - Status.
   - Maintenance type.
   - Selected asset, if opened from an asset detail page.
4. Select **View** for full details.

### Create a Maintenance Record

Administrators and ICT technicians can create records.

1. Go to **Assets > Maintenance**.
2. Select **New Record**.
3. Enter:
   - Asset.
   - Issue description.
   - Maintenance type: Repair, Upgrade, or Inspection.
   - Start date.
   - End date, if complete.
   - Technician or service provider.
   - Cost.
   - Status.
   - Notes.
4. Save the record.

If the status is **Completed**, enter an end date.

### Complete Maintenance

1. Open the maintenance record.
2. Select **Edit Record**.
3. Change status to **Completed**.
4. Enter the end date, cost, and final notes.
5. Save the record.

Open or in-progress maintenance may affect the asset status shown in the asset register.

## 11. Help Desk Tickets

Tickets are used to report and manage ICT faults, service requests, account issues, software problems, hardware faults, and network complaints.

### Ticket Categories

| Category | Use For |
| --- | --- |
| Hardware Fault | Faults involving a physical asset. Hardware tickets require an affected asset. |
| Software Problem | Application, operating system, or software errors. |
| Account / Login | Password, login, user access, or account issues. |
| Network Complaint | Connectivity, internet, Wi-Fi, or LAN issues. |
| ICT Service Request | General ICT service requests. |
| Other ICT Support | Issues that do not fit the other categories. |

### Priority Levels

| Priority | Typical Resolution Target |
| --- | --- |
| Low | 120 hours |
| Medium | 72 hours |
| High | 24 hours |
| Critical | 8 hours |

The system uses priority to calculate due dates and overdue status.

### Create a Ticket

Management users cannot create tickets. Other authenticated users can report issues.

1. Go to **Tickets > Report Issue** or **Tickets > All Tickets > New Ticket**.
2. Enter:
   - Title.
   - Description.
   - Department.
   - Ticket category.
   - Asset fault checkbox, if the issue is asset-related.
   - Asset, when required.
   - Location, if known.
   - Priority.
3. Save the ticket.

For department users, the department may be preselected and locked to the user's department.

### View Tickets

1. Go to **Tickets > All Tickets**.
2. Use queue cards and filters to narrow the list.
3. Search by ticket ID, title, requester, asset, or location.
4. Filter by status, priority, category, department, assignee, or overdue-only.
5. Select a ticket to open details.

Ticket visibility depends on role:

- Administrators, help desk officers, and management viewers can view all tickets.
- Technicians can view tickets assigned to them and tickets they reported.
- Department users can view tickets they reported.

### Update Ticket Details

Ticket details can be edited when permitted:

- The reporter can edit a ticket while it is still open.
- Help desk officers, administrators, and permitted technicians can update ticket work details.

1. Open the ticket.
2. Select **Edit Ticket**.
3. Update the fields.
4. Save the ticket.

### Manage Ticket Workflow

Users with workflow permission can update status, impact, assignee, due date, escalation, and maintenance requirement.

Common workflow statuses:

| Status | Meaning |
| --- | --- |
| Open | Ticket has been submitted and awaits review. |
| Triaged | Help desk has reviewed the issue. |
| Assigned | Ticket has been assigned to a responsible user. |
| In Progress | Work is underway. |
| Pending User | Waiting for user response or action. |
| Pending Parts | Waiting for required parts or supplies. |
| Resolved | Work has been completed and a resolution recorded. |
| Closed | Ticket is fully closed after resolution. |
| Cancelled | Ticket is cancelled and no further work is expected. |

Notes:

- Tickets moved into active work statuses must have an assignee.
- Use the resolution panel to mark a ticket as resolved.
- A ticket must be resolved before it can be closed.

### Add a Comment

1. Open the ticket.
2. Find the comments panel.
3. Enter the update, diagnosis, or response.
4. Submit the comment.

Comments help maintain an audit trail of communication and troubleshooting.

### Upload an Attachment

1. Open the ticket.
2. Find the attachment panel.
3. Select a file.
4. Add an optional description.
5. Upload the attachment.

Use attachments for screenshots, photos, forms, or supporting documents.

### Resolve a Ticket

1. Open the ticket.
2. Go to the resolution panel.
3. Enter:
   - Resolution summary.
   - Root cause, if known.
   - Action taken.
4. Save the resolution.

The system marks the ticket as **Resolved** and records the resolved time.

### Create Maintenance From a Ticket

For asset-linked tickets that are marked as asset faults or require maintenance:

1. Open the ticket.
2. Select the maintenance creation action if available.
3. The system creates a maintenance record using the ticket title and description.
4. The ticket is updated with a comment and maintenance status.
5. Continue maintenance work from **Assets > Maintenance**.

## 12. Reports

Reports summarize operational data and can be exported.

### Open Reports

1. Go to **Reports**.
2. Select **Open Report** for the required report.
3. Review the on-screen report.

### Export Reports

Each report card includes:

- **CSV** for spreadsheet-compatible export.
- **PDF** for printable report export.

### Available Reports

| Report | Shows |
| --- | --- |
| Ticket Report | Help desk workload, SLA risk, technician performance, and faulty asset trends. |
| Asset Inventory | Full asset register with category, department, location, and status. |
| Assets by Department | Department ownership summary and asset status counts. |
| Assets by Location | Current asset distribution by latest location. |
| Assigned Assets | Active assignment register with assignee and return details. |
| Maintenance Report | Repair, upgrade, and inspection activity with technician status. |
| Software Inventory | Installed software records and deployment coverage. |
| Depreciation Report | Asset purchase values, useful life, depreciation, and book value. |
| Audit Report | Audit runs and item outcomes such as found, missing, damaged, or relocated. |

## 13. User and Department Management

Only administrators can manage users and departments.

### Manage Users

1. Go to **Users > All Users**.
2. Search by name, email, phone, or department.
3. Filter by role or active status.
4. Select **Add User**, **View**, **Edit**, or **Delete**.

When adding a user, enter:

- Email.
- First name.
- Last name.
- Phone number.
- Role.
- Department.
- Active status.
- Password and password confirmation.

When updating a user, leave the new password fields blank to keep the current password.

The system does not allow you to delete the account you are currently using.

### Manage Departments

1. Go to **Users > Departments**.
2. Search existing departments.
3. Select **Add Department**, **View**, **Edit**, or **Delete**.

Department fields:

- Name.
- Code.
- Description.

Departments are used for user ownership, asset ownership, ticket routing, and reporting.

## 14. GPS Tracking

GPS tracking is available for assets linked to active tracker devices.

On an asset detail page, the GPS section shows:

- Device ID.
- Last seen time.
- Tracker active status.
- Latest latitude and longitude.
- Accuracy.
- Battery level.
- Recorded time.
- Map link when coordinates exist.

The GPS card and map refresh automatically every 20 seconds.

Tracker devices and API keys are managed by administrators in the Django admin area. GPS readings are received through the system's tracker ingestion endpoint.

## 15. Administration Area

The Django administration area is available at `/admin/` for users with staff access.

Administrators may use this area for setup records that are not fully managed from the main sidebar, including:

- Asset categories.
- Asset types.
- Suppliers.
- Asset purchases.
- Asset attributes.
- Asset audits and audit items.
- Tracker devices and GPS readings.
- Formal maintenance logs and schedules.
- Notifications, alerts, and SMS notification logs.

Use the main ICT-MS screens for day-to-day operations. Use the admin area for setup, corrections, and records that are not exposed in the normal user interface.

## 16. Recommended Daily Workflow

### System Administrator

1. Review the dashboard for overdue tickets, overdue returns, and maintenance warnings.
2. Confirm user and department records are current.
3. Review reports for management or audit needs.
4. Check locations, categories, asset types, and tracker devices when setup changes are required.

### Help Desk Officer

1. Open **Tickets > All Tickets**.
2. Review open and overdue queues.
3. Triage new tickets.
4. Assign tickets to technicians.
5. Follow up on pending user or pending parts tickets.
6. Confirm resolution details before closure.

### ICT Technician

1. Review assigned tickets.
2. Update ticket workflow as work progresses.
3. Add comments and attachments for troubleshooting records.
4. Create maintenance records for asset repair work.
5. Update asset, assignment, and maintenance records after work is complete.

### Department User

1. Report new ICT issues through **Tickets > Report Issue**.
2. Track submitted tickets from **Tickets > All Tickets**.
3. Add comments or attachments when the support team needs more information.
4. Confirm when resolved work has addressed the issue.

### Management Viewer

1. Open the dashboard for operational status.
2. Review reports for asset, maintenance, ticket, and audit summaries.
3. Use ticket queues to monitor workload and SLA risk.

## 17. Data Entry Guidelines

Use consistent data entry so reports remain reliable.

- Use unique, standardized asset tags.
- Record serial numbers exactly as shown on the equipment.
- Select the correct department before selecting an asset on ticket forms.
- Always enter expected return dates for temporary assignments.
- Record return condition when assets are returned.
- Close maintenance records only after the work is complete and the end date is known.
- Use ticket comments for progress updates instead of overwriting the original description.
- Add resolution summaries that a non-technical reader can understand.
- Avoid deleting records that have audit or operational value. Prefer inactive, retired, returned, completed, resolved, or closed states where appropriate.

## 18. Troubleshooting

| Problem | What To Check |
| --- | --- |
| I cannot see a button. | Your role may not have permission for that action. Contact the system administrator. |
| I cannot create a ticket. | Management users cannot create tickets. Confirm your role. |
| I cannot select an asset on a ticket. | Select the department first. Only assets in the selected department are shown. |
| A hardware ticket requires an asset. | Hardware tickets are treated as asset faults, so an affected asset must be selected. |
| I cannot assign an asset. | Check whether the asset already has an active assignment. Record the previous return first. |
| I cannot complete maintenance. | Enter an end date when changing maintenance status to Completed. |
| A location cannot be deleted. | The location is referenced in asset location history. Keep it for audit history. |
| GPS details do not appear. | Confirm that a tracker device is linked, active, and sending readings. |
| A report export does not download. | Retry from the report card using CSV or PDF. If the issue continues, contact the administrator. |

## 19. Glossary

| Term | Meaning |
| --- | --- |
| Asset | A registered ICT item such as a computer, printer, network device, or projector. |
| Asset Tag | The unique identifier used to label and track an asset. |
| Assignment | A record showing that an asset was issued to a person. |
| Current Location | The latest known physical location from location history. |
| Depreciation | A calculated reduction in asset book value over useful life. |
| Help Desk Ticket | A support case reported by a user or managed by ICT staff. |
| SLA Due Date | The target time by which a ticket should be resolved based on priority. |
| Maintenance Record | A repair, upgrade, or inspection record for an asset. |
| Software Catalog | The list of software titles that can be linked to computer assets. |
| Tracker Device | A GPS-capable device linked to an asset for location readings. |
| Audit | A review of assets to confirm whether they are found, missing, damaged, or relocated. |
