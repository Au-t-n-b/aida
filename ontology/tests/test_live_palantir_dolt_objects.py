"""Live acceptance tests for real Dolt data through the Foundry-shaped API.

These tests are intentionally not part of the offline unit-test safety net. They
hit the running ontology service over HTTP and should fail hard in acceptance
mode when the service, Dolt, or the Dolt-backed TestCase data is incomplete.

Run (PowerShell):
    $env:RUN_DOLT_ACCEPTANCE="1"
    python -B ontology\tests\test_live_palantir_dolt_objects.py -v

Optional:
    $env:ONTOLOGY_ACCEPTANCE_BASE_URL="http://127.0.0.1:8011"
"""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RUN_ACCEPTANCE = os.getenv("RUN_DOLT_ACCEPTANCE") == "1"
BASE_URL = (os.getenv("ONTOLOGY_ACCEPTANCE_BASE_URL") or "http://127.0.0.1:8011").rstrip("/")
ONTOLOGY_ID = os.getenv("ONTOLOGY_ACCEPTANCE_ONTOLOGY") or "default"
OBJECT_TYPE = "TestCase"
EXPECTED_TEST_CASE_TOTAL = 29
REQUIRED_TEST_CASE_FIELDS = (
    "testCaseId",
    "testCaseName",
    "caseCode",
    "testPurpose",
    "level3Category",
)


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = f"?{urlencode(params, doseq=True)}" if params else ""
    url = f"{BASE_URL}{path}{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            raw_body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"GET {url} returned HTTP {exc.code}: {detail[:500]}") from exc
    except TimeoutError as exc:
        raise AssertionError(f"GET {url} timed out") from exc
    except URLError as exc:
        raise AssertionError(f"Could not reach ontology service at {BASE_URL}: {exc.reason}") from exc

    body = raw_body.decode("utf-8")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"GET {url} did not return valid JSON: {body[:500]}") from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"GET {url} returned {type(payload).__name__}, expected JSON object")
    return payload


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


@unittest.skipUnless(
    RUN_ACCEPTANCE,
    "set RUN_DOLT_ACCEPTANCE=1 to run live Palantir/Dolt acceptance tests",
)
class LivePalantirDoltObjectAcceptanceTests(unittest.TestCase):
    def test_testcase_object_type_metadata_is_published(self):
        object_type = _get_json(f"/api/v2/ontologies/{ONTOLOGY_ID}/objectTypes/{OBJECT_TYPE}")

        self.assertEqual(object_type.get("apiName"), OBJECT_TYPE)
        self.assertEqual(object_type.get("primaryKeyPropertyApiNames"), ["testCaseId"])
        properties = object_type.get("properties")
        self.assertIsInstance(properties, dict)
        for field in REQUIRED_TEST_CASE_FIELDS:
            self.assertIn(field, properties)

    def test_testcase_objects_are_complete_from_real_dolt(self):
        page = _get_json(
            f"/api/v2/ontologies/{ONTOLOGY_ID}/objects/{OBJECT_TYPE}",
            params={"limit": 500, "offset": 0},
        )

        items = page.get("items")
        self.assertIsInstance(items, list)
        self.assertEqual(
            page.get("total"),
            EXPECTED_TEST_CASE_TOTAL,
            "TestCase total must match the Dolt-loaded 19_test_case table row count.",
        )
        self.assertEqual(
            len(items),
            EXPECTED_TEST_CASE_TOTAL,
            "The acceptance page limit should return every TestCase row.",
        )
        self.assertGreater(len(items), 0, "Dolt-backed TestCase API returned an empty table.")

        seen_keys: set[str] = set()
        duplicate_keys: list[str] = []
        missing_by_field: dict[str, list[str]] = {field: [] for field in REQUIRED_TEST_CASE_FIELDS}
        for index, row in enumerate(items):
            self.assertIsInstance(row, dict)
            row_label = f"row[{index}]"
            key = str(row.get("testCaseId") or "").strip()
            if not key:
                missing_by_field["testCaseId"].append(row_label)
            elif key in seen_keys:
                duplicate_keys.append(key)
            else:
                seen_keys.add(key)
                row_label = key

            for field in REQUIRED_TEST_CASE_FIELDS:
                if _is_blank(row.get(field)):
                    missing_by_field[field].append(row_label)

        missing_by_field = {field: labels for field, labels in missing_by_field.items() if labels}
        self.assertFalse(duplicate_keys, f"Duplicate TestCase primary keys: {duplicate_keys}")
        self.assertEqual(
            missing_by_field,
            {},
            "Dolt-backed TestCase rows are missing required acceptance fields.",
        )


if __name__ == "__main__":
    unittest.main()
