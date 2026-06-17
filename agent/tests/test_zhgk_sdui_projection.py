from agent.skills.zhgk.sdui import _build_assessment_panel, _build_macro_rail, _build_metrics_card


def test_zhgk_metrics_card_uses_dedicated_golden_metrics_node():
    state = {
        "overall_progress": 43,
        "project": {"intent": "survey_work", "generation_cooling": "A3-液冷"},
        "steps": [
            {"id": "preflight", "status": "completed"},
            {"id": "intent_select", "status": "completed"},
        ],
        "metrics": {
            "filtered_count": 76,
            "sub_scenes": ["硬装入场", "通液前", "加电前"],
        },
    }

    card = _build_metrics_card(state)

    assert card is not None
    dumped = card.model_dump(mode="json")
    assert dumped["id"] == "golden-metrics"
    assert dumped["children"][0]["type"] == "ZhgkGoldenMetrics"
    assert dumped["children"][0]["progress"] == 43
    assert dumped["children"][0]["items"][0]["title"] == "意图"
    assert len(dumped["children"][0]["items"]) == 4
    titles = [it["title"] for it in dumped["children"][0]["items"]]
    assert titles == ["意图", "代际制冷", "勘测条目", "勘测场景"]


def test_golden_metrics_shows_base_count_at_determine_gen_hitl(monkeypatch, tmp_path):
    from agent.skills.zhgk.sdui import _build_metrics_card

    table = tmp_path / "入场评估标准表.xlsx"
    from agent.tests.test_survey_item_stats import _write_mini_base_table
    _write_mini_base_table(table)
    monkeypatch.setattr(
        "agent.skills.zhgk.path_config.get_base_table_path",
        lambda: str(table),
    )

    state = {
        "overall_progress": 25,
        "project": {"intent": "survey_work"},
        "steps": [
            {"key": "determine_gen", "status": "hitl", "metrics": {"base_table_count": 4}},
        ],
        "hitl": {"step": "determine_gen"},
    }
    card = _build_metrics_card(state)
    items = card.model_dump(mode="json")["children"][0]["items"]
    by_title = {it["title"]: it["value"] for it in items}
    assert by_title["勘测条目"] == "4 条"
    assert by_title["代际制冷"] == "—"


def test_golden_metrics_shows_filtered_count_after_gen_cooling(monkeypatch, tmp_path):
    from agent.skills.zhgk.sdui import _build_metrics_card

    table = tmp_path / "入场评估标准表.xlsx"
    from agent.tests.test_survey_item_stats import _write_mini_base_table
    _write_mini_base_table(table)
    monkeypatch.setattr(
        "agent.skills.zhgk.path_config.get_base_table_path",
        lambda: str(table),
    )

    state = {
        "overall_progress": 30,
        "project": {"intent": "survey_work", "generation_cooling": "A3-液冷"},
        "steps": [
            {
                "key": "determine_gen",
                "status": "completed",
                "metrics": {
                    "generation_cooling": "A3-液冷",
                    "base_table_count": 4,
                    "filtered_count": 2,
                    "sub_scenes": ["硬装入场", "通液前", "加电前"],
                },
            },
        ],
    }
    card = _build_metrics_card(state)
    items = card.model_dump(mode="json")["children"][0]["items"]
    by_title = {it["title"]: it["value"] for it in items}
    assert by_title["勘测条目"] == "2 条"
    assert by_title["代际制冷"] == "A3-液冷"
    assert "硬装入场" in by_title["勘测场景"]


