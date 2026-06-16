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
