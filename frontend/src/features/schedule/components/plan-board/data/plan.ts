/* AIDA 排期 · 单一盘子数据源（站 / 货 / 人 / 批次 / 排期 共用）· 用户决策 2026-05-31
 * 6 机房 × 2 PoD = 12 PoD · 3 上线批 · 6 队伍。改盘子只改这里，各页派生一致。
 * 甘特时间线(GD_ACTS) 是排期"算出来的结果"(后端范畴)，仍在 planinit 内作 mock；
 * 其计数(机房/PoD/批) 从这里的 BATCH 派生对齐，不再硬编码。
 */

// ===== 类型 =====
// PoD：arrival 到货状态(arrived 已到货 / eta 在途有预计 / unknown 未明)；status 执行态(由时间轴指针定)
export type PodRow = { id: string; arrival: "arrived" | "eta" | "unknown"; etaLabel: string; etaDate?: string; status: "pending" | "in_progress" | "done"; goLiveBatch: string };
// 机房 3 段 ready 时间(可布线/可装设备/可通液)；可进场 = 任一段填了；site 字段保留兼容旧引用，显示用 deriveSite 派生
export type RoomRow = { code: string; proj: string; gx: number; gy: number; site: "ready" | "fitting" | "pending"; readyBatch: string; goLiveBatch: string; pods: PodRow[]; cableReadyAt?: string; equipReadyAt?: string; liquidReadyAt?: string; readyUnknown?: boolean };
// 批次(PoD 级，可编辑) = 一组 PoD(by id) + 上电 + 上线
export type BatchRow = { id: string; name: string; color: string; powerOnDate: string; goLiveDate: string; podIds: string[] };
// 队伍 = 全能施工单元；exp full 经验充分 / junior 待教，影响产能
export type TeamRow = { id: string; n: number; exp: "full" | "junior"; st: "on" | "wait" };

export const BATCH_COLORS = ["#3551D1", "#1B9D6B", "#BC7E14", "#7B61FF", "#0EA5A4", "#D9488B"];

// ===== 上线/上电批：核心主导维度（客户按批分阶段上线 PoD）=====
export const GO_LIVE_BATCHES = [
  { id: "B-go-A", label: "A", color: "#3551D1", rooms: ["M1", "M2"], goLiveDate: "2026-08-20" },
  { id: "B-go-B", label: "B", color: "#1B9D6B", rooms: ["M3", "M4"], goLiveDate: "2026-09-05" },
  { id: "B-go-C", label: "C", color: "#BC7E14", rooms: ["M5", "M6"], goLiveDate: "2026-09-20" },
];
// ===== 机房 ready 批：次要维度（与上线批独立）=====
export const READY_BATCHES = [
  { id: "B-ready-1", label: "批1", color: "#7B61FF", rooms: ["M1", "M2"], readyDate: "2026-07-05" },
  { id: "B-ready-2", label: "批2", color: "#0EA5A4", rooms: ["M3", "M4"], readyDate: "2026-07-20" },
  { id: "B-ready-3", label: "批3", color: "#F59E0B", rooms: ["M5", "M6"], readyDate: "2026-08-05" },
];

