# P0 · Gitea 服务端强制层落地清单

> **归属**：`VIBECODING_HARNESS.md` §6 的 P0。**目标**：把守门从「本地自觉（可 `--no-verify` 绕、没装钩子就没有）」升级为「服务端强制（绕不过）」。
> **为什么这是当前最致命的洞**：现有 `ci.yml` 是 **GitHub Actions**，跑在 GitHub 镜像上；团队真正集成在**内网 Gitea，且 CI 没接** → 硬阻断运行在没人干活的地方，20 人真实汇合处零强制层（断层 B）。
> **放仓库根**：避开 `docs/site` 派生守门扫描（同 `VIBECODING_HARNESS.md`）。

---

## 1. 两条路线对比（pre-receive 钩子 vs Gitea Actions）

| 维度 | **Gitea pre-receive 钩子** | **Gitea Actions** |
|---|---|---|
| 强制力 | **最强**：push 被接收前拒绝，`--no-verify` 绕不过，force-push 也拦 | 强：配 branch protection 后「checks 不过不能合并」，但代码已 push 到分支 |
| 时机 | push 接收瞬间（最早） | push 后 / PR 时 |
| 复用现有 `ci.yml` | ❌ 要写 shell | ✅ GitHub Actions 兼容语法，`ci.yml` 基本可直接搬 |
| 服务器依赖 | Gitea 服务器要有 python+依赖（或钩子内 `docker run` 带依赖镜像） | 需 **act_runner**（单独进程/容器） |
| 开发者反馈 | push 时命令行直接报错 | Gitea Web UI 的 checks 面板 |
| 谁能配 | 仓库/实例管理员（**你自建仓 = 有权**） | 实例管理员开 Actions + 注册 runner |
| 绕过风险 | 极低 | 低（除非有人关 branch protection） |

## 2. 推荐：两者分工，不是二选一

- **Gitea Actions 跑全套** `preflight`（lint + eval + 前端 build）—— 复用 `ci.yml`，开发者在 PR 看 checks，体验好、改动最小。**先上这个。**
- **pre-receive 只跑「最快最硬的几条红线」**（秒级：禁裸 LLM / 禁裸外发 / 派生新鲜度）—— 防止有人绕过 Actions/branch protection 直接 push 坏东西进集成分支。**作为第二道双保险，可选。**

## 3. 前置（必做）：抽一个 `preflight` 单一入口

两条路线 + 本地 pre-push **都调它**，避免守门清单散落成第三份会漂移的真相（治理自治）。

`scripts/preflight.sh`：
```sh
#!/bin/sh
set -eu
PY="${AIDA_PYTHON:-python}"
export AIDA_GUARD_STRICT=1   # 强制层下：缺依赖=配置错=该红（见 §6 修 fail-open）
$PY agent/scripts/lint_no_naked_llm.py
$PY agent/scripts/lint_no_naked_send.py
$PY agent/scripts/lint_skill_contract.py
$PY agent/scripts/lint_tools.py
$PY agent/scripts/lint_sdui_contract.py
$PY agent/scripts/lint_sdui_gallery.py
$PY agent/scripts/lint_docs_site.py
$PY agent/scripts/lint_team_portal.py
$PY agent/scripts/lint_runtime_contract.py
$PY agent/scripts/lint_module_boundaries.py
$PY agent/evals/eval_zhgk.py --fixture
# 前端（可选放 Actions 的独立 job）：cd frontend && npm run build
```

## 4. 路线 A 落地：Gitea Actions（先做）

1. **实例启用 Actions**：`app.ini` 加 `[actions]\nENABLED = true`（Gitea 1.19+；较新版本默认开）。
2. **装并注册 act_runner**：用官方 `gitea/act_runner`（docker 或二进制），`act_runner register` 指向实例 URL + 注册 token（实例/仓库设置里取）。runner 镜像要能装 `agent/requirements.txt`（内网 pip 镜像）+ node（前端 build）。
3. **放 workflow**：仓库加 `.gitea/workflows/ci.yml`（Gitea 同时认 `.gitea/workflows/` 和 `.github/workflows/`）。可从现有 `.github/workflows/ci.yml` 改造：把 `runs-on: ubuntu-latest` 对齐你 runner 的 label，`on:` 改 `[push, pull_request]` 覆盖你的集成分支（不是 master）。**正文可直接调 `scripts/preflight.sh`** 以单一入口。
4. **开 branch protection**：仓库 Settings → Branches → 保护 `feature_new`/集成分支，勾「Require status checks to pass」选中该 workflow。→ checks 不过不能合并。

