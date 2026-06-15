# 合并 SOP（通俗版，可打印贴墙）

> **一句话总纲**：`feature_new` 是大家的集成圣地，只能通过个人分支 + PR 审核合入；你只在自己的 `feat/xxx` 分支干活；**「验证通过」= 守门全绿 + 前端 build 过，且由审核人复核**——不是「我本地点了没事」。

---

## 🔧 第一次先做「一次性设置」（每台机器做一次，否则连不上 gitea）

```bash
# 1. 加内网 gitea 远端
git remote add gitea http://10.143.2.109:3010/jintao/aida.git
# 2. 只对 gitea 这个地址永久关闭公司代理（不影响其它地址走代理，避免 504）
git config --global http.http://10.143.2.109:3010/.proxy ""
# 3. （可选）记住 gitea 登录，免反复输令牌
git config --global credential.helper store
# 验证：不报错、不卡代理即成功
git ls-remote gitea HEAD
```

做完这三步后，后面所有 gitea 命令都不用再加 `-c http.proxy=` / 改环境变量。

---

## 🟢 平时合并 · 7 步

```
① 永远开自己的分支干活，别在 feature_new 上写
   git switch feature_new
   git fetch gitea feature_new          # 只更新本地指针，不在这分支上开发
   git switch -c feat/我的模块-简述

② 干完一个能验证的小闭环就准备合（分支别养超过 2 天）

③ 合之前，先把个人分支追到最新 feature_new（在自己这边解冲突）
   git fetch gitea feature_new
   git rebase gitea/feature_new

④ 有冲突？ → 把【合并前Agent提示词】丢给 Cursor，让它逐处解、两边都保留
   ⚠️ 解冲突最忌「整块选一边」——会把同事的代码删掉，和强推一样毁数据

⑤ 本地跑一遍守门（Cursor 会帮你跑），全绿再继续

⑥ 推自己的分支（注意是 --force-with-lease，不是 --force）：
   git push --force-with-lease gitea feat/我的模块-简述

⑦ 在 Gitea 发 PR（base = feature_new）→ 审核人复核 + 重跑守门全绿
   → 用 Squash 方式合入 → 删个人分支
```

---

## 🚦 三条铁律（记不住别的，记这三条）

| # | 铁律 | 为什么 |
|---|---|---|
| 1 | **push 被拒 → `git fetch && git rebase`，绝不 `--force`** | `--force` 推 feature_new = 抹掉别人提交，就是上次的事故 |
| 2 | **只动自己 `agent/skills/<我的模块>/` 的文件** | 碰框架共享文件 = 必和别人撞，且最难解 |
| 3 | **「完成」= 守门全绿 + build 过 + 审核人复核** | 本地环境会骗你（参考端口连错后端那次），光自己本地绿不算数 |

---

## 🆘 出事了怎么办（贴在最显眼处）

```
情况 A：git push 被拒（"non-fast-forward"）
  → 别慌，别 force。执行：
     git fetch gitea feature_new
     git rebase gitea/feature_new
     （有冲突就让 Cursor 按提示词解）
     git push --force-with-lease gitea <我的分支>

情况 B：发现 feature_new 被误强推，提交不见了
  → 立刻在群里喊停，别再推。按顺序找回（24 小时内基本都能救）：
     · 任何 fetch 过的人本地：  git reflog  /  git reflog gitea/feature_new
     · 强推者本人本地：         git reflog                ← 他机器上一定有
     · Gitea 活动页查 push 记录里的旧 SHA
     · 都查不到 → 找 Gitea 管理员，在服务器裸库上跑：
              git reflog   或   git fsck --lost-found    ← 捞悬空 commit
     · 拿到旧 SHA → git branch rescue/<日期> <SHA> → 走正常 PR 合回 feature_new
  → 找回后交给负责人统一合，别自己硬推
```

---

## ✋ 永远不要做

- ❌ `git push --force`（任何时候）
- ❌ 直接推 feature_new / 在 feature_new 上开发
- ❌ 解冲突时整块采用一边、删掉另一边的改动
- ❌ 让 AI「顺手」重格式化无关文件 / 改框架共享文件
- ❌ 手改 `docs/site/*.html` 这类生成产物（要用 `gen_*.py` 重新生成）
- ❌ 跳过「一次性设置」直接连 gitea（会 504 / fetch 失败）
- ❌ 把「我本地能跑」当成验证通过
