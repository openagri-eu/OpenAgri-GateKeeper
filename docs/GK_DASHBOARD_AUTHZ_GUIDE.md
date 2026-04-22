# GateKeeper Authorization Guide For Dashboard + FarmCalendar

This document describes the current GateKeeper model used by the shared OpenAgri deployment.

It reflects the tenant-scoped model that is now implemented in GK.

## 1. High-Level Model

GK is the central authority for:

- who the user is
- which tenant the user belongs to
- which services the user may access
- which actions are allowed
- which farms or parcels a role grant applies to

`UserDashboard` is the user-facing application.

`FarmCalendar` remains the source of truth for real farm and parcel data, but GK keeps a mirrored cache so roles can be granted against stable farm and parcel identifiers.

## 2. Responsibility Split

### GateKeeper owns

- users
- tenants
- service definitions
- permission definitions
- tenant-scoped service roles
- user role grants
- JWT issuance
- entitlement resolution
- FarmCalendar farm and parcel cache
- proxy enforcement for downstream service access

### FarmCalendar owns

- real farm records
- real parcel records
- FC business entities such as activities and other FC-specific resources

### UserDashboard owns

- page rendering and user flow
- reading GK identity and entitlement payloads
- calling downstream services through GK

## 3. Core Authorization Objects

### 3.1 Tenants

Each external SIP is represented as a tenant.

Examples:

- `sip06`
- `sip07`
- `sip08`

Every non-platform user belongs to exactly one tenant.

### 3.2 Users

Users are the actual accounts that log in.

Key user flags:

- `is_superuser`
  - platform admin
- `is_tenant_admin`
  - tenant-scoped admin inside GK

### 3.3 Services

A service is a protected application domain.

Examples:

- `FC`
- `IRM`
- `WD`
- `PDM`
- `RP`

### 3.4 Permissions

Permissions are the atomic actions for a service.

Examples:

- `view`
- `add`
- `edit`
- `delete`

These are stored globally per service/action pair.

### 3.5 Service Roles

Service roles are now tenant-scoped.

A tenant can define its own role catalog for a service.

Examples for `sip06` and `FC`:

- `Viewer`
- `Editor`
- `Admin`

Each role maps to one or more permission rows.

### 3.6 Role Grants

This is the actual access assignment.

A role grant means:

- this tenant user
- gets this tenant-local role
- for this service
- on this farm or parcel scope

So the effective model is:

- `Permission -> Service Role -> Role Grant(User + Scope)`

GK admin now exposes this concept as:

- `Role Grant`

## 4. Farm And Parcel Scopes

GK supports two FC scope types:

- `farm`
- `parcel`

The role grant stores:

- `scope_type`
- `scope_id`

Examples:

- Alice is `Viewer` on `farm <uuid>`
- Bob is `Editor` on `parcel <uuid>`

## 5. Tenant Admin Behavior

Tenant admins use the same GK admin panel as platform admins, but are tenant-scoped.

Tenant admins can:

- see only their own tenant users
- create users only in their own tenant
- create service roles only in their own tenant
- create role grants only for users in their own tenant

Tenant admins cannot:

- create superusers
- see another tenant's users, roles, grants, or FC cache rows
- manage global platform configuration

Tenant admins also receive an implicit FC entitlement in GK so they can use FC flows before the first farm-level role grants exist.

## 6. Platform Admin Behavior

Platform admins are Django superusers.

They can:

- manage all tenants
- manage all users
- manage all services and permissions
- see all FC cache rows
- bypass tenant restrictions

## 7. `/api/me/` Contract

`GET /api/me/` returns:

- user identity
- tenant context
- `is_platform_admin`
- `is_tenant_admin`
- normalized service entitlements

Example shape:

```json
{
  "user": {
    "tenant_code": "sip06",
    "is_platform_admin": false,
    "is_tenant_admin": true
  },
  "services": [
    {
      "code": "FC",
      "roles": ["tenant_admin"],
      "actions": ["add", "edit", "view", "delete"],
      "scopes": {
        "farm": [],
        "parcel": []
      },
      "assignments": [],
      "unrestricted": false
    }
  ]
}
```

`services` entries are normalized to contain:

- `code`
- `name`
- `roles`
- `actions`
- `scopes`
- `assignments`
- `unrestricted`

## 8. FarmCalendar Scope Endpoints

GK exposes two FC-specific helper endpoints:

- `GET /api/farmcalendar-scopes/`
- `GET /api/farmcalendar-catalog/`

### `/api/farmcalendar-scopes/`

Returns a UI-friendly FC entitlement summary for the authenticated user:

- tenant
- roles
- actions
- assignments
- unrestricted flag
- farm and parcel scope lists

### `/api/farmcalendar-catalog/`

Returns GK's mirrored FC farm and parcel cache.

For non-platform users:

- results are tenant-filtered

For platform admins:

- all cached rows are visible

## 9. FC Catalog Mirror

GK stores FC resource mirror rows in:

- `FarmCalendarResourceCache`

These rows are used for:

- role-grant scope selection in admin
- tenant-scoped FC catalog responses
- FC entitlement expansion for tenant admins

The sync flow is:

- FC remains the source of truth
- GK syncs `Farm` and `FarmParcels`
- GK upserts cache rows
- missing FC resources are soft-deactivated in GK cache
- related stale role grants are soft-deactivated

Management command:

```bash
python manage.py sync_farmcalendar_catalog
```

## 10. Authentication Notes

GK login now accepts either:

- username
- email

This applies to:

- JSON login via `POST /api/login/`
- Django admin login

Admin logout is also routed back to:

- `/admin/login/?next=/admin/`

instead of the site login page.
