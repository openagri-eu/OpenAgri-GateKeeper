# Multi-Tenancy Shared Deployment Plan

## Purpose

This note documents the target architecture for moving OpenAgri from:

- one deployment per SIP organisation

to:

- one shared deployment with many SIP organisations using the same GK, UI, and service instances

The tenant boundary is the SIP organisation.

## Core Principle

In a shared deployment:

- every user belongs to exactly one tenant
- every protected business resource belongs to exactly one tenant
- every authorization decision must be tenant-aware
- every write must persist tenant ownership

Without this, shared-instance isolation will leak.

## Services In Scope

Primary implementation focus:

- `GK` GateKeeper
- `UI` User Dashboard

Important architectural constraint:

- if `FC` is shared by many SIPs in one instance, then `FC` is also a multi-tenant service, even if users only create farms and parcels through `UI`

Reason:

- `UI` sends the request
- `GK` authorizes the request
- `FC` persists the farm or parcel

So the created record must carry tenant ownership when stored, not just when displayed.

## Recommended Admin Model

Do not use external SIP admins as unrestricted superusers.

Recommended model:

- `platform_admin`
  - internal OpenAgri operator
  - can access all tenants
- `tenant_admin`
  - one or more per SIP
  - can manage only users and data inside that SIP
- `tenant_user`
  - normal SIP user

Why:

- a true superuser normally bypasses all tenant isolation
- that is too dangerous for external SIP organisations in a shared deployment

Conclusion:

- external SIP organisations should have tenant admins, not global superusers

## Tenant Identity

Each SIP needs:

- immutable internal tenant primary key: `tenant_id`
- stable public tenant code: `tenant_code`
- display name: `tenant_name`

Recommended format:

- `tenant_id`
  - database UUID
- `tenant_code`
  - immutable short code such as `sip06`, `sip07`, ...
- optional `tenant_slug`
  - human-readable slug such as `sip06-pois`

Recommendation:

- use `tenant_code` as the stable external identifier in configs, claims, and APIs
- use UUID internally as the primary key

## External SIP Tenant Codes

Source used:

- Horizon OpenAgri external SIP page, accessed March 26, 2026:
  - <https://horizon-openagri.eu/external-sips/>

As of March 26, 2026, that page lists `SIP6` through `SIP14`, which is 9 external SIPs.

Recommended stable tenant codes:

| Tenant Code | Tenant Slug | SIP Name |
| --- | --- | --- |
| `sip06` | `sip06-pois` | Precise Olive Irrigation Solution |
| `sip07` | `sip07-coagriads` | Collaborative Development of Open-Source Aerial Detection ADS |
| `sip08` | `sip08-agritwin` | Agricultural Digital Twin for Intelligent Decision-Making |
| `sip09` | `sip09-spotifly` | Smart Pest Observation and Tracking for Identifying Flying Insects |
| `sip10` | `sip10-smartcherry` | Smartphone-based DSS for Cherry Orchards |
| `sip11` | `sip11-sheepcare` | Smart Health and Efficiency Enhancement through Prediction and Conductimetry |
| `sip12` | `sip12-bugfinderai` | Identifying Insect Pests in Leafy Green Vegetables Using AI Image Recognition |
| `sip13` | `sip13-smartfeed` | Smart Feed System |
| `sip14` | `sip14-scibee` | Smart Community Integrated Beehive |

Current confirmed target:

- 9 external SIP organisations

## Confirmed Business Rules

The current intended rules are:

- one user cannot belong to more than one SIP
- if the same human needs access to another SIP, that SIP gets a separate account
- farms, parcels, and related resources belong to exactly one SIP
- a tenant admin can create users only inside their own SIP

## Open Design Clarifications

### Reports Aggregate Across SIPs

This question means:

- should reporting pages or APIs combine data from multiple SIPs into one view

Examples:

- total farms across all SIPs
- disease trends across all tenants
- cross-tenant benchmarking

Recommendation:

- external tenant users: no cross-tenant reporting
- platform admins: optional cross-tenant reporting if explicitly needed

Default safe rule:

- `RP` should be tenant-scoped unless the caller is a platform admin

### Are Service Roles Tenant-Local Or Global

This question means:

- is a role definition reused globally, or assigned inside a tenant boundary

Recommended model:

- role names can be global templates:
  - `Viewer`
  - `Moderator`
  - `TenantAdmin`
- role assignments must be tenant-local

Example:

- `charlie` may be `Moderator` in `sip10`
- that must not imply `Moderator` in `sip11`

So:

- role definition: reusable
- role assignment: tenant-scoped

## Required Architecture Changes

## 1. GateKeeper Data Model

Add a tenant model in GK.

Suggested entities:

- `Tenant`
  - `id`
  - `code`
  - `slug`
  - `name`
  - `status`
- user to tenant relation
  - one user belongs to one tenant
- group to tenant relation
  - optional, if groups are tenant-owned
- service access assignments constrained by tenant
- scope assignments constrained by tenant

Recommendation:

- tenant admins must never be able to assign users, groups, or scopes outside their tenant

## 2. GateKeeper Authentication Payloads

GK auth and entitlement APIs should return tenant context.

Suggested additions:

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `is_platform_admin`
- `is_tenant_admin`

This gives UI a clean tenant context at login.

## 3. GateKeeper Proxy Enforcement

GK must enforce tenant isolation for:

- list reads
- detail reads
- nested resources
- write requests
- search endpoints
- bulk operations

For each proxied request:

1. resolve caller tenant
2. resolve target resource tenant
3. allow only if tenants match, unless platform admin

## 4. FC Resource Ownership

If FC is shared, FC resources need tenant ownership.

Recommended ownership model:

- `Farm.tenant_id`
- `Parcel` belongs to a `Farm`
- `Activity` belongs to a `Parcel` or `Farm`
- tenant is derived or stored consistently

When UI creates a farm or parcel:

1. UI sends request through GK
2. GK checks `add` permission and tenant membership
3. GK attaches or validates tenant ownership
4. FC persists the record under that tenant

This is why FC cannot be ignored in the final design.

If FC stores no tenant ownership at all, then:

- GK can only filter heuristically
- write safety becomes fragile
- cross-tenant leakage becomes likely

## 5. UI Changes

UI must become tenant-aware but must not be treated as the security boundary.

Needed changes:

- show active tenant context after login
- fetch and store tenant context from GK
- restrict user-management screens to tenant-local users
- restrict role/group assignment screens to tenant-local entities
- never expose cross-tenant selectors to tenant admins

## 6. User Management Rules

Tenant admins should be able to:

- create users only in their own tenant
- assign only tenant-local groups and scopes
- see only users in their own tenant

Tenant admins should not be able to:

- create platform admins
- move users across tenants
- assign roles in another tenant

## 7. Auditing And Logs

Add tenant identifiers to:

- login logs
- proxy logs
- write logs
- admin actions

At minimum, log:

- `tenant_code`
- `user_id`
- `service`
- `action`
- `resource_type`
- `resource_id`

## Implementation Order

1. define the tenant model and invariants
2. add `Tenant` and user-to-tenant ownership in GK
3. add tenant-aware admin and user management in GK
4. add tenant ownership to FC resources
5. return tenant context from GK auth and entitlement APIs
6. enforce tenant filtering in GK proxy reads
7. enforce tenant filtering in GK proxy writes
8. update UI to operate within tenant context
9. add audit logging with tenant metadata
10. add cross-tenant penetration tests

## Test Matrix

For user in `Tenant A`:

- cannot read `Tenant B` farm
- cannot read `Tenant B` parcel
- cannot edit `Tenant B` farm
- cannot create child resources under `Tenant B`
- cannot see `Tenant B` users or groups

## Concrete Implementation Backlog

This section turns the target architecture into a delivery plan.

## Phase 0. Decisions To Freeze

Before code changes, freeze these decisions:

- 9 external SIP organisations will be onboarded in the shared deployment
- external SIP admins are `tenant_admin`, not unrestricted superusers
- one account belongs to exactly one tenant
- farms, parcels, and related assets belong to exactly one tenant
- tenant users do not see cross-tenant reporting

Deliverable:

- signed-off tenant model and role model

## Phase 1. GateKeeper Data Model

Add tenant ownership to GK identity and authorization tables.

Backlog items:

- add `Tenant` model
- add immutable tenant fields:
  - `code`
  - `slug`
  - `name`
  - `status`
- add user-to-tenant relation
- add group-to-tenant relation if tenant-owned groups are used
- add tenant scoping to:
  - service access assignments
  - service scope assignments
  - service role assignments if stored separately
- add database constraints to prevent cross-tenant assignment mistakes

Acceptance criteria:

- every non-platform user has exactly one tenant
- tenant admins cannot create or assign objects outside their tenant
- cross-tenant foreign-key combinations are rejected

## Phase 2. GateKeeper Role Model

Split global operators from tenant operators.

Backlog items:

- define `platform_admin`
- define `tenant_admin`
- define reusable service roles such as:
  - `Viewer`
  - `Moderator`
  - `TenantAdmin`
- make role assignments tenant-local
- ensure `tenant_admin` is enforced by tenant context, not by username or group naming convention alone

Acceptance criteria:

- tenant admin in `sip06` has no admin power in `sip07`
- platform admin can still access all tenants

## Phase 3. GateKeeper Authentication And Entitlements

Expose tenant identity to clients and downstream checks.

Backlog items:

- add tenant context to login response
- add tenant context to `/api/me/`
- add tenant context to service entitlement responses
- expose:
  - `tenant_id`
  - `tenant_code`
  - `tenant_name`
  - `is_platform_admin`
  - `is_tenant_admin`

Acceptance criteria:

- UI can determine current tenant from GK without guessing
- tenant context is stable across refresh and re-login

## Phase 4. GateKeeper User Management

Tenant admins must manage only tenant-local users.

