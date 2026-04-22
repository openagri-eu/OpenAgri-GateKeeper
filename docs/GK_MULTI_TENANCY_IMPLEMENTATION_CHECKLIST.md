# GK Multi-Tenancy Implementation Checklist

## Scope

This checklist reflects the current implementation constraint:

- implement multi-tenancy primarily in `GK`
- do not require `UI` changes in the first iteration
- do not require `FC` changes in the first iteration

Assumption:

- `UI` will continue sending farm and parcel payloads to `GK`
- `GK` can derive the tenant from the authenticated user and enforce tenant isolation at the proxy boundary

## Important Constraint

This GK-only approach is viable only if tenant ownership can be derived and enforced at `GK` for all relevant FC resources.

That means at least one of these must be true:

- GK stamps tenant ownership into requests in a way FC already stores
- GK can derive tenant ownership from farm/parcel/resource mappings it maintains itself
- all sensitive FC resources can be traced back to a tenant-owned farm or parcel through GK-side logic

If none of those remain true for some FC endpoints, the GK-only model becomes fragile.

## Target Outcome

After implementation:

- each user belongs to exactly one tenant
- tenant admins can create users only inside their tenant
- GK returns tenant context at login and entitlement endpoints
- GK blocks cross-tenant reads
- GK blocks cross-tenant writes
- GK allows allowed-scope operations inside the caller tenant

## Repo Scope

Primary repo:

- `GateKeeper`

Reference repos only:

- `OpenAgri-UserDashboard`
- `farmcalendar`

No first-pass code changes are assumed in those reference repos.

## Phase 1. Tenant Model In GK

### 1.1 Add a `Tenant` model

Fields:

- `id` UUID primary key
- `code` unique, immutable
- `slug` unique, human-readable
- `name`
- `status`
- `created_at`
- `updated_at`

Seed the 9 external SIP tenants:

- `sip06`
- `sip07`
- `sip08`
- `sip09`
- `sip10`
- `sip11`
- `sip12`
- `sip13`
- `sip14`

### 1.2 Assign users to tenants

Add a user-to-tenant relation for all non-platform users.

Rule:

- one GK user belongs to exactly one tenant

### 1.3 Make groups tenant-owned

If GK groups are used for service access and scope assignment, add tenant ownership to groups or introduce tenant-scoped group wrappers.

Reason:

- a tenant admin must not attach a user to a group owned by another tenant

## Phase 2. Tenant-Aware Roles And Admin Types

### 2.1 Split admin types

Implement:

- `platform_admin`
- `tenant_admin`

Recommendation:

- keep Django `is_superuser` only for internal platform operators
- use explicit GK-level tenant admin logic for SIP admins

### 2.2 Keep service role definitions reusable

Examples:

- `Viewer`
- `Moderator`
- `TenantAdmin`

But make all role assignments tenant-local.

## Phase 3. Tenant Context In GK APIs

Update GK APIs to return tenant context.

Endpoints:

- `POST /api/login/`
- `GET /api/me/`
- `GET /api/farmcalendar-scopes/`

Suggested response additions:

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `is_platform_admin`
- `is_tenant_admin`

Reason:

- even without UI changes, this becomes the stable contract for current and future clients

## Phase 4. Tenant-Safe User Management In GK

Restrict tenant admins to tenant-local identity management.

Required behavior:

- tenant admin can list only users in their own tenant
- tenant admin can create users only in their own tenant
- tenant admin can assign only tenant-local groups and roles
- tenant admin cannot see or modify users in another tenant

This affects:

- admin views
- custom APIs
- serializer/queryset filtering

## Phase 5. Tenant Ownership Source For FC Resources

Because FC is not being changed in the first iteration, GK needs a reliable tenant-ownership source.

Recommended approach:

- treat `Farm` as the primary tenant-owned root object
- keep a GK-side ownership mapping for FC resources
- derive parcel and activity tenant from the owning farm

Possible storage options inside GK:

- extend `FarmCalendarResourceCache`
- add tenant ownership fields to cached FC resources
- keep farm-to-tenant and parcel-to-farm mappings in GK

Minimum required mappings:

- `farm_id -> tenant_id`
- `parcel_id -> farm_id`
- downstream resource -> parcel or farm if needed

## Phase 6. Create Flow In GK

Since UI already sends create requests to GK, GK must attach tenant meaning before proxying upstream.

### 6.1 Farm create

On farm create:

1. resolve caller tenant from GK user
2. confirm caller has `add` permission in FC for their tenant
3. proxy create request
4. register the created farm as owned by caller tenant in GK cache/mapping

### 6.2 Parcel create

On parcel create:

1. resolve caller tenant
2. inspect referenced farm
3. ensure referenced farm belongs to caller tenant
4. proxy create request
5. register parcel ownership in GK cache/mapping

### 6.3 Update/delete

On patch/delete:

1. resolve caller tenant
2. resolve target farm/parcel tenant from GK cache/mapping
3. allow only if tenant matches and action is granted

## Phase 7. Read Filtering In GK

Extend the existing GK proxy filtering to enforce tenant boundaries explicitly.

Required behavior:

- list endpoints return only tenant-owned data
- detail endpoints return only tenant-owned resources
- nested resources must inherit tenant checks
- forbidden tenant resources should be filtered or denied consistently

Endpoints to verify at minimum:

- `Farm`
- `FarmParcels`
- `FarmCalendarActivities`

## Phase 8. Write Filtering In GK

Write-path enforcement must use both:

- action permissions
- tenant ownership

Required behavior:

- `edit` without tenant ownership -> deny
- `delete` without tenant ownership -> deny
- `add` creating under another tenant -> deny
- action-only users with no tenant-owned scope -> deny

## Operator Bootstrap

For the clean-start deployment we agreed on:

- exactly one GK platform superuser
- 9 seeded tenants in GK
- one tenant admin per SIP tenant

### Single tenant admin creation

Use:

```bash
python manage.py create_tenant_admin sip06 sip06_admin sip06_admin@example.com 'replace-me' --first-name 'SIP 06' --last-name 'Admin'
```

Effect:

- creates or updates the user
- assigns the user to the tenant
- marks the user as `is_tenant_admin=True`
- ensures the user is not a Django superuser

### Bulk tenant admin bootstrap

Use:

```bash
python manage.py bootstrap_tenant_admins --csv /path/to/tenant_admins.csv --dry-run
python manage.py bootstrap_tenant_admins --csv /path/to/tenant_admins.csv
```

Required CSV columns:

- `tenant_code`
- `username`
- `email`
- `password`

Optional CSV columns:

- `first_name`
- `last_name`

Example CSV:

```csv
tenant_code,username,email,password,first_name,last_name
sip06,sip06_admin,sip06_admin@example.com,replace-me,SIP 06,Admin
sip07,sip07_admin,sip07_admin@example.com,replace-me,SIP 07,Admin
```

### Expected clean-start workflow

1. run migrations in GK
2. keep only one GK superuser for internal platform operations
3. confirm tenants `sip06` to `sip14` exist
4. create one tenant admin per SIP
5. let tenant admins create tenant-local users only
6. let all FC farms and parcels be created through GK so ownership is stamped in GK cache from day one

Important edge case:

- a user with global `edit` action but no tenant-owned farm scope must not be allowed to patch arbitrary farms

## Phase 9. GK Admin And Operational Tools

Add operational support in GK for tenant setup.

Needed capabilities:

- create tenant
- create tenant admin
- assign users to tenant
- inspect tenant-owned scopes
- inspect tenant-owned FC cache mappings

Recommendation:

- add management commands for bootstrap and repair

Examples:

- create tenant records
- create tenant admin
- backfill tenant ownership into GK cache
- validate that no cross-tenant mappings exist

## Phase 10. Testing

Reuse and extend the existing GK proxy pentest work.

### 10.1 Read tests

For tenant A user:

- allowed farm list contains only tenant A farms
- tenant B farm detail is filtered or denied
- tenant B parcel detail is filtered or denied
- tenant B activities are filtered or denied

### 10.2 Write tests

For tenant A user:

- patch allowed farm succeeds only with `edit`
- patch tenant B farm fails
- create parcel under tenant B farm fails

### 10.3 User management tests

For tenant admin:

- can create user in own tenant
- cannot create user in another tenant
- cannot see another tenant’s users

## Concrete GK File Areas Likely To Change

These are the main GK areas likely involved.

Models and migrations:

- `aegis/models.py`
- `aegis/migrations/`

Auth and entitlement APIs:

- `aegis/views/api/auth_views.py`
- `aegis/services/entitlement_service.py`

Proxy enforcement:

- `aegis/views/api/service_registry_views.py`

Admin:

- `aegis/admin.py`

Possibly serializers/forms/views used for user administration:

- relevant API/admin modules under `aegis/views/` and related forms/serializers

## Suggested Delivery Order

1. add tenant model and migrations
2. assign users and groups to tenants
3. update login and entitlement payloads
4. restrict tenant-admin user management
5. add GK-side tenant ownership mappings for FC resources
6. enforce tenant checks in proxy read path
7. enforce tenant checks in proxy write path
8. add bootstrap and validation commands
9. extend penetration tests

## What This Approach Avoids

In the first iteration, this avoids:

- changing UI request formats
- changing FC schema
- changing service deployments

## What This Approach Does Not Remove

It does not remove the need to answer one architectural question:

- where is the source of truth for tenant ownership of FC resources

In this first iteration, the answer is:

- `GK` must hold and enforce that mapping

If later that becomes too brittle, FC tenant ownership will need to become explicit in FC itself.
