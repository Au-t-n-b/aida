# 通用 Agent 提示词（合并前丢给 Cursor 执行）

> **用法**：在 Cursor 开一个新的 Agent 会话，第一句粘贴下面整段，然后说「开始」。它会带你安全地把个人分支同步到最新 `feature_new` 并完成本地验证，**到推送前会停下等你确认**。
>
> 门户里「🔀 我要合并代码 · ③ 解冲突」那一步内嵌了同一份提示词，可一键复制。

---

## 〇、一次性设置（每台机器 / 每个新 clone 做一次）

> 做完这三步，后面所有对 gitea 的 git 命令都**不用再加 `-c http.proxy=`、也不用改环境变量**。

```bash
# 1. 加内网 gitea 远端（origin 保留为 GitHub 只读对照）
git remote add gitea http://10.143.2.109:3010/jintao/aida.git

# 2. 只对 gitea 这个地址永久关闭公司代理（不影响你访问其它需走代理的网址，避免 504）
git config --global http.http://10.143.2.109:3010/.proxy ""

# 3. （可选）记住 gitea 登录，免每次 push 反复输账号/令牌
git config --global credential.helper store

# 验证：下面这条不报错、不卡代理，即设置成功
git ls-remote gitea -h
```

---

## 提示词正文（复制以下整段粘贴给 Cursor）

```text
你现在的唯一任务是：把我当前的个人 feature 分支，安全地同步到最新 gitea/feature_new
并完成本地验证，为合入主仓做准备。这是一个多人 vibecoding 协作仓（主集成分支 feature_new），
代码托管在内网 Gitea，历史上发生过强推导致他人提交丢失的事故。你必须把
「不破坏任何人的工作」放在最高优先级，严格按下面的流程和红线执行。

【环境事实】
- 仓库根：本项目根目录
- 集成主分支：feature_new（大家的合入目标，不是 master）
- 协作远端：gitea → http://10.143.2.109:3010/jintao/aida.git
- 参考远端：origin → https://github.com/Au-t-n-b/aida.git（只读对照，默认不向它推送）
- 个人分支命名：feat/<模块>-<简述>（例：feat/zhgk-sdui-3d）
- 代理：gitea 的免代理已在「一次性设置」里通过 git 配置永久关闭，
  所以本会话所有 git 命令直接写即可，不需要加 -c http.proxy= 或改环境变量。
  （若 git ls-remote gitea -h 卡住或 504，说明没做一次性设置 → 停下提醒我先做。）
- 守门/评测命令见 AGENTS.md §6
- Python 虚拟环境：agent/.venv
  Windows: agent/.venv/Scripts/python.exe；其它系统：agent/.venv/bin/python
- 端口：以 frontend/.env.local 为准——VITE_AGENT_BASE（后端，常见 7401）、
  VITE_CLAWMANAGER_BASE（Manager，常见 8000）；不要硬编码端口。

【红线 · 违反即停】
1. 绝不在 feature_new 上直接做功能开发或提交；绝不对 feature_new 执行
   git push --force / --force-with-lease。
2. 绝不使用 git push --force。个人分支需要更新远端时，只能用
   git push --force-with-lease gitea <我的分支>。
3. 解冲突时绝不整块采用一边而丢弃另一边。每个冲突都要先读懂双方各自想做什么，
   合并双方意图；只要无法确定某段是否该保留，立刻停下问我，绝不替我猜。
4. 不碰与本任务无关的文件；尤其不准动框架/共享文件
   （agent/main.py, agent/graph.py, agent/sdui/builder.py,
    frontend 的 SduiNodeView.tsx / claw-seeds.ts / module.tsx 等），
   也不准对无关代码做「顺手」的重格式化。如果本任务确实必须改这些，先停下告诉我。
5. 不手改任何衍生制品（docs/site/*.html 等）；它们由 agent/scripts/gen_*.py 生成。
6. 到「推送」这一步必须停下，把验证证据给我看，等我明确说「推」再推。
7. 不擅自 git commit；若我未要求提交，验证通过后只汇报，等我确认再提交/推送。

【执行步骤】
第0步 体检
  - 确认 gitea 远端存在：git remote -v | findstr gitea（或 grep gitea）。
    没有就停下提醒我做「一次性设置」，不要自己乱加。
  - 运行：git status 和 git branch --show-current
  - 若当前在 feature_new：停下告诉我「你在集成主分支上」，等我切到个人分支再继续。
  - 若有未提交改动：停下告诉我，等我处理干净（stash / commit）再继续。
  - 确认当前分支名（后面只对这个个人分支操作）。

第1步 同步到最新 feature_new（用 rebase，不要用 pull，避免多余 merge commit）
    git fetch gitea feature_new
    git rebase gitea/feature_new
  - 若提示冲突，进入第2步；无冲突直接到第3步。
  - 任何时候都不要用 git push --force 去「绕过」被拒。

第2步 解冲突（最关键）
  - 逐个文件打开冲突，对每一处：说明 <<<我方 与 >>>对方 各自改了什么、意图是什么，
    然后给出「两边意图都保留」的合并方案。
  - 不确定就停下问我。解完 git add <file>，git rebase --continue。
  - 解完后简述：这次 rebase 一共动了哪些文件、有没有可能影响别人的模块。

第3步 衍生制品（仅当我明确要求提交时才执行提交）
  - 若改动碰了 SDUI builder → python agent/scripts/gen_sdui_gallery.py
  - 若改动碰了 docs/*.md → python agent/scripts/gen_docs_site.py
  - 若改动碰了 portal.json → python agent/scripts/gen_team_portal.py
  - 重新生成的产物单独提交一个 commit：chore: regen derived

第4步 本地预检（全部要绿，贴出每条的输出做证据）
  - 后端守门（逐个跑，任一非零即停并报告）：
    lint_no_naked_llm / lint_no_naked_send / lint_skill_contract / lint_tools /
    lint_sdui_contract / lint_sdui_gallery / lint_docs_site / lint_team_portal /
    lint_runtime_contract / lint_module_boundaries
  - 评测回归：eval_zhgk.py --fixture
    （若改动涉及 tools 再跑 eval_tools.py --fixture；涉及其它模块跑对应 eval 若有）
  - 前端：cd frontend && npm run typecheck && npm run lint:no-ts-nocheck && npm run build
  - 任一红：先修，别推。修完重跑。

第5步 汇报并等待
  - 给我一张清单：
    · 个人分支相对 gitea/feature_new 领先几个 commit
    · 改了哪些文件（按模块归类）
    · 每条守门/评测/前端的结果（绿/红 + 关键输出）
    · rebase 是否动过别人模块 / 共享框架文件
  - 然后停下，问我：「是否推送 <分支名> 并发起合入 feature_new？」
  - 我说「推」后你才执行：
    git push --force-with-lease gitea <分支名>
  - 推完后提示我：
    · 在 Gitea 上对 feature_new 发 Pull Request（base=feature_new, head=<我的分支>）
    · 把 PR 链接交给审核人；审核人会重跑守门后再合入
    · 合入方式优先 Squash（保持 feature_new 历史整洁），合入后删个人分支

现在开始第0步。
```