## 5. 路线 B 落地：pre-receive 钩子（强制·绕不过·第二道）

1. **允许自定义 git hooks**：确认 `app.ini` `[security] DISABLE_GIT_HOOKS = false`（**查你实例的实际值**，部分部署默认禁用），且 Gitea 进程用户有权。
2. **配钩子**：仓库 Settings → Git Hooks → `pre-receive` 贴脚本（需仓库 admin）。
3. **脚本骨架**（pre-receive 时工作树未更新，要把推上来的内容 checkout 到临时目录再跑）：
```sh
#!/bin/sh
set -eu
while read oldrev newrev refname; do
  # 只管集成分支
  case "$refname" in refs/heads/feature_new|refs/heads/master) ;; *) continue ;; esac
  tmp="$(mktemp -d)"
  git archive "$newrev" | tar -x -C "$tmp"   # 导出该 commit 内容
  # 在带依赖的环境/容器里跑红线（示例直接跑，要求服务器有 python+依赖）
  if ! ( cd "$tmp" && sh scripts/preflight_redlines.sh ); then
    echo "❌ 红线守门未过，拒绝本次 push（修复后重推）" >&2
    rm -rf "$tmp"; exit 1
  fi
  rm -rf "$tmp"
done
```
（`preflight_redlines.sh` = `preflight.sh` 的秒级子集：no-naked-llm / no-naked-send / 三个派生新鲜度。服务器无依赖时改成 `docker run --rm -v "$tmp":/w -w /w <带依赖镜像> sh scripts/preflight_redlines.sh`。）

## 6. 配套：修 fail-open（否则强制层也是假绿）

P0 不只是「搬位置」，还要堵 fail-open，否则服务端跑了也可能静默绿：
- **`lint_skill_contract`**：现状「缺 venv → exit 0 + warn」。强制层下缺依赖 = 配置错 = 该红。加 `AIDA_GUARD_STRICT=1` 环境变量：设了则缺依赖 `exit≠0`，本地不设保持宽容。`preflight.sh` 里已 export。
- **`lint_module_boundaries`**（本轮 P1a 已修）：旧版正则找 `register("字面量")` 但代码用变量 → 一直静默 SKIP（假绿）。重构为目录自动发现后已真正生效。
- 全量排查其余 lint 是否有同类「缺依赖/缺文件 → exit 0」分支，统一收口到 `AIDA_GUARD_STRICT`。

## 7. 验收

- 故意提交一个 `import openai`（裸 LLM）→ Gitea Actions check 变红 / pre-receive 拒绝 push，合并被拦。
- 本地 `sh scripts/preflight.sh` 与服务端跑出**同样结论**（单一入口，无第三份清单）。

## 8. 执行顺序（谁做）

| # | 动作 | 谁 | 状态 |
|---|---|---|---|
| 1 | 写 `scripts/preflight.sh`（单一入口）+ `preflight_redlines.sh` | 我（仓内） | ✅ 完成（preflight 全跑绿，含 eval） |
| 2 | 修 fail-open：`agent/scripts/_guard.py` + 4 个 lint（skill/runtime/sdui-contract/sdui-gallery）接入 `AIDA_GUARD_STRICT` | 我（仓内） | ✅ 完成（strict 单测：宽容=0/严格=1） |
| 3 | Gitea Actions：`.gitea/workflows/ci.yml`（调 `preflight.sh`）+ 装 act_runner + branch protection | **你（Gitea）** | ☐ |
| 4 | （可选）pre-receive 红线二道（调 `preflight_redlines.sh`） | **你（Gitea 服务器）** | ☐ |

> ✅ 1+2 已落地（纯仓内）；3+4 需你在 Gitea 操作，workflow/钩子骨架已在 §4/§5。
