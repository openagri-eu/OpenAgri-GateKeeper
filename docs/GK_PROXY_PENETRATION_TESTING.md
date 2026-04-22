# GK Proxy Penetration Testing

This document describes how to test whether GateKeeper correctly enforces:

- read visibility by farm/parcel scope
- action permissions by role
- scope restrictions on write requests
- direct forged requests that bypass the UI

The goal is to verify that a user cannot use the dashboard token to access or mutate FarmCalendar resources outside their allowed scope.

## Scope

These tests target:

- `GateKeeper` as the policy and proxy enforcement boundary
- `FarmCalendar` as the upstream data service
- `UserDashboard` only as a source of real browser requests and tokens

These tests should be run against GK endpoints directly.

## Core Rules To Verify

For each user:

1. Allowed reads should succeed.
2. Forbidden reads should be filtered or return `404`.
3. Allowed writes with allowed actions should pass GK.
4. Allowed writes with forbidden actions should return `403`.
5. Writes outside scope should return `403`.
6. Admin or superuser should be unrestricted.

## Relevant GK Endpoints

Authentication and inspection:

- `POST /api/login/`
- `GET /api/me/`
- `GET /api/farmcalendar-scopes/`

Read targets:

- `GET /api/proxy/farmcalendar/api/v1/Farm/`
- `GET /api/proxy/farmcalendar/api/v1/Farm/<farm_uuid>/`
- `GET /api/proxy/farmcalendar/api/v1/FarmParcels/`
- `GET /api/proxy/farmcalendar/api/v1/FarmParcels/<parcel_uuid>/`
- `GET /api/proxy/farmcalendar/api/v1/FarmCalendarActivities/?format=json&parcel=<parcel_uuid>`

Write targets:

- `PATCH /api/proxy/farmcalendar/api/v1/Farm/<farm_uuid>/?format=json`
- `PATCH /api/proxy/farmcalendar/api/v1/FarmParcels/<parcel_uuid>/?format=json`

## Recommended Test Users

Use the configured users and compare their effective scopes from GK:

- `admin`
- `alice`
- `bob`
- `charlie`

Expected patterns:

- `admin`: unrestricted
- `alice`: viewer on assigned farms/parcels only
- `bob`: moderator on assigned farms/parcels only
- `charlie`: based on direct or group assignment

## Test Method

### 1. Get a token

```bash
curl -sS -X POST "$GK_BASE/login/" \
  -d "username=$USER" \
  -d "password=$PASS"
```

Extract `access`.

### 2. Inspect the user’s effective access

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$GK_BASE/farmcalendar-scopes/"
```

Record:

- allowed farm UUIDs
- allowed parcel UUIDs
- allowed actions
- unrestricted flag

### 3. Pick targets

For each user, select:

- one allowed farm
- one forbidden farm
- one allowed parcel
- one forbidden parcel

### 4. Run read tests

Verify:

- allowed farm detail returns `200`
- forbidden farm detail returns filtered result or `404`
- list endpoints only contain allowed data

### 5. Run write tests

Verify:

- viewer cannot edit inside allowed scope
- moderator can edit allowed scope when you explicitly choose to run a positive write test
- any user is blocked from writing outside scope

## Expected Outcomes

### Alice as Viewer

- can read allowed farms/parcels
- cannot read forbidden farms/parcels
- cannot `PATCH`
- cannot `DELETE`

### User With No FC Entitlement

If a user has:

- no FC group service access
- no FC direct scope assignment
- no FC group-derived scope assignment

then GK should deny proxied FarmCalendar access entirely.

Expected result:

- proxied FC endpoints should return `403`
- example error:
  - `"You do not have access to this FarmCalendar service."`

This is stricter and safer than returning an empty list, because it prevents accidental data leaks when no FC entitlement exists at all.

### Bob as Moderator

- can read allowed farms/parcels
- can `PATCH` inside allowed scope
- cannot `DELETE` unless explicitly granted
- cannot write outside allowed scope

### Charlie

- should match whatever user or group scope is assigned

### Admin

- unrestricted

## Useful Status Codes

- `200`: request passed through GK
- `403`: GK blocked by action or scope
- `403`: GK blocked because the user has no FC entitlement at all
- `404`: resource inaccessible after filtering or target unavailable
- `401`: bad token or session problem
- `500`: bug or unexpected proxy failure

## GK Logs To Watch

Useful GK log patterns:

- successful proxy:
  - `GK PROXY ... scope_filter=on`
- blocked by action:
  - `reason=missing_action`
- blocked by scope:
  - `reason=scope`

## Important Limitation

GK now enforces:

- read-path scope filtering
- write-path action checks
- write-path scope checks when target scope can be resolved from:
  - the request body
  - or the upstream resource

Some unusual FC write endpoints may still need endpoint-specific target resolution if they hide farm/parcel linkage behind non-standard payload shapes.

## Recommended First Matrix

1. Alice `GET` allowed farm -> `200`
2. Alice `GET` forbidden farm -> `404`
3. Alice `PATCH` allowed farm -> `403`
4. Bob `PATCH` forbidden farm -> `403`
5. Charlie `PATCH` allowed farm -> `403` when Charlie is only `Viewer`
6. Charlie `PATCH` forbidden farm -> `403`
7. Optional manual positive write check: `PATCH` an allowed farm with a user that actually has `edit`

## Runnable Script

Use:

- [gk_proxy_pentest.sh](/home/pranav/PyCharm/OpenAgri/GateKeeper/scripts/gk_proxy_pentest.sh)

That script:

- fetches tokens
- prints effective scopes
- auto-discovers allowed and forbidden farm/parcel targets from GK
- runs read tests
- runs scoped read checks for a user with real FC access, if one is configured
- includes parcel detail and activity reads for that scoped-access user
- asserts expected outcomes and exits non-zero if they fail
- runs optional non-destructive write tests
- keeps destructive write checks out of the default script flow
- skips allowed-scope checks gracefully when a user has no assigned farms or parcels
- still runs forbidden-target checks when possible, which is useful for verifying the default no-access posture

Manual UUID variables are optional overrides now. If you already know the exact target IDs you want to test, you can still export them before running the script.

### Default Usage

```bash
cd /home/pranav/PyCharm/OpenAgri/GateKeeper
bash ./scripts/gk_proxy_pentest.sh
```

### With Write Tests Enabled

```bash
cd /home/pranav/PyCharm/OpenAgri/GateKeeper
ENABLE_WRITE_TESTS=1 bash ./scripts/gk_proxy_pentest.sh
```

Write mode now sends only `PATCH` requests that are expected to be blocked by GK and asserts `403` responses. It does not send `DELETE` requests or admin cleanup writes.

### Optional Manual Overrides

```bash
ALICE_ALLOWED_FARM=<uuid> \
ALICE_FORBIDDEN_FARM=<uuid> \
ENABLE_WRITE_TESTS=1 \
bash ./scripts/gk_proxy_pentest.sh
```
