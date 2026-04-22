# GateKeeper Authorization Guide For Dashboard + FarmCatalog

This document explains how GateKeeper (GK) handles authentication, authorization, farm/parcel catalog mirroring, token claims, and proxy routing when `UserDashboard` is the user-facing application and `FarmCalendar` (FC) is a downstream service.

The goal is to make the model understandable to both technical and non-technical team members.

## 1. High-Level Idea

GK is the central authority for:

- who the user is
- which groups the user belongs to
- which service the user may access
- which actions are allowed
- which farms or parcels those permissions apply to

`UserDashboard` is the main user-facing application.

`FarmCalendar` is the source of truth for farm and parcel data, but GK keeps a mirrored catalog of those FC resources so permissions can be assigned centrally in GK.

In plain language:

- FC owns the real farms and parcels
- GK keeps a copy of those farm/parcel IDs and names
- GK decides which user/group can access which farm/parcel
- Dashboard reads GK permissions and shows/hides data accordingly
- Dashboard calls services through GK proxy routes

## 2. Responsibility Split

### GateKeeper owns

- users
- groups
- services
- action definitions
- role and scope assignments
- token issuance
- FC farm/parcel catalog mirror
- proxying dashboard requests to downstream services

### FarmCalendar owns

- farm data
- parcel data
- activities, crops, animals, assets, and other FC business data

### UserDashboard owns

- user-facing UX
- which pages and controls are shown
- which requests are made to GK proxy endpoints

## 3. Core GK Concepts

There are five core authorization building blocks in GK.

### 3.1 Users

Users are the actual people who log in.

Stored in:

- `auth_user_extend`

Examples:

- `alice`
- `charlie`
- `edward`

### 3.2 Groups

Groups are containers for permission intent.

Instead of assigning everything directly to every user, you usually:

- create a group
- add users to the group
- assign service scopes to that group

Examples:

- `viewers`
- `moderators`
- `admins`
- or more business-specific groups like `farm_01_viewers`

Stored in:

- `auth_group`
- `auth_user_extend_groups`

### 3.3 Services

A service is a logical application or backend domain.

Example:

- `FarmCalendar`

Stored in:

- `service_master`

Important fields:

- `service_code`
- `service_name`

For FC, the current service code is:

- `FarmCalendar`

### 3.4 Permissions

Permissions are the action vocabulary for a service.

Examples:

- `view`
- `add`
- `edit`
- `delete`

Stored in:

- `permission_master`

One service/action pair should exist only once.

Example:

- `FarmCalendar + view`
- `FarmCalendar + add`
- `FarmCalendar + edit`
- `FarmCalendar + delete`

These are logical action definitions, not yet user access.

### 3.5 Service Roles

Roles are now database-backed.

Stored in:

- `service_role`

A role belongs to a service and maps to one or more permission rows.

Examples for `FC`:

- `Viewer` -> `view`
- `Moderator` -> `view, add, edit`
- `Admin` -> `view, add, edit, delete`

Important fields:

- `service`
- `role_code`
- `role_name`
- `permissions`

### 3.6 Scope Assignments

This is the most important authorization table.

Stored in:

- `service_scope_assignments`

A row here means:

- this user or this group
- has this role
- with actions derived from that role
- on this service
- scoped to this exact farm or parcel

Important fields:

- `service`
- `user` or `group`
- `role_ref` (selected DB-backed role)
- `role` (legacy stored role code, filled automatically)
- `actions` (legacy stored action list, filled automatically from the selected role)
- `scope_type`
- `scope_id`

## 4. What `scope_type` And `scope_id` Mean

`scope_type` tells GK what kind of FC object the scope refers to.

Supported values:

- `farm`
- `parcel`

`scope_id` is the UUID of that exact FC object.

Examples:

- `scope_type = farm`
- `scope_id = a2138fc4-d7e9-481f-b41a-07e145f28f36`

This means:

- the permission applies to that exact farm

Another example:

- `scope_type = parcel`
- `scope_id = 74b99671-fd66-4393-81c1-e5188805fc14`

This means:

- the permission applies to that exact parcel

Important:

- `scope_id` is not a GK-internal fake key
- it should match the real UUID coming from FC

## 5. Why GK Needs A Farm/Parcel Catalog

Users should not assign permissions using random UUIDs they typed by hand.

GK therefore keeps a local mirror of FC farms and parcels in:

- `farmcalendar_resource_cache`

This mirror is used so GK can:

- display readable farm names
- display readable parcel identifiers
- know which farm a parcel belongs to
- provide valid scope targets for permission assignment

