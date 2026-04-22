# GK Multi-Tenancy File-By-File Plan

## Working Assumption

This plan uses the agreed model:

- `FC` remains unchanged in the first iteration
- `UI` remains unchanged in the first iteration
- `GK` becomes the source of truth for:
  - tenant identity
  - tenant ownership mapping of FC resources
  - tenant-aware access control

That means:

- FC stores farms and parcels
- GK syncs FC resources into `FarmCalendarResourceCache`
- GK decides which tenant owns which FC farm and parcel
- GK enforces that ownership on reads and writes

## Current GK Surfaces To Build On

Already present in GK:

- `DefaultAuthUserExtend`
- `GroupServiceAccess`
- `ServiceRole`
- `ServiceScopeAssignment`
- `FarmCalendarResourceCache`
- `resolve_service_entitlements_for_user()`
- `LoginAPIView`
- `MeAPIView`
- `FarmCalendarScopeAPIView`
- FC proxy enforcement in `service_registry_views.py`

This is a good base for a GK-only first implementation.

## 1. `aegis/models.py`

This file will carry the main schema changes.

## 1.1 Add `Tenant`

Add a new model:

- `Tenant`
  - `id` UUID
  - `code`
  - `slug`
  - `name`
  - `status`

Reason:

- every non-platform user and every tenant-owned GK record must anchor to a tenant

## 1.2 Extend `DefaultAuthUserExtend`

Add:

- `tenant = ForeignKey(Tenant, null=True, blank=True, ...)`
- optional `is_tenant_admin = BooleanField(default=False)`

Keep Django `is_superuser` for internal platform admins only.

Rule:

- external SIP admins should not rely on `is_superuser`

## 1.3 Extend `GroupServiceAccess`

Add:

- `tenant = ForeignKey(Tenant, ...)`

Reason:

- a group-to-service access row must belong to one tenant
- tenant admins must not link groups across tenants

## 1.4 Extend `ServiceScopeAssignment`

Add:

- `tenant = ForeignKey(Tenant, ...)`

Reason:

- current scope assignments identify:
  - service
  - subject user or group
  - role
  - scope type
  - scope id
- but they do not encode tenant ownership directly

The tenant field makes cross-tenant mistakes detectable and enforceable.

Add constraints:

- assigned user tenant must match assignment tenant
- assigned group tenant must match assignment tenant

## 1.5 Extend `FarmCalendarResourceCache`

Add:

- `tenant = ForeignKey(Tenant, null=True, blank=True, ...)`

This is the key GK-only ownership mapping.

Meaning:

- for `resource_type="farm"`, `tenant` is the owning SIP
- for `resource_type="parcel"`, `tenant` is the owning SIP and `farm_id` links it to the root farm

This table becomes the GK-side resource ownership registry for FC.

## 1.6 Optional: extend `RequestLog`

Add:

- `tenant = ForeignKey(Tenant, null=True, blank=True, ...)`

Reason:

- audit and incident review become much easier

## 2. `aegis/migrations/`

Add migrations in this order:

1. create `Tenant`
2. add tenant FK to `DefaultAuthUserExtend`
3. add tenant FK to `GroupServiceAccess`
4. add tenant FK to `ServiceScopeAssignment`
5. add tenant FK to `FarmCalendarResourceCache`
6. add tenant FK to `RequestLog` if desired
7. add integrity constraints and indexes

Add a data migration to:

- seed tenants `sip06` through `sip14`

Do not mix schema creation and complex backfill logic in one migration if avoidable.

## 3. `aegis/admin.py`

This file needs tenant-safe administration.

## 3.1 Tenant admin

Register `Tenant` in admin.

Allow platform admins to:

- create tenant
- edit tenant
- inspect tenant-owned mappings

## 3.2 User admin

Update `DefaultAuthUserExtendAdmin`:

- show tenant
- filter users by tenant for tenant admins
- prevent tenant admins from editing users in another tenant
- prevent tenant admins from assigning another tenant

## 3.3 Scope assignment admin

Update `ServiceScopeAssignmentAdminForm` and admin queryset logic:

- subject user/group choices should be tenant-filtered
- farm/parcel choices should be tenant-filtered from `FarmCalendarResourceCache`
- selected farm/parcel tenant must match assignment tenant

## 3.4 FC cache admin

Update `FarmCalendarResourceCacheAdmin`:

- show tenant column
- filter by tenant
- optionally provide list filters for:
  - tenant
  - resource type

## 4. `aegis/services/entitlement_service.py`

This file should become tenant-aware, not just scope-aware.

Changes:

- include tenant context in normalized entitlement payloads
- ensure action grants are resolved within tenant context
- ensure scope assignments are interpreted only within the user tenant unless platform admin

Potential additions to payload:

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `is_platform_admin`
- `is_tenant_admin`

