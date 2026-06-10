'use client';

/* TopologyDiagram · G-18 · 组网图禁用前端生成
 *
 * 决策（5.27 会议）：
 * - 组网图必须来源于 SR（Solution Repository）方案库的标准物理拓扑图
 * - 前端不再「画」组网，避免 PD/TD 误以为是真实组网
 * - 改为：1）展示 SR 来源徽章 + 版本号 / 责任 SE
 *         2）提供「上传 SR 拓扑图」与「跳转 SR 中心」两个入口
 *         3）历史 SVG 渲染逻辑保留为可折叠的「占位预览」便于开发期 review
 */

const SR_META = {
  source: 'SR · Solution Repository',
  templateId: 'NW-AI-CLUSTER-TPL-2026-Q2',
  version: 'v3.2.1',
  owner: '王明 · SE',
  approvedBy: '何博 · TD',
  approvedAt: '2026-05-22 16:08',
  /* 演示阶段：占位静态图 URL（实际由 SR 中心下发） */
  imageUrl: '',
};

export default function TopologyDiagram() {
  return (
    <div className="topology-wrap">
      <div className="topology-head">
        <h3>样本面组网设计</h3>
        <span className="topology-sub">
          组网图来源 · <strong className="topology-sr-tag">{SR_META.source}</strong>
          <span className="topology-sr-meta">
            模板 {SR_META.templateId} · {SR_META.version} · {SR_META.owner}
          </span>
        </span>
      </div>

      <div className="topology-body">
        {/* G-18 · SR 来源说明（替代前端绘图） */}
        <div className="topology-sr-card">
          {SR_META.imageUrl ? (
            <img src={SR_META.imageUrl} alt="SR 标准组网图" className="topology-sr-img" />
          ) : (
            <div className="topology-sr-empty">
              <div className="topology-sr-empty-ic">SR</div>
              <div className="topology-sr-empty-title">尚未挂载 SR 标准组网图</div>
              <div className="topology-sr-empty-desc">
                组网图必须由 SE 在 SR · Solution Repository 中维护。请使用下方入口挂载或前往 SR 中心查阅。
              </div>
              <div className="topology-sr-actions">
                <button className="btn sm primary">↑ 挂载 SR 拓扑图（{SR_META.version}）</button>
                <button className="btn sm">↗ 打开 SR 中心</button>
              </div>
              <div className="topology-sr-approval">
                批准：{SR_META.approvedBy} · {SR_META.approvedAt}
              </div>
            </div>
          )}
        </div>

        {/* 右侧说明（保留容量与带宽指标，作为辅助说明） */}
        <div className="topology-side">
          <div className="topology-spec">
            <div className="topology-spec-head">样本面组网 · 关键指标（SR 模板默认）</div>
            <ul>
              <li>每台 AI 计算节点上行 <b>2×100GE</b> 至样本面网络</li>
              <li>存储聚合带宽考虑：断点续训读 CKPT 和 边训边读 两种</li>
              <li>断点续训聚合带宽 = <b>6.7 GB/s</b>（基于 bloom 176B · 每节点带宽 × 节点数 / DP 域大小 × 2）</li>
              <li>边训边读聚合带宽：LLM 约 <b>0.2 GB/s</b>，推荐 <b>72 GB/s</b>；多模态 Sora <b>1.05 GB/s</b>；自动驾驶 <b>2.7 GB/s</b></li>
              <li>存储容量主要考虑 ckpt 容量、训练数据集、性能调试、实验数据，<b>算存比 ≈ 100:1</b></li>
            </ul>
          </div>

          <div className="topology-note">
            前端不再生成组网图 · 唯一来源 = SR 模板（{SR_META.templateId}）
          </div>
        </div>
      </div>

    </div>
  );
}