def test_zhgk_progress_rail_shows_survey_work_compact_steps():
    state = {
        "project": {"intent": "survey_work"},
        "steps": [
            {"key": "preflight", "status": "completed"},
            {"key": "intent_select", "status": "completed"},
            {"key": "determine_gen", "status": "completed"},
            {"key": "filter_build", "status": "completed"},
            {"key": "method_split", "status": "completed"},
            {"key": "data_append", "status": "completed"},
            {"key": "confirm_table", "status": "completed"},
            {"key": "task_dispatch", "status": "completed"},
            {"key": "wait_survey", "status": "completed"},
            {"key": "assess", "status": "running"},
            {"key": "issue_list", "status": "pending"},
            {"key": "resurvey_gate", "status": "pending"},
        ],
    }

    rail = _build_macro_rail(state)

    assert rail is not None
    dumped = rail.model_dump(mode="json")
    titles = [s["title"] for s in dumped["steps"]]
    assert 3 < len(titles) <= 8
    assert "建表确认" in titles
    assert "现场勘测" in titles
    assert "AI 评估" in titles


def test_zhgk_progress_rail_uses_current_step_when_prior_steps_were_skipped():
    state = {
        "current_step": "issue_list",
        "project": {"intent": "survey_work"},
        "steps": [
            {"key": "preflight", "status": "completed"},
            {"key": "confirm_table", "status": "completed"},
            {"key": "task_dispatch", "status": "completed"},
            {"key": "wait_survey", "status": "completed"},
            {"key": "assess", "status": "completed"},
        ],
    }

    rail = _build_macro_rail(state)

    assert rail is not None
    dumped = rail.model_dump(mode="json")
    assert dumped["currentId"] == "assess"
    by_id = {s["id"]: s["status"] for s in dumped["steps"]}
    assert by_id["prep"] == "done"
    assert by_id["table"] == "done"
    assert by_id["field"] == "done"
    assert by_id["assess"] == "running"


def test_zhgk_progress_rail_keeps_resurvey_app_wait_in_resurvey_phase():
    state = {
        "current_step": "wait_survey",
        "project": {
            "intent": "survey_work",
            "resurvey_decision": "resurvey",
            "resurvey_dispatch_decision": "dispatch",
        },
        "hitl": {"step": "wait_survey"},
        "steps": [
            {"key": "preflight", "status": "completed"},
            {"key": "intent_select", "status": "completed"},
            {"key": "determine_gen", "status": "completed"},
            {"key": "filter_build", "status": "completed"},
            {"key": "method_split", "status": "completed"},
            {"key": "data_append", "status": "completed"},
            {"key": "confirm_table", "status": "completed"},
            {"key": "task_dispatch", "status": "completed"},
            {"key": "wait_survey", "status": "hitl"},
            {"key": "assess", "status": "completed"},
            {"key": "issue_list", "status": "completed"},
            {"key": "resurvey_gate", "status": "completed"},
        ],
    }

    rail = _build_macro_rail(state)

    assert rail is not None
    dumped = rail.model_dump(mode="json")
    assert dumped["currentId"] == "resurvey"
    by_id = {s["id"]: s["status"] for s in dumped["steps"]}
    assert by_id["field"] == "done"
    assert by_id["resurvey"] == "running"


def test_zhgk_assessment_panel_uses_dedicated_clickable_node():
    state = {
        "steps": [
            {
                "key": "assess",
                "status": "completed",
                "metrics": {
                    "assess_total": 2,
                    "assess_满足": 1,
                    "assess_未勘测": 1,
                    "assess_detail_groups": {
                        "满足": [
                            {
                                "item": "冷通道封闭完整",
                                "result": "已封闭",
                                "source": "最新检查结果",
                                "risk": "",
                            }
                        ],
                        "未勘测": [
                            {
                                "item": "温湿度监控可用",
                                "result": "",
                                "source": "未填写",
                                "risk": "缺少采集数据",
                            }
                        ],
                    },
                },
            }
        ]
    }

    card = _build_assessment_panel(state)

    assert card is not None
    dumped = card.model_dump(mode="json")
    panel = dumped["children"][0]
    assert panel["type"] == "ZhgkAssessmentPanel"
    assert panel["total"] == 2
    assert panel["rateValue"] == 50
    categories = {item["label"]: item for item in panel["categories"]}
    assert categories["满足"]["details"][0]["item"] == "冷通道封闭完整"
    assert categories["未勘测"]["details"][0]["risk"] == "缺少采集数据"