Backlog items:

- tenant admin can create a user only in their own tenant
- tenant admin can list only users in their own tenant
- tenant admin can assign only tenant-local groups and roles
- tenant admin cannot promote another tenant user
- platform admin can create or manage tenants and tenant admins

Acceptance criteria:

- user-management screens and APIs are tenant-scoped
- no cross-tenant user listing is possible for tenant admins

## Phase 5. FC Tenant Ownership

This is the critical persistence layer change for shared FC.

Backlog items:

- add tenant ownership to farms
- ensure parcels inherit or store tenant ownership consistently
- ensure activities, crops, and related objects resolve to a single tenant
- add validation preventing cross-tenant parent-child relationships
- expose tenant-aware filtering in FC where needed

Preferred ownership approach:

- `Farm.tenant_id`
- `Parcel` references `Farm`
- child resources derive tenant through parent or store it redundantly for performance and integrity checks

Acceptance criteria:

- every farm belongs to one tenant
- every parcel belongs to one tenant
- cross-tenant object linkage is impossible

## Phase 6. GateKeeper Proxy Enforcement

GK becomes the operational enforcement boundary for shared services.

Backlog items:

- resolve caller tenant for every proxied request
- resolve target tenant for every proxied resource
- enforce tenant equality for reads
- enforce tenant equality for writes
- enforce tenant filtering for list endpoints
- enforce tenant filtering for search and nested endpoints
- ensure create requests stamp or validate tenant ownership before forwarding

Acceptance criteria:

- tenant A cannot read tenant B resources through GK
- tenant A cannot mutate tenant B resources through GK
- create requests from tenant A always create tenant A data

## Phase 7. User Dashboard Changes

UI must operate in explicit tenant context.

Backlog items:

- fetch tenant context after login
- display active tenant in session/header context
- restrict user-management screens to current tenant
- remove cross-tenant selectors for tenant admins
- ensure forms creating farms/parcels/users run inside current tenant context
- add clear platform-admin vs tenant-admin UI separation

Acceptance criteria:

- tenant admin sees only their tenant users and assets
- platform admin can switch or inspect tenants explicitly
- no UI path accidentally exposes cross-tenant lists

## Phase 8. Reporting Rules

Define reporting access before RP is shared.

Backlog items:

- make default reporting tenant-scoped
- explicitly define any platform-level cross-tenant reporting endpoints
- block tenant users from requesting cross-tenant aggregates

Acceptance criteria:

- tenant users receive only tenant-local reports
- cross-tenant reporting exists only for explicit platform-admin use cases

## Phase 9. Migration Strategy

You are moving from isolated deployments to one shared deployment, so data migration must preserve ownership.

Backlog items:

- create tenant records for `sip06` to `sip14`
- map each existing SIP dataset to a tenant
- import GK users with tenant ownership
- import FC data with tenant ownership
- verify all foreign-key relationships after migration
- run read/write isolation tests after each tenant import

Acceptance criteria:

- all imported users belong to the correct tenant
- all imported farms/parcels belong to the correct tenant
- no data is left without tenant ownership

## Phase 10. Testing And Penetration Coverage

Extend the existing GK proxy penetration testing to cover multi-tenancy explicitly.

Backlog items:

- tenant A allowed read succeeds
- tenant A forbidden read is empty, `404`, or `403` depending on endpoint policy
- tenant A allowed write succeeds if action is granted
- tenant A forbidden write fails
- tenant admin cannot manage tenant B users
- stale or missing tenant-owned targets are reported clearly as skipped/inconclusive where appropriate

Acceptance criteria:

- automated tests fail on any cross-tenant leak
- audit logs include tenant metadata for every failure and mutation

## Recommended Delivery Sequence

Recommended order of implementation:

1. freeze tenant and role decisions
2. implement GK tenant model
3. implement GK auth and user-management changes
4. implement FC tenant ownership
5. implement GK proxy tenant enforcement
6. implement UI tenant context and tenant-admin flows
7. migrate tenant data
8. run cross-tenant penetration tests

## Main Risk Areas

Pay special attention to:

- stale scope assignments pointing at missing FC resources
- action permissions without tenant scope
- cached FC metadata without tenant ownership
- nested list endpoints leaking cross-tenant children
- user-management endpoints returning cross-tenant data

## Immediate Next Step

Create a technical task breakdown for:

- GK schema changes
- GK auth/API changes
- FC schema changes
- UI changes
- migration scripts
- penetration tests

That task breakdown should be the implementation tracker for the actual work.

For tenant admin in `Tenant A`:

- can create users only in `Tenant A`
- can assign roles only in `Tenant A`
- cannot view `Tenant B` users or data

For platform admin:

- can access all tenants

## Main Recommendation

Proceed with:

- one shared deployment
- tenant admins instead of external superusers
- tenant-aware GK model
- tenant-owned FC records
- tenant-aware UI

Do not proceed with:

- multiple unrestricted external superusers
- UI-only tenant filtering
- shared FC records without tenant ownership
