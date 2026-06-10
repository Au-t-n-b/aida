/**
 * /sdui-preview — SDUI 组件预览页（dev 工具）
 *
 * 用 mock SduiDocument 渲染各节点，供视觉验证，**不依赖后端 / SSE**
 * （SduiNodeView 走 SduiContext 默认 no-op runtime，交互节点回调为空但视觉完整）。
 * 新增 / 优化 SDUI 组件后，在此页核对渲染效果再提交。
 */
import type { SduiNode } from '@/lib/sdui';
import { SduiNodeView } from '@/components/sdui/SduiNodeView';

const SAMPLES: { title: string; node: SduiNode }[] = [
  {
    title: 'Tier D · MacroStepRail / TaskTimelineStrip / InputSlotList / TabGroup（新增 · v5 交付台）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        {
          type: 'MacroStepRail',
          currentId: 's3',
          steps: [
            { id: 's1', title: '输入件准备', status: 'done' },
            { id: 's2', title: '地址规划', status: 'done' },
            { id: 's3', title: '互联规划', hint: 'L2/L3 互联', status: 'running' },
            { id: 's4', title: 'LLD 生成', status: 'pending' },
            { id: 's5', title: 'ZTP 配置', hint: '可跳过', optional: true, status: 'pending' },
            { id: 's6', title: '发布完成', status: 'pending' },
          ],
        },
        {
          type: 'TaskTimelineStrip',
          plannedStart: '2026-06-01', plannedEnd: '2026-06-30',
          actualStart: '2026-06-03', remainingDays: -2, progressPct: 80,
        },
        {
          type: 'InputSlotList',
          title: '输入件清单（4 项）',
          slots: [
            { label: 'BOQ 设备清单', source: 'manual', required: true, ready: true, fileName: 'BOQ.xlsx', previewPath: 'Input/BOQ.xlsx' },
            { label: '仿真拓扑产物', source: 'auto', required: true, ready: false },
            { label: '地址规划表', source: 'manual', required: true, ready: false },
            { label: '现场照片', source: 'manual', required: false, ready: true, fileName: 'site.zip' },
          ],
        },
        {
          type: 'TabGroup',
          activeTab: 'prog',
          tabs: [
            { id: 'prog', label: '进度', children: [
              { type: 'VerticalStepper', items: [{ label: '输入件准备', status: 'done' }, { label: '互联规划', status: 'running' }, { label: 'LLD 生成', status: 'pending' }] },
            ] },
            { id: 'inputs', label: '输入件', badge: 2, children: [
              { type: 'Alert', tone: 'warning', message: '2 项必需输入件缺失，请上传或等待仿真产出。' },
            ] },
            { id: 'outputs', label: '输出件', badge: 5, children: [
              { type: 'ArtifactGrid', mode: 'output', artifacts: [{ label: 'LLD.docx', path: 'Output/LLD.docx', kind: 'docx' }, { label: '地址规划.xlsx', path: 'Output/addr.xlsx', kind: 'xlsx' }] },
            ] },
          ],
        },
      ],
    },
  },
  {
    title: 'Tier C · StatusBanner / SegmentedControl / VerticalStepper / AssessmentBar / RecipientList / DiffView / ImageGrid / InlinePreview / Sparkline（新增）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'StatusBanner', items: [{ status: 'run', text: '执行中 · determine_gen · 26%' }, { status: 'pause', text: '待补充 · HITL 已路由至会话' }, { status: 'fail', text: '失败 · 缺 generation_cooling' }] },
        { type: 'SegmentedControl', segments: ['概览', '条目', '风险'], caption: '代际 A3 · 液冷 · 全流程工勘' },
        { type: 'VerticalStepper', items: [{ label: 'preflight', status: 'done' }, { label: 'determine_gen', status: 'running' }, { label: 'filter_build', status: 'pending' }] },
        { type: 'AssessmentBar', title: 'AI 五值评估（共 128 项）', segments: [{ label: '满足', value: 62, color: '#0f9d58' }, { label: '不满足', value: 18, color: '#dc2626' }, { label: '不涉及', value: 12, color: '#94a3b8' }, { label: '无法识别', value: 8, color: '#d97706' }] },
        { type: 'RecipientList', items: [{ name: '张工', role: '项目经理 · 已发送', status: '已读' }, { name: '李工', role: '配电负责人 · 待确认', status: '待确认' }] },
        { type: 'DiffView', leftTitle: 'BOQ 条目', rightTitle: 'HLD 规划', rows: [{ left: 'Atlas 800 × 32', right: 'Atlas 800 × 32' }, { left: '液冷 CDU × 4', right: '液冷 CDU × 6', change: 'chg' }, { left: '风冷机柜 × 8', right: '—', change: 'del' }] },
        { type: 'ImageGrid', images: [{ label: '配电', caption: 'PDU-01.jpg' }, { label: '机房', caption: 'room-a.jpg' }, { label: '走线', caption: 'cable-tray.jpg' }] },
        { type: 'InlinePreview', filename: '工勘报告.docx', placeholder: '预览区 · 对接 ArtifactGrid open_preview' },
        { type: 'Sparkline', label: '满足度', value: '78%', delta: '▲ 6%', points: [28, 24, 26, 18, 20, 12, 14, 8, 6] },
      ],
    },
  },
  {
    title: 'Tier C · DashboardLayout / Drawer（递归容器）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'DashboardLayout', main: [{ type: 'Alert', tone: 'info', title: '主区', message: '黄金指标 + 评估面板 + 风险 + 产物' }], side: [{ type: 'ProgressBar', label: '执行进度', value: 26, tone: 'warning' }] },
        { type: 'Drawer', title: 'PDU 容量不足', children: [{ type: 'Alert', tone: 'error', title: '高风险', message: '建议扩容至 2×160A' }, { type: 'KeyValueList', items: [{ key: '场景', value: '配电' }, { key: '条目', value: 'SS-BP-E-003' }] }] },
      ],
    },
  },
  {
    title: 'Tier B 批1 · Banner / ProgressBar / Spinner / EmptyState（新增）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'Banner', tone: 'brand', title: '提示', message: '当前 skill 支持 4 种工作流，启动后选择意图。' },
        { type: 'ProgressBar', label: '建表进度', value: 62, tone: 'success' },
        { type: 'Spinner', tone: 'brand', label: '加载数据…' },
        { type: 'EmptyState', icon: '○', title: '暂无勘测数据', subtitle: '上传 BOQ 后自动生成勘测表' },
      ],
    },
  },
  {
    title: 'Tier B 批2 · CodeBlock / LogStream / Checklist / FileTree（新增）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'CodeBlock', filename: 'survey.sh', code: '# 启动全量工勘\naida survey run \\\n  --boq Input/BOQ.xlsx \\\n  --gen A3-liquid' },
        {
          type: 'LogStream',
          lines: [
            { time: '10:02:14', text: '✓ preflight 文件齐备', level: 'ok' },
            { time: '10:02:51', text: '→ 识别代际 A3 · 液冷', level: 'info' },
            { time: '10:03:09', text: '! PDU 容量待复核', level: 'warn' },
          ],
        },
        {
          type: 'Checklist',
          items: [
            { label: '建立全量勘测表', done: true },
            { label: '现场数据回填', done: false },
            { label: 'AI 五值评估', done: false },
          ],
        },
        {
          type: 'FileTree',
          items: [
            { name: 'ProjectData', type: 'dir', depth: 0 },
            { name: 'Input', type: 'dir', depth: 1 },
            { name: 'BOQ.xlsx', type: 'file', depth: 2, tag: '已上传' },
            { name: 'Output', type: 'dir', depth: 1 },
            { name: '工勘报告.docx', type: 'file', depth: 2, tag: '待生成' },
          ],
        },
      ],
    },
  },
  {
    title: 'Tier B 批3 · Tabs / Accordion（新增 · 有状态）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        {
          type: 'Tabs',
          tabs: [
            { label: '概览', content: '代际 A3 · 液冷 · 全流程工勘，共 128 项勘测条目。' },
            { label: '条目', content: '现场类 86 项 · 数据类 42 项。' },
            { label: '风险', content: '高 1 · 中 1 · 低 1。' },
          ],
        },
        {
          type: 'Accordion',
          items: [
            { title: '配电场景', body: 'PDU 容量、配电负载率、UPS 冗余等 32 项。' },
            { title: '土建场景', body: '机房净高、承重、防水等 28 项。' },
          ],
        },
      ],
    },
  },
  {
    title: 'Tier B 批4 · DataTable / TabbedTable（新增）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        {
          type: 'DataTable',
          title: '设备清单',
          columns: ['名称', '型号', '数量'],
          rows: [
            ['训练服务器', 'Atlas 800', 32],
            ['液冷 CDU', 'CDU-160', 6],
            ['网络交换机', 'CE8850', 12],
          ],
        },
        {
          type: 'TabbedTable',
          tabs: [
            { label: 'A 机房', headers: ['SN', '位置', '状态'], rows: [['SN-001', 'R01-U10', '已扫'], ['SN-002', 'R01-U12', '待扫']] },
            { label: 'B 机房', headers: ['SN', '位置', '状态'], rows: [['SN-101', 'R05-U03', '已扫']] },
          ],
        },
      ],
    },
  },
  {
    title: 'Tier B 批5 · MultiSelect / Slider / ConfirmDialog / FormGroup（新增）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'MultiSelect', title: '选择勘测场景', options: [{ label: '配电' }, { label: '土建' }, { label: '网络' }, { label: '暖通' }] },
        { type: 'Slider', label: '配电负载率阈值', value: 80, min: 0, max: 100, unit: '%' },
        { type: 'FormGroup', fields: [{ label: '项目编号', value: 'K1903' }, { label: '机房名称', placeholder: '如 A 机房' }] },
        { type: 'ConfirmDialog', title: '确认分发工勘报告？', message: '将发送给张工、李工、王工共 3 位干系人。', confirmLabel: '确认分发', cancelLabel: '再看看' },
      ],
    },
  },
  {
    title: 'RiskList · 风险清单（新增 · 等级色带）',
    node: {
      type: 'RiskList',
      title: 'AI 风险识别（共 3 项）',
      items: [
        { title: 'PDU 容量不足', level: 'high', detail: '配电场景 · 建议扩容至 2×160A · SS-BP-E-003' },
        { title: '机房净高临界', level: 'mid', detail: '土建场景 · 净高 2.8m，建议复核机柜高度' },
        { title: '走线距离偏长', level: 'low', detail: '网络场景 · 可接受，记录备案' },
      ],
    },
  },
  {
    title: 'Stepper · 横向',
    node: {
      type: 'Stepper',
      orientation: 'horizontal',
      steps: [
        { id: 's1', title: '预检', status: 'done' },
        { id: 's2', title: '意图', status: 'done' },
        { id: 's3', title: '代际制冷', status: 'running' },
        { id: 's4', title: '建表', status: 'waiting' },
        { id: 's5', title: '验收', status: 'waiting' },
      ],
    },
  },
  {
    title: 'Stepper · 竖向（zhgk 主用 · 含日志 detail）',
    node: {
      type: 'Stepper',
      orientation: 'vertical',
      steps: [
        { id: 'v1', title: '环境预检', status: 'done', detail: ['✓ 文件齐备'] },
        { id: 'v2', title: '场景建议生成', status: 'running', detail: ['→ 识别代际 A3 · 液冷', '建表中 80 / 128', '! PDU 容量待复核'] },
        { id: 'v3', title: 'AI 五值评估', status: 'waiting' },
      ],
    },
  },
  {
    title: '现有组件回归（Alert / StatisticRow / Table）',
    node: {
      type: 'Stack',
      gap: 'md',
      children: [
        { type: 'Alert', tone: 'warning', title: '待确认', message: 'BOQ 解析完成，识别代际 A3，等待确认制冷方式。' },
        {
          type: 'StatisticRow',
          items: [
            { title: '满足度', value: '78%', color: 'success' },
            { title: '风险项', value: 3, color: 'warning' },
            { title: '待补充', value: 1, color: 'error' },
          ],
        },
        {
          type: 'Table',
          headers: ['场景', '条目', '等级'],
          rows: [
            ['配电', 'PDU 容量', '高'],
            ['土建', '机房净高', '中'],
            ['网络', '走线距离', '低'],
          ],
        },
      ],
    },
  },
];

export default function SduiPreviewPage() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--c-bg, #f6f8fb)' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>SDUI 组件预览</h1>
        {SAMPLES.map((s, i) => (
          <section key={i} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
              {s.title}
            </div>
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <SduiNodeView node={s.node} />
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