def test_filter_preview_reads_survey_table_at_confirm_table_hitl(tmp_path):
    from openpyxl import Workbook

    from agent.skills.zhgk.sdui import _build_filter_preview, _build_summary

    out_dir = tmp_path / "ProjectData" / "Output"
    out_dir.mkdir(parents=True)
    table = out_dir / "ACT001_全量勘测结果表.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["序号", "细分场景", "勘测要素", "项目", "勘测方法", "检查内容"])
    ws.append([1, "硬装入场", "接地", "接地线", "现场勘测", "检查接地"])
    ws.append([2, "通液前", "管路", "排水管", "现场勘测", "检查排水"])
    wb.save(table)
    wb.close()

    state = {
        "work_root": str(tmp_path),
        "hitl": {"step": "confirm_table"},
        "logs": [
            "[data_append] ▶ 开始 勘测条目追加",
            "[confirm_table] ⏸ HITL · 等待确认 1 项",
        ],
    }

    card = _build_filter_preview(state)
    assert card is not None
    dumped = card.model_dump(mode="json")
    assert dumped["id"] == "filter-preview"
    assert dumped["children"][0]["rows"][0][0] == "1"
    assert dumped["children"][0]["rows"][0][1] == "硬装入场"
    assert _build_summary(state) is None


def test_scan_workspace_excludes_project_demo_report(tmp_path):
    from agent.skills.zhgk.demo_assets import MOCK_REPORT_FILENAME
    from agent.skills.zhgk.sdui import _scan_workspace_files

    input_dir = tmp_path / "ProjectData" / "Input"
    input_dir.mkdir(parents=True)
    (input_dir / MOCK_REPORT_FILENAME).write_bytes(b"%PDF")
    (input_dir / "BOQ.xlsx").write_bytes(b"xlsx")

    state = {
        "work_root": str(tmp_path),
        "project": {"intent": "survey_work"},
        "steps": [],
    }
    scan_in, scan_out = _scan_workspace_files(state)

    assert f"ProjectData/Input/{MOCK_REPORT_FILENAME}" not in scan_in
    assert "ProjectData/Input/BOQ.xlsx" in scan_in
    assert scan_out == []


def test_scan_workspace_hides_survey_table_before_field_survey(tmp_path):
    from agent.skills.zhgk.sdui import _scan_workspace_files

    output_dir = tmp_path / "ProjectData" / "Output"
    output_dir.mkdir(parents=True)
    table = output_dir / "ACT001_智算Q3_全量勘测结果表.xlsx"
    table.write_bytes(b"xlsx")

    base_state = {
        "work_root": str(tmp_path),
        "project": {"intent": "survey_work"},
        "steps": [{"key": "filter_build", "status": "completed"}],
    }

    _, scan_out = _scan_workspace_files(base_state)
    assert scan_out == []

    after_survey = {
        **base_state,
        "steps": [
            {"key": "filter_build", "status": "completed"},
            {"key": "wait_survey", "status": "completed"},
        ],
    }
    _, scan_out2 = _scan_workspace_files(after_survey)
    assert scan_out2 == ["ProjectData/Output/ACT001_智算Q3_全量勘测结果表.xlsx"]


def test_scan_workspace_shows_survey_table_for_report_gen_intent(tmp_path):
    from agent.skills.zhgk.sdui import _scan_workspace_files

    output_dir = tmp_path / "ProjectData" / "Output"
    output_dir.mkdir(parents=True)
    table = output_dir / "ACT001_全量勘测结果表.xlsx"
    table.write_bytes(b"xlsx")

    state = {
        "work_root": str(tmp_path),
        "project": {"intent": "report_gen"},
        "steps": [],
    }
    _, scan_out = _scan_workspace_files(state)
    assert scan_out == ["ProjectData/Output/ACT001_全量勘测结果表.xlsx"]
