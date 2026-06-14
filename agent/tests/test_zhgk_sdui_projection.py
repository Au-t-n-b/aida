from agent.skills.zhgk.sdui import _build_metrics_card


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
