from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "contingency-decision-runtime.html"
DATA_JS = ROOT / "contingency-ontology-data.js"


def _runtime_html() -> str:
    return HTML.read_text(encoding="utf-8")


def _graph_data_js() -> str:
    return DATA_JS.read_text(encoding="utf-8")


class ContingencyRuntimePresentationTest(unittest.TestCase):
    def test_curated_object_labels_do_not_show_live_row_counts(self) -> None:
        html = _runtime_html()

        self.assertIsNone(re.search(r'label:"[^"]+·\d+"', html))
        self.assertRegex(html, r'\{id:"o-row"[^}]*label:"计划活动"')
        self.assertNotIn("计划行·332", html)

    def test_graph_data_exposes_schema_property_fields(self) -> None:
        data_js = _graph_data_js()

        self.assertIn('"properties": [', data_js)
        self.assertIn('"api": "projectKey"', data_js)
        self.assertIn('"name": "项目主键"', data_js)

    def test_object_inspector_lists_fields_without_live_values(self) -> None:
        html = _runtime_html()

        self.assertIn('<div class="lab">属性字段', html)
        self.assertIn("function propRow", html)
        self.assertNotIn('live "+esc(c.label.split("·")[1]||"?")+" 行', html)
        self.assertNotIn('<div class="lab">讲解备注</div>', html)