Important rule:

- a user with `edit` action but no tenant-owned scope must not be treated as globally editable

This is the exact class of issue your Bob test exposed.

## 5. `aegis/views/api/auth_views.py`

This file should expose tenant context to clients.

## 5.1 `LoginAPIView`

Either:

- extend the serializer response

or:

- keep login minimal and rely on `/api/me/`

Recommended:

- expose tenant context through `/api/me/`
- optionally also include it in login response if the current frontend already consumes that shape safely

## 5.2 `MeAPIView`

Add:

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `is_platform_admin`
- `is_tenant_admin`

## 5.3 `FarmCalendarScopeAPIView`

Add tenant metadata to the response so the UI or any client can understand the active tenant context.

## 6. `aegis/views/api/service_registry_views.py`

This is the most important enforcement file.

Current role:

- FC proxy read filtering
- FC write-path action checks
- scope checks

Required tenant changes:

## 6.1 Read path

For every FC response:

- resolve caller tenant from `request.user`
- allow only resources whose cached owner tenant matches caller tenant
- platform admins bypass tenant filter

That means:

- list endpoints must be filtered by tenant-owned farm/parcel roots
- detail endpoints must be filtered by tenant-owned roots
- nested activity and child resources must resolve back to a tenant-owned farm or parcel

## 6.2 Write path

For every FC write:

- resolve caller tenant
- resolve target resource tenant from `FarmCalendarResourceCache`
- allow only if:
  - caller has the action
  - caller tenant matches target tenant
  - or caller is platform admin

## 6.3 Create path

This is the critical GK-only ownership step.

On successful create:

- GK must record the new FC resource in `FarmCalendarResourceCache` with the caller tenant

Examples:

- create farm:
  - new farm cache row gets caller tenant
- create parcel:
  - new parcel cache row gets caller tenant and farm linkage

If create responses already contain created resource IDs, this can be done immediately in GK.

If not, you need a post-create lookup strategy.

## 7. FC Catalog Sync / Cache Sync Code

GK already imports FC catalog data into `FarmCalendarResourceCache`.

Wherever that sync currently lives, update it so tenant ownership is preserved.

Likely service area:

- FC sync/catalog code used by `FarmCalendarCatalogAPIView`
- existing sync helpers referenced from admin and catalog APIs

Required behavior:

- sync must not wipe `tenant` ownership when refreshing existing farm/parcel rows
- sync may update payload/name/farm linkage
- sync must preserve tenant mapping for existing resources

This is essential.

If sync overwrites rows without keeping tenant, tenant ownership will disappear.

## 8. Management Commands

Add GK management commands for operational control.

Suggested commands:

- `bootstrap_tenants`
  - create the 9 SIP tenants
- `assign_user_tenant`
  - map a user to a tenant
- `backfill_fc_resource_tenants`
  - assign tenant ownership to existing farm/parcel cache rows
- `validate_tenant_integrity`
  - detect:
    - users without tenant
    - scope assignments with mismatched tenant
    - FC resources without tenant
    - parcel rows whose farm maps to a different tenant

## 9. Test Files / Test Areas

Add or extend tests around:

- entitlement resolution
- auth payloads
- proxy filtering
- write enforcement
- admin restrictions

Important cases:

- tenant A viewer cannot read tenant B farm
- tenant A moderator can edit tenant A farm
- tenant A moderator cannot edit tenant B farm
- action-only user with no tenant-owned scope cannot patch arbitrary farm
- tenant admin cannot manage tenant B user

## 10. Data Backfill Plan

For existing deployments/data:

1. create tenants `sip06` to `sip14`
2. assign current users to a tenant
3. assign tenant admins
4. map FC farms to tenants in `FarmCalendarResourceCache`
5. map parcels via farm linkage
6. add or repair scope assignments as needed

Because FC is unchanged, this mapping must be correct in GK before enabling shared multi-tenant access.

## 11. Hard Limitation Of The GK-Only First Iteration

This plan works if all protected FC resources can be resolved to a tenant-owned farm or parcel in GK.

If later you encounter FC endpoints where GK cannot reliably infer tenant ownership, then:

- GK-only will stop being robust
- FC will need explicit tenant metadata or stronger parent linkage

For the first iteration, your current architecture suggests GK can carry this responsibility.

## Recommended First Implementation Slice

Implement in this order:

1. `Tenant` model and user tenant field
2. tenant context in `/api/me/` and `/api/farmcalendar-scopes/`
3. tenant field in `FarmCalendarResourceCache`
4. tenant-aware filtering in `service_registry_views.py`
5. tenant-safe admin/queryset restrictions
6. bootstrap/backfill commands

This gets you:

- identity isolation
- FC ownership mapping in GK
- tenant-safe reads
- tenant-safe writes

without changing UI or FC in the first pass.