Important fields in `farmcalendar_resource_cache`:

- `resource_type`
- `resource_id`
- `name`
- `farm_id`
- `payload`

Meaning:

- `resource_id` = actual FC UUID
- `name` = readable label
- `farm_id` = for parcels, the parent farm UUID
- `payload` = original synced data from FC

This cache is a catalog mirror only.

It is not the source of truth.
FC remains the source of truth.

## 6. How GK Learns About New Farms And Parcels

GK learns about FC farms and parcels through catalog sync.

Command:

```bash
python manage.py sync_farmcalendar_catalog
```

What it does:

1. logs into GK to get an access token
2. calls FC farm and parcel endpoints
3. writes those farms/parcels into `farmcalendar_resource_cache`

What it does not do:

- it does not decide who gets access
- it does not create business permissions automatically
- it does not hard-delete scope assignments

So the process is:

- FC creates a new farm or parcel
- GK sync imports it into catalog cache
- admin can then assign scopes in GK to users/groups

If a farm or parcel is deleted in FC:

- GK sync marks the matching catalog row inactive
- GK soft-deactivates active `ServiceScopeAssignment` rows pointing to that deleted farm/parcel
- GK keeps those scope assignment rows in the database for audit/history

Lazy refresh behavior in GK admin:

1. when the `FarmCalendar Resource Cache` admin page is opened, GK checks the latest `synced_at`
2. if the cache was refreshed less than 1 hour ago, GK does nothing
3. if the cache is older than 1 hour, GK runs a catalog sync before rendering the page
4. if nobody visits that page, no sync runs

This is demand-driven refresh. It avoids a background scheduler while still keeping the catalog reasonably fresh for admins.

## 7. How Access Is Actually Defined

Access is usually defined in three layers.

### Layer 1: Group membership

Example:

- Alice is in `viewers`

### Layer 2: Group has service access

Example:

- `viewers` can access `FarmCalendar`

### Layer 3: Group has scope assignments

Example:

- `viewers`
- service = `FarmCalendar`
- role = `viewer`
- scope_type = `parcel`
- scope_id = `<parcel_uuid>`

That means everyone in `viewers` may view that parcel.

## 8. Recommended Pattern

Use groups by default.

Good pattern:

- define access on groups
- assign users to groups

Avoid direct per-user scope assignments unless there is a real exception.

Why:

- groups are easier to maintain
- permissions stay understandable
- new users can be onboarded by group membership

## 9. Example: Give Alice Access To One Farm And One Parcel

Suppose you want:

- Alice can view Farm A
- Alice can also view Parcel P7

There are two ways to do it.

### Recommended way: group-based

1. Create or choose a group

Example:

- `alice_viewers`

2. Add Alice to that group

3. Add `ServiceScopeAssignment` rows for that group

Row 1:

- `service = FarmCalendar`
- `group = alice_viewers`
- `role = viewer`
- `scope_type = farm`
- `scope_id = <farm_uuid>`

Row 2:

- `service = FarmCalendar`
- `group = alice_viewers`
- `role = viewer`
- `scope_type = parcel`
- `scope_id = <parcel_uuid>`

### Direct user way: allowed but not preferred

Instead of `group`, put:

- `user = alice`

This works, but it is harder to maintain at scale.

## 10. Exact Admin Workflow In GK

This is the practical click path in the Django admin.

### Step A: Confirm the farm/parcel exists in GK catalog

Open:

- `FarmCalendar Resource Cache`

Find:

- the farm row
- or the parcel row

Use the readable labels:

- farm name
- parcel identifier
- parent farm

Copy or note the relevant UUID if needed.

### Step B: Create or reuse a group

Open:

- `Groups`

Either:

- create a new group
- or use an existing one like `viewers`, `moderators`, `admins`

### Step C: Add Alice to that group

Open:

- `User Masters`

Find:

- `alice`

Edit the user and add the group membership.

### Step D: Ensure the group can access the service

Open:

- `Group Services Access`

Create or confirm a row:

- `group = <your group>`
- `service = FarmCalendar`

This is the coarse application-level access.

### Step E: Define actions for the service

Open:

- `Permissions`

Ensure the service has the action vocabulary:

- `view`
- `add`
- `edit`
- `delete`

These are the canonical action names.

### Step F: Create scope assignments

Open:

- `Service Scope Assignments`

Create the rows that matter.

In the admin form:

- choose `Service`
- choose `Subject type`
- choose either `Group` or `Individual user`
- choose `Role`
- choose `Scope type`
- choose the matching `Farm` or `Parcel`

