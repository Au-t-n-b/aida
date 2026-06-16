# SOG 实景孪生资产目录

大文件 `scene.sog` 不入 git（见仓库根 `.gitignore`），目录骨架与追踪清单入库。

## 通道1 演示样例

| 项 | 路径 |
|----|------|
| 运行时 SOG | `channel1/scene.sog` |
| 元数据 | `channel1/meta.json` |
| 热点标注 | `channel1/hotspots.json` |
| **样例来源追踪** | `channel1/sample-source.manifest.json` |
| 场景注册表 | `../sog-scenes.json` |

本地首次部署或更新样例：

```powershell
powershell -ExecutionPolicy Bypass -File agent/scripts/init_sog_channel1.ps1 `
  -Source "D:\.cursor_workplace\aida\通道1.sog"
```

脚本将源文件复制为 `channel1/scene.sog` 并刷新 `meta.json` / `hotspots.json`。

前端入口：http://127.0.0.1:8080/twin/survey
