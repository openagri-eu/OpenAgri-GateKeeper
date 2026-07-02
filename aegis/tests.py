from django.test import SimpleTestCase

from aegis.views.api.service_registry_views import (
    _has_fc_service_wide_action,
    _endpoint_matches,
    select_matching_service,
)


class _FakeService:
    """Minimal stand-in for a RegisteredService row (endpoint + methods)."""

    def __init__(self, endpoint, methods):
        self.endpoint = endpoint
        self.methods = methods


class FarmCalendarServiceWideActionTests(SimpleTestCase):
    def test_tenant_admin_can_use_flattened_service_action_without_scope_assignments(self):
        entitlement = {
            "roles": ["tenant_admin"],
            "actions": ["add", "delete", "edit", "view"],
            "assignments": [],
            "unrestricted": False,
        }

        self.assertTrue(_has_fc_service_wide_action(entitlement, "add"))

    def test_scoped_role_does_not_get_service_wide_action_from_flattened_actions(self):
        entitlement = {
            "roles": ["Viewer"],
            "actions": ["view"],
            "assignments": [],
            "unrestricted": False,
        }

        self.assertFalse(_has_fc_service_wide_action(entitlement, "view"))


class EndpointMatchesTests(SimpleTestCase):
    def test_plain_endpoint_matches_ignoring_slashes(self):
        self.assertTrue(_endpoint_matches("api/v1/foo/", "api/v1/foo"))
        self.assertFalse(_endpoint_matches("api/v1/foo/", "api/v1/bar/"))

    def test_template_matches_single_segment_only(self):
        self.assertTrue(_endpoint_matches("api/v1/foo/{id}/", "api/v1/foo/abc-123/"))
        # a template segment must not span a slash
        self.assertFalse(_endpoint_matches("api/v1/foo/{id}/", "api/v1/foo/abc/extra/"))

    def test_plain_endpoint_is_not_treated_as_regex(self):
        # a literal endpoint must match literally, not as a pattern
        self.assertFalse(_endpoint_matches("api/v1/foo/bar/", "api/v1/foo/XXX/"))


class SelectMatchingServiceTests(SimpleTestCase):
    # Registry ordered template-first on purpose: the fix must not depend on
    # DB row order (template-first is what clobbered reporting originally).
    REPORTING = [
        _FakeService("api/v1/openagri-report/{report_id}/", ["GET"]),
        _FakeService("api/v1/openagri-report/irrigation-report/", ["POST", "GET"]),
        _FakeService("api/v1/openagri-report/compost-report/", ["POST"]),
    ]

    def test_generate_routes_to_literal_not_template(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/irrigation-report/", "POST"
        )
        self.assertTrue(matched)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/irrigation-report/")

    def test_retrieval_by_uuid_routes_to_template(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/6a6d9391-7114-45ad-8107-c9eba5329efd/", "GET"
        )
        self.assertTrue(matched)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/{report_id}/")

    def test_matched_path_but_disallowed_method_is_405_not_404(self):
        # POST on a uuid: template matches the path but only allows GET -> 405 semantics
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/6a6d9391-7114-45ad-8107-c9eba5329efd/", "POST"
        )
        self.assertIsNone(entry)
        self.assertTrue(matched)

    def test_no_match_is_404_semantics(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/", "GET"
        )
        self.assertIsNone(entry)
        self.assertFalse(matched)

    def test_options_is_always_allowed_through(self):
        entry, matched = select_matching_service(
            self.REPORTING, "api/v1/openagri-report/compost-report/", "OPTIONS"
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.endpoint, "api/v1/openagri-report/compost-report/")

    def test_pdm_import_literal_and_id_template_coexist(self):
        pdm = [
            _FakeService("api/v1/threat-model/{tm_id}/", ["DELETE", "PATCH"]),
            _FakeService("api/v1/threat-model/import-excel/", ["POST"]),
            _FakeService("api/v1/threat-model/import-json/", ["POST"]),
        ]
        entry, _ = select_matching_service(pdm, "api/v1/threat-model/import-excel/", "POST")
        self.assertEqual(entry.endpoint, "api/v1/threat-model/import-excel/")
        # real DELETE/PATCH on an id still reach the template
        entry, _ = select_matching_service(pdm, "api/v1/threat-model/abc-uuid/", "DELETE")
        self.assertEqual(entry.endpoint, "api/v1/threat-model/{tm_id}/")

    def test_weather_location_literals_and_id_template(self):
        weather = [
            _FakeService("api/v1/locations/locations/{location_id}/", ["DELETE"]),
            _FakeService("api/v1/locations/locations/by-coordinates/", ["GET"]),
            _FakeService("api/v1/locations/locations/unique/", ["POST"]),
        ]
        entry, _ = select_matching_service(
            weather, "api/v1/locations/locations/by-coordinates/", "GET"
        )
        self.assertEqual(entry.endpoint, "api/v1/locations/locations/by-coordinates/")
        entry, _ = select_matching_service(
            weather, "api/v1/locations/locations/some-id/", "DELETE"
        )
        self.assertEqual(entry.endpoint, "api/v1/locations/locations/{location_id}/")
        # GET on an id is unsupported by the service -> matched path, no method -> 405
        entry, matched = select_matching_service(
            weather, "api/v1/locations/locations/some-id/", "GET"
        )
        self.assertIsNone(entry)
        self.assertTrue(matched)