You do not enter `actions` manually in this form anymore.

GK derives them from the selected role:

- `Viewer -> ["view"]`
- `Moderator -> ["view", "add", "edit"]`
- `Admin -> ["view", "add", "edit", "delete"]`

Those mappings are not hardcoded in the admin form anymore.

They come from:

- `Service Roles`
- each role's linked `Permissions`

Example viewer on one parcel:

- `service = FarmCalendar`
- `group = viewers`
- `role = Viewer`
- `scope_type = parcel`
- `scope_id = <parcel_uuid>`

Example moderator on one farm:

- `service = FarmCalendar`
- `group = moderators`
- `role = Moderator`
- `scope_type = farm`
- `scope_id = <farm_uuid>`

Example admin on one farm:

- `service = FarmCalendar`
- `group = admins`
- `role = Admin`
- `scope_type = farm`
- `scope_id = <farm_uuid>`

## 11. How Activities, Crops, Animals, And Other Data Are Controlled

The intended model is:

- access is assigned on `farm` and `parcel`
- downstream FC entities inherit visibility from those scopes

So:

- if Alice can access parcel `P1`
- she should see FC data attached to parcel `P1`

Examples:

- activities for that parcel
- crops in that parcel
- animals/assets if the dashboard associates them through the parcel/farm scope

This avoids per-object ACL complexity.

The main permission boundary is:

- `farm`
- `parcel`

Not:

- every crop
- every activity
- every animal

unless you intentionally design for that later.

## 12. How GK Builds The Final Entitlement For A User

GK resolves a user’s effective entitlement in:

- `aegis/services/entitlement_service.py`

It combines:

1. legacy action permissions via groups
2. legacy action permissions via direct user permissions
3. scoped service assignments from `ServiceScopeAssignment`

The output is normalized into a structure like:

```json
[
  {
    "code": "FarmCalendar",
    "name": "FarmCalendar",
    "roles": ["viewer"],
    "actions": ["view"],
    "scopes": {
      "parcel": ["74b99671-fd66-4393-81c1-e5188805fc14"]
    }
  }
]
```

## 13. How JWTs Carry This Information

On login, GK issues access and refresh tokens.

The access token contains:

- identity fields
- `service_access`

That happens in:

- `aegis/serializers.py`

Meaning:

- dashboard can use `/api/me/`
- or directly decode the access token if needed

## 14. Which Endpoints Matter

### Authentication

- `POST /api/login/`
- `POST /api/token/refresh/`
- `POST /api/logout/`

### Identity and authorization context

- `GET /api/me/`
- `GET /api/farmcalendar-scopes/`
- `GET /api/farmcalendar-catalog/`

### Service gateway

- `GET|POST|PUT|PATCH|DELETE /api/proxy/<service>/<path>`

## 15. How Dashboard Uses GK

Dashboard is configured to call GK as its API base.

Examples in the dashboard repo:

- `proxy/farmcalendar/...`
- `proxy/reporting/...`
- `proxy/irrigation/...`
- `proxy/weather_data/...`

So the request path is:

```text
Browser -> UserDashboard -> GK -> downstream service
```

Token behavior:

- access token goes on normal authenticated API requests
- refresh token is used only when refreshing the session

## 16. What Should Be Editable In GK

Editable:

- users
- groups
- services
- service access
- scope assignments
- permission definitions

Read-only or effectively mirrored:

- `FarmCalendarResourceCache`

Why:

- FC owns farm/parcel truth
- GK should not manually edit mirrored farm/parcel catalog data

## 17. Current Important Design Rule

Catalog sync and authorization assignment are different things.

Catalog sync answers:

- what farms and parcels exist in FC?

Authorization assignment answers:

- who can access which farms and parcels?

These should remain separate.

So:

- `sync_farmcalendar_catalog` updates the GK catalog mirror
- admins assign access explicitly via `ServiceScopeAssignment`

## 18. Operational Rules

### If FC gets new farms/parcels

Run:

```bash
python manage.py sync_farmcalendar_catalog
```

Then assign scopes in GK if needed.

### If FC is reseeded and UUIDs change

You must:

1. reseed FC
2. resync catalog into GK
3. update scope assignments to current UUIDs
4. have users log in again to refresh JWT claims

### If dashboard is the only user-facing app

Recommended deployment:

- Dashboard public
- GK public
- FC internal
- services behind GK proxy

## 19. Key Files

Core GK authorization model:

- `aegis/models.py`
- `aegis/services/entitlement_service.py`
- `aegis/serializers.py`
- `aegis/views/api/auth_views.py`
- `aegis/views/api/service_registry_views.py`
- `aegis/services/fc_catalog_sync.py`
- `aegis/management/commands/sync_farmcalendar_catalog.py`
- `aegis/admin.py`

## 20. Short Summary

If you want to explain the system in one paragraph:

GK is the central authority that knows which users belong to which groups, which groups can access which services, and which farms or parcels those permissions apply to. FC owns the real farm and parcel data, while GK keeps a mirrored catalog of those FC resources so admins can assign permissions using valid farm/parcel IDs. Dashboard logs in through GK, receives authorization context from GK, and sends service requests through GK proxy endpoints. Access to activities and other FC data is then derived from the farm/parcel scopes assigned in GK.

## 21. Practical Authorization Examples

Use the following examples as the expected behavior model.

### Example A: Alice is Viewer on 2 farms

If:

- Alice belongs to `Viewer`
- Alice is assigned `Farm A`
- Alice is assigned `Farm B`

Then Alice should be able to see:

- `Farm A`
- `Farm B`
- all parcels inside those farms
- downstream data inside those farms:
  - activities
  - animals
  - machinery
  - crops
  - assets

And Alice should only be able to:

- view

Alice should not be able to:

- add
- edit
- delete

### Example B: Alice is Viewer on 1 parcel only

If:

- Alice belongs to `Viewer`
- Alice is assigned only `Parcel P7`

Then Alice should be able to see:

- only `Parcel P7`
- downstream data linked to `Parcel P7`

Alice should not see:

- sibling parcels
- unrelated farms
- unrelated downstream data

And Alice should only be able to:

- view

### Example C: Alice is Viewer on two farms, but Moderator on another farm

If:

- Alice has viewer-level access on `Farm A`
- Alice has viewer-level access on `Farm B`
- Alice has moderator-level access on `Farm C`

Then:

- on `Farm A` and `Farm B`, Alice should only be able to view
- on `Farm C`, Alice should be able to view, add, and edit

Important:

- moderator access on `Farm C` must not automatically become moderator access on all farms
- actions are scope-specific

### Example D: Alice is Moderator on one parcel and Admin on one farm

If:

- Alice has moderator-level access on `Parcel P9`
- Alice has admin-level access on `Farm D`

Then:

- on `Parcel P9`, Alice can view, add, and edit
- on `Farm D`, Alice can view, add, edit, and delete
- outside those scopes, Alice has no access

### Default policy for a new user

Recommended default:

- no access at all

That means a new user should not automatically see:

- any farms
- any parcels
- any downstream FC data

until you explicitly assign:

- service access
- and one or more farm/parcel scopes

## 22. Recommended Setup Order

When configuring Farm Calendar access in GK from scratch, use this order.

### Step 1: Create the service

Create the FC service first.

Example:

- `service_code = FC`
- `service_name = Farm Calendar`

### Step 2: Create the permission vocabulary

For FC, create these four canonical permissions in `PermissionMaster`:

- `view`
- `add`
- `edit`
- `delete`

These are the base action names for the service.

### Step 3: Create groups

Create the groups you want to use for user categorization and coarse access.

Examples:

- `Viewer`
- `Moderator`
- `Admin`

You can also use more business-specific names later if needed.

### Step 4: Give groups service-level access

In `Group Services Access`, grant those groups access to `FC`.

This answers:

- can this group access Farm Calendar at all?

### Step 5: Add users to groups

Assign each user to the relevant group or groups.

This answers:

- what type of user is this?

### Step 6: Refresh FC catalog into GK

Make sure FC farms and parcels are present in `FarmCalendar Resource Cache`.

This can happen by:

- opening the `FarmCalendar Resource Cache` admin page
- or running:

```bash
python manage.py sync_farmcalendar_catalog
```

### Step 7: Create farm/parcel scope assignments

In `Service Scope Assignments`, assign the relevant farm or parcel scopes.

The admin form should be interpreted as:

- `Subject type` = who gets the assignment
- `Role` = what actions are allowed
- `Scope type` + `Farm/Parcel` = where those actions apply

Role currently drives actions automatically:

- `viewer -> ["view"]`
- `moderator -> ["view", "add", "edit"]`
- `admin -> ["view", "add", "edit", "delete"]`

### Step 8: Verify with `/api/me`

After assigning users, groups, and scopes, verify the result using:

- `/api/me`
- `/api/farmcalendar-scopes`

This confirms:

- which service access the user has
- which farms/parcels they can see
- which actions apply within those scopes