// ===== 机房 + PoD（站 / 货 盘子）=====
// adjust(信息全)直接用本数据；init(信息少)在 planinit 内派生 INITIAL_ROOMS_BARE（ready/到货置「待定」）
export const INITIAL_ROOMS: RoomRow[] = [
  // M1/M2 · 批 A · 3 段时间全填 → 可进场
  { code:"M1", proj:"智算一期", gx:0, gy:0, site:"ready",   readyBatch:"B-ready-1", goLiveBatch:"B-go-A",
    cableReadyAt:"2026-06-15", equipReadyAt:"2026-07-01", liquidReadyAt:"2026-07-10",
    pods:[
      { id:"P-01", arrival:"arrived", etaLabel:"可上架", status:"in_progress", goLiveBatch:"B-go-A" },
      { id:"P-02", arrival:"arrived", etaLabel:"可上架", status:"in_progress", goLiveBatch:"B-go-A" },
    ] },
  { code:"M2", proj:"智算一期", gx:0, gy:1, site:"ready",   readyBatch:"B-ready-1", goLiveBatch:"B-go-A",
    cableReadyAt:"2026-06-18", equipReadyAt:"2026-07-03", liquidReadyAt:"2026-07-12",
    pods:[
      { id:"P-03", arrival:"arrived", etaLabel:"可上架", status:"in_progress", goLiveBatch:"B-go-A" },
      { id:"P-04", arrival:"arrived", etaLabel:"可上架", status:"pending",     goLiveBatch:"B-go-A" },
    ] },
  // M3/M4 · 批 B · ready 3 段已明确 → 可进场
  { code:"M3", proj:"智算一期", gx:1, gy:0, site:"fitting", readyBatch:"B-ready-2", goLiveBatch:"B-go-B",
    cableReadyAt:"2026-07-05", equipReadyAt:"2026-07-18", liquidReadyAt:"2026-07-25",
    pods:[
      { id:"P-05", arrival:"arrived", etaLabel:"可上架",     status:"pending", goLiveBatch:"B-go-B" },
      { id:"P-06", arrival:"eta",     etaLabel:"在途 07-10", etaDate:"2026-07-10", status:"pending", goLiveBatch:"B-go-B" },
    ] },
  { code:"M4", proj:"智算一期", gx:1, gy:1, site:"fitting", readyBatch:"B-ready-2", goLiveBatch:"B-go-B",
    cableReadyAt:"2026-07-08", equipReadyAt:"2026-07-20", liquidReadyAt:"2026-07-28",
    pods:[
      { id:"P-07", arrival:"eta",     etaLabel:"在途 07-25", etaDate:"2026-07-25", status:"pending", goLiveBatch:"B-go-B" },
      { id:"P-08", arrival:"eta",     etaLabel:"在途 07-30", etaDate:"2026-07-30", status:"pending", goLiveBatch:"B-go-B" },
    ] },
  // M5/M6 · 批 C · ready 3 段已明确 + 到货已排期 → 可进场
  { code:"M5", proj:"智算一期", gx:2, gy:0, site:"ready", readyBatch:"B-ready-3", goLiveBatch:"B-go-C",
    cableReadyAt:"2026-08-02", equipReadyAt:"2026-08-09", liquidReadyAt:"2026-08-15",
    pods:[
      { id:"P-09", arrival:"eta", etaLabel:"在途 08-15", etaDate:"2026-08-15", status:"pending", goLiveBatch:"B-go-C" },
      { id:"P-10", arrival:"eta", etaLabel:"在途 08-18", etaDate:"2026-08-18", status:"pending", goLiveBatch:"B-go-C" },
    ] },
  { code:"M6", proj:"智算一期", gx:2, gy:1, site:"ready", readyBatch:"B-ready-3", goLiveBatch:"B-go-C",
    cableReadyAt:"2026-08-05", equipReadyAt:"2026-08-11", liquidReadyAt:"2026-08-17",
    pods:[
      { id:"P-11", arrival:"eta", etaLabel:"在途 08-20", etaDate:"2026-08-20", status:"pending", goLiveBatch:"B-go-C" },
      { id:"P-12", arrival:"eta", etaLabel:"在途 08-22", etaDate:"2026-08-22", status:"pending", goLiveBatch:"B-go-C" },
    ] },
];

// ===== 批次（PoD 级，可编辑；BatchManager / 倒排图 / 排期共用）=====
export const INITIAL_BATCHES: BatchRow[] = [
  { id:"bt-1", name:"批次1", color:BATCH_COLORS[0]!, powerOnDate:"2026-08-15", goLiveDate:"2026-08-20", podIds:["P-01","P-02","P-03","P-04"] },
  { id:"bt-2", name:"批次2", color:BATCH_COLORS[1]!, powerOnDate:"2026-08-31", goLiveDate:"2026-09-05", podIds:["P-05","P-06","P-07","P-08"] },
  { id:"bt-3", name:"批次3", color:BATCH_COLORS[2]!, powerOnDate:"2026-09-15", goLiveDate:"2026-09-20", podIds:["P-09","P-10","P-11","P-12"] },
];

// ===== 队伍（人 盘子）· 6 机房 → 6 队，人数 10~12 =====
export const INITIAL_TEAMS: TeamRow[] = [
  {id:"01",n:12,exp:"full",  st:"on"},   {id:"02",n:10,exp:"full",  st:"wait"},
  {id:"03",n:11,exp:"full",  st:"on"},   {id:"04",n:12,exp:"junior",st:"wait"},
  {id:"05",n:10,exp:"full",  st:"wait"}, {id:"06",n:11,exp:"junior",st:"wait"},
];

// ===== 盘子元信息（全部从上面派生，杜绝硬编码漂移）=====
export const BATCH = {
  group: "智算一期 2026 Q2",
  rooms: INITIAL_ROOMS.length,
  pods: INITIAL_ROOMS.reduce((s, r) => s + r.pods.length, 0),
  teams: INITIAL_TEAMS.length,
  headcount: INITIAL_TEAMS.reduce((s, t) => s + t.n, 0),
  deadline: INITIAL_BATCHES.reduce((m, b) => (b.goLiveDate > m ? b.goLiveDate : m), INITIAL_BATCHES[0]!.goLiveDate),
};
