"""hotreload 守门：运行时热插拔 skill 的核心契约。

  · 重载已存在 skill → reloaded，仍在注册表
  · 非法名 / 不存在 → error
  · 投放最小合法 skill → added；语法错 → 事务化保留旧版；删目录 → removed

跑：agent/.venv/Scripts/python -m unittest agent.tests.test_hotreload -v
"""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

import agent.skills  # 触发 _register_all
from agent.skills import registry
from agent.skills.hotreload import reload_skill

SKILLS_DIR = Path(agent.skills.__file__).resolve().parent
TMP = "zzz_hotreload_tmp"


class TestHotReload(unittest.TestCase):
    def test_reload_existing(self):
        self.assertIn("zhgk", registry.names())
        r = reload_skill("zhgk")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["action"], "reloaded")
        self.assertIn("zhgk", registry.names())

    def test_nonexistent(self):
        r = reload_skill("definitely_not_a_skill")
        self.assertFalse(r["ok"])
        self.assertEqual(r["action"], "error")

    def test_illegal_names(self):
        for bad in ("../evil", "_template", "a.b", ""):
            self.assertFalse(reload_skill(bad)["ok"], bad)

    def test_add_transactional_remove(self):
        try:
            # ① 投放最小合法 skill → added
            d = SKILLS_DIR / TMP
            d.mkdir(parents=True, exist_ok=True)
            (d / "__init__.py").write_text("", encoding="utf-8")
            (d / "skill.py").write_text(f"def get_{TMP}_skill():\n    return None\n", encoding="utf-8")
            self.assertNotIn(TMP, registry.names())
            r = reload_skill(TMP)
            self.assertEqual(r.get("action"), "added", r)
            self.assertIn(TMP, registry.names())

            # ② 改成语法错 → 失败但保留旧版（事务化）
            (d / "skill.py").write_text("def broken(:\n", encoding="utf-8")
            r2 = reload_skill(TMP)
            self.assertFalse(r2["ok"])
            self.assertEqual(r2["action"], "error")
            self.assertIn(TMP, registry.names(), "坏编辑不应清掉旧版")

            # ③ 删目录 → removed
            shutil.rmtree(d)
            r3 = reload_skill(TMP)
            self.assertEqual(r3.get("action"), "removed", r3)
            self.assertNotIn(TMP, registry.names())
        finally:
            registry._builders.pop(TMP, None)
            registry._cache.pop(TMP, None)
            for k in [m for m in sys.modules if m == f"agent.skills.{TMP}" or m.startswith(f"agent.skills.{TMP}.")]:
                del sys.modules[k]
            shutil.rmtree(SKILLS_DIR / TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
