import {
  ADJUST_PATH,
  API_PREFIX,
  COMMIT_PATH,
  EXPORT_PLAN_PATH,
  GENERATE_PATH,
  PARSE_CHANGES_PATH,
  PROJECT_DATA_PATH,
  REPORT_SUMMARY_PATH,
  type Activity as ScheduleActivity,
  type AdjustRequest,
  type AdjustResponse,
  type ArrivalItem,
  type Batch,
  type ChangeSet,
  type CommitRequest,
  type CommitResponse,
  type Dependency,
  type GenerateRequest,
  type GenerateResponse,
  type InputBundle,
  type ParseChangesResponse,
  type PlanResult,
  type Pod,
  type Project,
  type ReportSummaryRequest,
  type ReportSummaryResponse,
  type Room,
  type RuleConfig,
  type Team,
} from '@/features/schedule/contracts/schedule.gen';
import { BATCH_COLORS, type BatchRow, type RoomRow, type TeamRow } from '@/features/schedule/components/plan-board/data/plan';

const FORCE_MOCK_FLAG = '1';
const CHANGE_TEMPLATE_DOWNLOAD_PATH = `${API_PREFIX}/change-template`;
const CHANGE_TEMPLATE_FILENAME = '变更表模板.xlsx';
const DELIVERY_PLAN_FILENAME = '交付计划表.xlsx';
const REPORT_SNAPSHOT_STORAGE_KEY = 'aida:schedule-risk-report:last';

export type GenerateScheduleInput = {
  rooms: RoomRow[];
  batches: BatchRow[];
  teams: TeamRow[];
  signal?: AbortSignal;
};

export type ProjectScheduleData = {
  project: Project;
  rooms: RoomRow[];
  batches: BatchRow[];
  teams: TeamRow[];
};

export type ScheduleReportSnapshot = {
  source: 'api';
  project: Project;
  inputs: InputBundle;
  plan: PlanResult;
  plan_id: string;
  version: number;
  committed_at: string;
  report_summary?: ReportSummaryResponse | null;
};

export type LoadProjectDataInput = {
  signal?: AbortSignal;
  totalCardCount?: number;
};

export type LoadProjectDataResult =
  | { source: 'api'; response: InputBundle; data: ProjectScheduleData }
  | { source: 'mock'; reason: 'forced' | 'unavailable' | 'http_error'; error?: unknown };

export type GenerateScheduleResult =
  | { source: 'api'; request: GenerateRequest; response: GenerateResponse }
  | { source: 'mock'; request: GenerateRequest; reason: 'forced' | 'unavailable' | 'http_error'; error?: unknown };

export type ScheduleBaseline = {
  plan_id: string;
  version: number;
};

export type ScheduleIncidentInput = {
  id: string;
  kind: 'efficiency' | 'holiday';
  label: string;
  start: string;
  end: string;
  efficiency: number;
};

export type AdjustScheduleInput = GenerateScheduleInput & {
  changeKeys: string[];
  incidents?: ScheduleIncidentInput[];
};

export type AdjustScheduleResult =
  | { source: 'api'; request: AdjustRequest; response: AdjustResponse; baseline: ScheduleBaseline }
  | { source: 'mock'; request?: AdjustRequest; reason: 'forced' | 'unavailable' | 'http_error' | 'no_baseline'; error?: unknown };

export type CommitScheduleInput = GenerateScheduleInput & {
  optionId: string;
  durationOverrides?: Record<string, number>;
};

export type CommitScheduleResult =
  | { source: 'api'; request: CommitRequest; response: CommitResponse; baseline: ScheduleBaseline }
  | { source: 'mock'; request?: CommitRequest; reason: 'forced' | 'unavailable' | 'http_error' | 'no_adjustment'; error?: unknown };

export type ParseChangeTemplateInput = GenerateScheduleInput & {
  file: File;
};

export type ParseChangeTemplateResult =
  | { source: 'api'; response: ParseChangesResponse }
  | { source: 'error'; reason: 'unavailable' | 'http_error'; error?: unknown };

export type GenerateReportSummaryResult =
  | { source: 'api'; response: ReportSummaryResponse }
  | { source: 'error'; reason: 'forced' | 'unavailable' | 'http_error'; error?: unknown };

type BaselineSnapshot = {
  baseline: ScheduleBaseline;
  input: GenerateScheduleInput;
};

type LastAdjustment = {
  plan_id: string;
  base_version: number;
};

let currentBaseline: BaselineSnapshot | null = null;
let lastAdjustment: LastAdjustment | null = null;
let latestProjectBundle: InputBundle | null = null;
let latestReportSnapshot: ScheduleReportSnapshot | null = null;

export async function loadProjectData(input: LoadProjectDataInput = {}): Promise<LoadProjectDataResult> {
  if (shouldForceMock()) {
    latestProjectBundle = null;
    return { source: 'mock', reason: 'forced' };
  }

  try {
    const response = await fetch(projectDataPath(input.totalCardCount), {
      method: 'GET',
      signal: input.signal,
    });

    if (!response.ok) {
      latestProjectBundle = null;
      return { source: 'mock', reason: 'http_error', error: await readError(response) };
    }

    const payload = (await response.json()) as InputBundle;
    latestProjectBundle = payload;
    return { source: 'api', response: payload, data: mapProjectDataToRows(payload) };
  } catch (error) {
    latestProjectBundle = null;
    return { source: 'mock', reason: 'unavailable', error };
  }
}

export async function generateInitialSchedule(input: GenerateScheduleInput): Promise<GenerateScheduleResult> {
  const request = buildGenerateRequest(input);

  if (shouldForceMock()) {
    return { source: 'mock', request, reason: 'forced' };
  }

  try {
    const response = await fetch(GENERATE_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: input.signal,
    });

    if (!response.ok) {
      return { source: 'mock', request, reason: 'http_error', error: await readError(response) };
    }

    const payload = (await response.json()) as GenerateResponse;
    currentBaseline = {
      baseline: { plan_id: payload.plan.plan_id, version: payload.plan.version },
      input: cloneScheduleInput(input),
    };
    lastAdjustment = null;
    return { source: 'api', request, response: payload };
  } catch (error) {
    return { source: 'mock', request, reason: 'unavailable', error };
  }
}

export async function ensureScheduleBaseline(input: GenerateScheduleInput): Promise<GenerateScheduleResult> {
  if (currentBaseline) {
    return { source: 'api', request: buildGenerateRequest(currentBaseline.input), response: baselineToGenerateResponse(currentBaseline) };
  }
  return generateInitialSchedule(input);
}

export async function adjustSchedule(input: AdjustScheduleInput): Promise<AdjustScheduleResult> {
  if (shouldForceMock()) {
    return { source: 'mock', reason: 'forced' };
  }

  const baselineResult = await ensureScheduleBaseline(input);
  if (baselineResult.source !== 'api' || !currentBaseline) {
    return { source: 'mock', reason: baselineResult.source === 'mock' ? baselineResult.reason : 'no_baseline', error: baselineResult.source === 'mock' ? baselineResult.error : undefined };
  }

  const baseline = currentBaseline.baseline;
  const request: AdjustRequest = {
    plan_id: baseline.plan_id,
    base_version: baseline.version,
    changes: buildChangeSet(input, currentBaseline.input),
  };

  try {
    const response = await fetch(ADJUST_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: input.signal,
    });

    if (!response.ok) {
      return { source: 'mock', request, reason: 'http_error', error: await readError(response) };
    }

    const payload = (await response.json()) as AdjustResponse;
    lastAdjustment = { plan_id: baseline.plan_id, base_version: baseline.version };
    return { source: 'api', request, response: payload, baseline };
  } catch (error) {
    return { source: 'mock', request, reason: 'unavailable', error };
  }
}

export async function commitSchedule(input: CommitScheduleInput): Promise<CommitScheduleResult> {
  if (shouldForceMock()) {
    return { source: 'mock', reason: 'forced' };
  }
  if (!lastAdjustment) {
    return { source: 'mock', reason: 'no_adjustment' };
  }

  const request: CommitRequest = {
    plan_id: lastAdjustment.plan_id,
    base_version: lastAdjustment.base_version,
    option_id: input.optionId,
  };
  const durationOverrides = normalizedDurationOverrides(input.durationOverrides);
  if (durationOverrides) {
    request.duration_overrides = durationOverrides;
  }

  try {
    const response = await fetch(COMMIT_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: input.signal,
    });

    if (!response.ok) {
      return { source: 'mock', request, reason: 'http_error', error: await readError(response) };
    }

    const payload = (await response.json()) as CommitResponse;
    const reportInputs = latestProjectBundle ?? buildGenerateRequest(input).inputs;
    currentBaseline = {
      baseline: { plan_id: payload.plan_id, version: payload.new_version },
      input: cloneScheduleInput(input),
    };
    lastAdjustment = null;
    writeLatestScheduleReportSnapshot({
      source: 'api',
      project: reportInputs.project,
      inputs: reportInputs,
      plan: payload.plan,
      plan_id: payload.plan_id,
      version: payload.new_version,
      committed_at: new Date().toISOString(),
    });
    return { source: 'api', request, response: payload, baseline: currentBaseline.baseline };
  } catch (error) {
    return { source: 'mock', request, reason: 'unavailable', error };
  }
}

export async function parseChangeTemplate(input: ParseChangeTemplateInput): Promise<ParseChangeTemplateResult> {
  const form = new FormData();
  form.append('file', input.file);
  form.append('known_room_ids', JSON.stringify(input.rooms.map((room) => room.code)));
  form.append('known_pod_ids', JSON.stringify(input.rooms.flatMap((room) => room.pods.map((pod) => pod.id))));
  form.append(
    'known_batches',
    JSON.stringify(input.batches.map((batch) => ({
      batch_id: batch.id,
      batch_name: batch.name,
      pod_ids: batch.podIds,
    }))),
  );

  try {
    const response = await fetch(PARSE_CHANGES_PATH, {
      method: 'POST',
      body: form,
      signal: input.signal,
    });
    if (!response.ok) {
      return { source: 'error', reason: 'http_error', error: await readError(response) };
    }
    return { source: 'api', response: (await response.json()) as ParseChangesResponse };
  } catch (error) {
    return { source: 'error', reason: 'unavailable', error };
  }
}

export async function downloadChangeTemplate(): Promise<void> {
  const response = await fetch(CHANGE_TEMPLATE_DOWNLOAD_PATH);
  if (!response.ok) {
    throw await readError(response);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = CHANGE_TEMPLATE_FILENAME;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function downloadDeliveryPlan(input: { planId?: string; version?: number } = {}): Promise<void> {
  const params = new URLSearchParams();
  if (input.planId) {
    params.set('plan_id', input.planId);
  }
  if (input.version != null) {
    params.set('version', String(input.version));
  }
  const query = params.toString();
  const response = await fetch(query ? `${EXPORT_PLAN_PATH}?${query}` : EXPORT_PLAN_PATH);
  if (!response.ok) {
    throw await readError(response);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = DELIVERY_PLAN_FILENAME;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function generateReportSummary(
  request: ReportSummaryRequest,
  signal?: AbortSignal,
): Promise<GenerateReportSummaryResult> {
  if (shouldForceMock()) {
    return { source: 'error', reason: 'forced' };
  }

  try {
    const response = await fetch(REPORT_SUMMARY_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    });
    if (!response.ok) {
      return { source: 'error', reason: 'http_error', error: await readError(response) };
    }
    return { source: 'api', response: (await response.json()) as ReportSummaryResponse };
  } catch (error) {
    return { source: 'error', reason: 'unavailable', error };
  }
}

export function readLatestScheduleReportSnapshot(): ScheduleReportSnapshot | null {
  if (latestReportSnapshot) return latestReportSnapshot;
  latestReportSnapshot = readStoredScheduleReportSnapshot();
  return latestReportSnapshot;
}

export function writeLatestScheduleReportSummary(summary: ReportSummaryResponse): void {
  const snapshot = latestReportSnapshot ?? readStoredScheduleReportSnapshot();
  if (!snapshot) return;
  writeLatestScheduleReportSnapshot({ ...snapshot, report_summary: summary });
}

export function isScheduleApiForcedMock(): boolean {
  return shouldForceMock();
}

export function buildGenerateRequest({ rooms, batches, teams }: GenerateScheduleInput): GenerateRequest {
  const projectBundle = currentProjectBundleSource();
  if (projectBundle) {
    const source = indexProjectBundle(projectBundle);
    return {
      inputs: {
        project: projectBundle.project,
        rooms: rooms.map((room) => toContractRoom(room, source.rooms.get(room.code))),
        pods: rooms.flatMap((room) => room.pods.map((pod) => toContractPod(room, pod.id, source.pods.get(pod.id)))),
        arrivals: [...(projectBundle.arrivals ?? [])],
        teams: teams.map((team) => toContractTeam(team, source.teams.get(team.id))),
        activities: projectBundle.activities,
        dependencies: projectBundle.dependencies,
        batches: batches.map((batch) => toContractBatch(batch, source.batches.get(batch.id))),
        anchors: [...(projectBundle.anchors ?? [])],
        rule_config: projectBundle.rule_config,
      },
    };
  }

  const pods = rooms.flatMap((room) => room.pods.map((pod) => toContractPod(room, pod.id)));
  const mockProjectStart = deriveProjectStart(rooms, batches);
  const inputs: InputBundle = {
    project: buildMockProject(pods.length, mockProjectStart),
    rooms: rooms.map((room) => toContractRoom(room)),
    pods,
    arrivals: rooms.flatMap((room) => toContractArrivals(room, mockProjectStart)),
    teams: teams.map((team) => toContractTeam(team)),
    activities: MOCK_SCHEDULE_TEMPLATE,
    dependencies: MOCK_SCHEDULE_DEPENDENCIES,
    batches: batches.map((batch) => toContractBatch(batch)),
    anchors: [],
    rule_config: DEFAULT_RULE_CONFIG,
  };

  return { inputs };
}

type ProjectBundleIndex = {
  rooms: Map<string, Room>;
  pods: Map<string, Pod>;
  teams: Map<string, Team>;
  batches: Map<string, Batch>;
};

function indexProjectBundle(bundle: InputBundle): ProjectBundleIndex {
  return {
    rooms: new Map(bundle.rooms.map((room) => [room.room_id, room])),
    pods: new Map(bundle.pods.map((pod) => [pod.pod_id, pod])),
    teams: new Map((bundle.teams ?? []).map((team) => [team.team_id, team])),
    batches: new Map(bundle.batches.map((batch) => [batch.batch_id, batch])),
  };
}

function currentProjectBundleSource(): InputBundle | null {
  return shouldForceMock() ? null : latestProjectBundle;
}

function projectDataPath(totalCardCount?: number): string {
  if (!Number.isFinite(totalCardCount) || !totalCardCount) {
    return PROJECT_DATA_PATH;
  }
  const params = new URLSearchParams({ total_card_count: String(Math.round(totalCardCount)) });
  return `${PROJECT_DATA_PATH}?${params.toString()}`;
}

function mapProjectDataToRows(bundle: InputBundle): ProjectScheduleData {
  const batches = bundle.batches.map((batch, index) => toBatchRow(batch, index));
  const batchByPod = new Map<string, BatchRow>();
  batches.forEach((batch) => batch.podIds.forEach((podId) => batchByPod.set(podId, batch)));

  const arrivalsByPod = new Map<string, ArrivalItem[]>();
  (bundle.arrivals ?? []).forEach((arrival) => {
    const arrivals = arrivalsByPod.get(arrival.pod_id) ?? [];
    arrivals.push(arrival);
    arrivalsByPod.set(arrival.pod_id, arrivals);
  });

  const podsByRoom = new Map<string, Pod[]>();
  bundle.pods.forEach((pod) => {
    const pods = podsByRoom.get(pod.room_id) ?? [];
    pods.push(pod);
    podsByRoom.set(pod.room_id, pods);
  });

  const roomGridByBatch = new Map<string, number>();
  const rooms = bundle.rooms.map((room, roomIndex) => {
    const pods = podsByRoom.get(room.room_id) ?? [];
    const batchId = firstBatchIdForPods(pods, batchByPod, batches);
    const gx = batchId ? Math.max(0, batches.findIndex((batch) => batch.id === batchId)) : roomIndex;
    const gy = roomGridByBatch.get(batchId ?? room.room_id) ?? 0;
    roomGridByBatch.set(batchId ?? room.room_id, gy + 1);
    const hasReady = Boolean(room.cabling_ready_date || room.install_ready_date || room.liquid_ready_date);

    return {
      code: room.room_id,
      proj: bundle.project.project_name || bundle.project.project_id,
      gx,
      gy,
      site: hasReady ? 'ready' : 'pending',
      readyBatch: batchId ? `ready-${batchId}` : `ready-${room.room_id}`,
      goLiveBatch: batchId ?? `batch-${room.room_id}`,
      cableReadyAt: room.cabling_ready_date ?? undefined,
      equipReadyAt: room.install_ready_date ?? undefined,
      liquidReadyAt: room.liquid_ready_date ?? undefined,
      readyUnknown: !hasReady,
      pods: pods.map((pod) => toPodRow(pod, arrivalsByPod.get(pod.pod_id) ?? [], batchByPod)),
    } satisfies RoomRow;
  });

  return {
    project: bundle.project,
    rooms,
    batches,
    teams: (bundle.teams ?? []).map(toTeamRow),
  };
}

function toBatchRow(batch: Batch, index: number): BatchRow {
  return {
    id: batch.batch_id,
    name: batch.batch_name,
    color: BATCH_COLORS[index % BATCH_COLORS.length]!,
    powerOnDate: batch.power_on_target_date ?? '',
    goLiveDate: batch.online_target_date ?? '',
    podIds: [...batch.pod_ids],
  };
}

function firstBatchIdForPods(pods: Pod[], batchByPod: Map<string, BatchRow>, batches: BatchRow[]): string | null {
  const ids = new Set(pods.map((pod) => batchByPod.get(pod.pod_id)?.id).filter((id): id is string => Boolean(id)));
  return batches.find((batch) => ids.has(batch.id))?.id ?? null;
}

function toPodRow(pod: Pod, arrivals: ArrivalItem[], batchByPod: Map<string, BatchRow>): RoomRow['pods'][number] {
  const arrivalDate = maxIso(arrivals.map((arrival) => arrival.arrival_date));
  const hasArrived = arrivals.length > 0 && arrivals.every((arrival) => arrival.arrival_status === '已到货');
  const batchId = batchByPod.get(pod.pod_id)?.id ?? '';

  if (!arrivalDate) {
    return {
      id: pod.pod_id,
      arrival: 'unknown',
      etaLabel: '待定',
      status: 'pending',
      goLiveBatch: batchId,
    };
  }

  return {
    id: pod.pod_id,
    arrival: hasArrived ? 'arrived' : 'eta',
    etaLabel: hasArrived ? '可上架' : `在途 ${arrivalDate.slice(5)}`,
    etaDate: hasArrived ? undefined : arrivalDate,
    status: 'pending',
    goLiveBatch: batchId,
  };
}

function toTeamRow(team: Team): TeamRow {
  return {
    id: team.team_id,
    n: team.size ?? 12,
    exp: team.experience === '丰富' ? 'full' : 'junior',
    st: team.on_site === false ? 'wait' : 'on',
  };
}

function maxIso(dates: Array<string | null | undefined>): string | null {
  const values = dates.filter((date): date is string => Boolean(date));
  return values.length ? values.reduce((latest, date) => (date > latest ? date : latest), values[0]!) : null;
}

function minIso(dates: Array<string | null | undefined>): string | null {
  const values = dates.filter((date): date is string => Boolean(date));
  return values.length ? values.reduce((earliest, date) => (date < earliest ? date : earliest), values[0]!) : null;
}

function deriveProjectStart(rooms: RoomRow[], batches: BatchRow[]): string | null {
  return minIso([
    ...rooms.flatMap((room) => [
      room.cableReadyAt,
      room.equipReadyAt,
      room.liquidReadyAt,
      ...room.pods.map((pod) => pod.etaDate),
    ]),
    ...batches.flatMap((batch) => [batch.powerOnDate, batch.goLiveDate]),
  ]);
}

function shouldForceMock(): boolean {
  const envForced = import.meta.env.VITE_SCHEDULE_FORCE_MOCK === FORCE_MOCK_FLAG;
  const browserForced =
    typeof window !== 'undefined' && window.localStorage?.getItem('aida_schedule_force_mock') === FORCE_MOCK_FLAG;
  return envForced || browserForced;
}

function writeLatestScheduleReportSnapshot(snapshot: ScheduleReportSnapshot): void {
  latestReportSnapshot = snapshot;
  if (typeof window === 'undefined') return;
  try {
    window.localStorage?.setItem(REPORT_SNAPSHOT_STORAGE_KEY, JSON.stringify(snapshot));
  } catch (error) {
    console.warn('[T-023] failed to persist schedule risk report snapshot', error);
  }
}

function readStoredScheduleReportSnapshot(): ScheduleReportSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage?.getItem(REPORT_SNAPSHOT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return isScheduleReportSnapshot(parsed) ? parsed : null;
  } catch (error) {
    console.warn('[T-023] failed to read schedule risk report snapshot', error);
    return null;
  }
}

function isScheduleReportSnapshot(value: unknown): value is ScheduleReportSnapshot {
  if (!isRecord(value)) return false;
  return (
    value.source === 'api' &&
    typeof value.plan_id === 'string' &&
    typeof value.version === 'number' &&
    typeof value.committed_at === 'string' &&
    isRecord(value.project) &&
    isRecord(value.inputs) &&
    isRecord(value.plan)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

async function readError(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

function normalizedDurationOverrides(overrides?: Record<string, number>): Record<string, number> | undefined {
  const entries = Object.entries(overrides ?? {})
    .map(([instanceId, days]) => [instanceId, Math.round(days)] as const)
    .filter(([instanceId, days]) => instanceId && Number.isFinite(days) && days > 0);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function buildMockProject(podCount: number, startDate: string | null): Project {
  return {
    project_id: 'aida-plan-init',
    project_name: '智算一期 2026 Q2',
    start_date: startDate,
    handover_date: null,
    scene: '集群集成',
    product_form: 'A3',
    cooling_method: 'liquid_cooling',
    project_scale: '标准项目',
    total_card_count: podCount * 384,
    note: 'mock 回退：前端基于排期盘子生成的初排请求。',
  };
}

function buildChangeSet(input: AdjustScheduleInput, baseline: GenerateScheduleInput): ChangeSet {
  const currentRequest = buildGenerateRequest(input);
  const baselineRequest = buildGenerateRequest(baseline);
  const changeKeys = new Set(input.changeKeys);
  const changedRoomIds = idsFromChangeKeys(changeKeys, 'room');
  const changedPodIds = idsFromChangeKeys(changeKeys, 'pod');
  const changedTeamIds = idsFromChangeKeys(changeKeys, 'team');
  const changedBatchIds = idsFromChangeKeys(changeKeys, 'batch');

  const rooms = currentRequest.inputs.rooms.filter((room) =>
    changedRoomIds.has(room.room_id) || !hasSameById(baselineRequest.inputs.rooms, room, 'room_id'),
  );
  const arrivals = buildArrivalChanges(
    input.rooms,
    changedPodIds,
    currentRequest.inputs.arrivals ?? [],
    baselineRequest.inputs.arrivals ?? [],
  );
  const teams = (currentRequest.inputs.teams ?? []).filter((team) =>
    changedTeamIds.has(team.team_id) || !hasSameById(baselineRequest.inputs.teams ?? [], team, 'team_id'),
  );
  const batches = currentRequest.inputs.batches.filter((batch) =>
    changedBatchIds.has(batch.batch_id) || !hasSameById(baselineRequest.inputs.batches, batch, 'batch_id'),
  );

  return {
    rooms,
    arrivals,
    teams,
    batches,
    anchors: buildBatchAnchors(batches),
    demands: buildBatchDemands(currentRequest.inputs.batches, baselineRequest.inputs.batches),
    incidents: (input.incidents ?? []).map(toIncidentEvent),
    rule_config: currentRequest.inputs.rule_config,
  };
}

function idsFromChangeKeys(changeKeys: Set<string>, prefix: string): Set<string> {
  const ids = new Set<string>();
  changeKeys.forEach((key) => {
    const [kind, id] = key.split(':');
    if (kind === prefix && id && id !== 'new') ids.add(id);
  });
  return ids;
}

function hasSameById<T, K extends keyof T>(items: T[], item: T, idKey: K): boolean {
  const found = items.find((candidate) => candidate[idKey] === item[idKey]);
  return found ? JSON.stringify(found) === JSON.stringify(item) : false;
}

function buildArrivalChanges(
  rooms: RoomRow[],
  changedPodIds: Set<string>,
  currentArrivals: ArrivalItem[],
  baselineArrivals: ArrivalItem[],
): ArrivalItem[] {
  const sourceByPod = new Map<string, ArrivalItem[]>();
  currentArrivals.forEach((arrival) => {
    const arrivals = sourceByPod.get(arrival.pod_id) ?? [];
    arrivals.push(arrival);
    sourceByPod.set(arrival.pod_id, arrivals);
  });

  const changedArrivals: ArrivalItem[] = [];
  rooms.forEach((room) => {
    room.pods.forEach((pod) => {
      if (!changedPodIds.has(pod.id)) return;
      const source = sourceByPod.get(pod.id) ?? [];
      if (source.length) {
        changedArrivals.push(...source.map((arrival) => applyPodArrivalState(arrival, pod)));
        return;
      }
      changedArrivals.push(...toContractArrivals({ ...room, pods: [pod] }, null));
    });
  });

  const changedArrivalIds = new Set(changedArrivals.map((arrival) => arrival.arrival_id));
  return [
    ...changedArrivals,
    ...currentArrivals.filter((arrival) =>
      !changedArrivalIds.has(arrival.arrival_id) && !hasSameById(baselineArrivals, arrival, 'arrival_id'),
    ),
  ];
}

function applyPodArrivalState(arrival: ArrivalItem, pod: RoomRow['pods'][number]): ArrivalItem {
  return {
    ...arrival,
    arrival_date: pod.etaDate ?? null,
    arrival_status: pod.arrival === 'arrived' ? '已到货' : pod.arrival === 'eta' ? '在途' : '未明',
  };
}

function buildBatchAnchors(batches: Batch[]): NonNullable<ChangeSet['anchors']> {
  return batches.flatMap((batch) => {
    const anchors: NonNullable<ChangeSet['anchors']> = [];
    if (batch.power_on_target_date) {
      anchors.push({
        anchor_id: `anchor-${batch.batch_id}-power-on`,
        target: { kind: '批次上电', ref_id: batch.batch_id },
        anchor_date: batch.power_on_target_date,
        anchor_source: '上电',
        is_hard: true,
      });
    }
    if (batch.online_target_date) {
      anchors.push({
        anchor_id: `anchor-${batch.batch_id}-online`,
        target: { kind: '批次上线', ref_id: batch.batch_id },
        anchor_date: batch.online_target_date,
        anchor_source: '上线',
        is_hard: true,
      });
    }
    return anchors;
  });
}

function buildBatchDemands(current: Batch[], baseline: Batch[]): NonNullable<ChangeSet['demands']> {
  const baselineById = new Map(baseline.map((batch) => [batch.batch_id, batch]));
  const demands: NonNullable<ChangeSet['demands']> = [];
  for (const batch of current) {
    const before = baselineById.get(batch.batch_id);
    if (!before) continue;
    addDateDemand(demands, batch.batch_id, '批次上线', before.online_target_date ?? null, batch.online_target_date ?? null);
    addDateDemand(demands, batch.batch_id, '批次上电', before.power_on_target_date ?? null, batch.power_on_target_date ?? null);
  }
  return demands;
}

function addDateDemand(
  demands: NonNullable<ChangeSet['demands']>,
  batchId: string,
  kind: '批次上线' | '批次上电',
  before: string | null,
  after: string | null,
): void {
  if (!before || !after || before === after) return;
  const delta = daysBetween(before, after);
  if (delta === 0) return;
  demands.push({
    demand_id: `demand-${batchId}-${kind === '批次上线' ? 'online' : 'power-on'}`,
    target: { kind, ref_id: batchId },
    direction: delta > 0 ? '延后' : '提前',
    amount_days: Math.abs(delta),
    reason: '前端计划调整页目标日期变更',
  });
}

function daysBetween(before: string, after: string): number {
  return Math.round((Date.parse(after + 'T00:00:00Z') - Date.parse(before + 'T00:00:00Z')) / 86400000);
}

function toIncidentEvent(event: ScheduleIncidentInput): NonNullable<ChangeSet['incidents']>[number] {
  return {
    incident_id: event.id,
    incident_type: event.kind === 'holiday' ? '假期停工' : '效率打折',
    window: { start: event.start, end: event.end },
    efficiency: event.kind === 'holiday' ? 0 : Math.max(0.01, Math.min(1, event.efficiency)),
    reason: event.label,
  };
}

function cloneScheduleInput(input: GenerateScheduleInput): GenerateScheduleInput {
  return {
    rooms: JSON.parse(JSON.stringify(input.rooms)) as RoomRow[],
    batches: JSON.parse(JSON.stringify(input.batches)) as BatchRow[],
    teams: JSON.parse(JSON.stringify(input.teams)) as TeamRow[],
  };
}

function baselineToGenerateResponse(snapshot: BaselineSnapshot): GenerateResponse {
  return {
    plan: {
      plan_id: snapshot.baseline.plan_id,
      version: snapshot.baseline.version,
      base_version: null,
      activities: [],
      critical_path: [],
      project_finish_date: null,
    },
    readiness_suggestions: [],
    risks: [],
    unmet: [],
    explanation: {
      is_initial: false,
      notes: ['前端沿用最近一次计划基线版本。'],
    },
  };
}

function toContractRoom(room: RoomRow, source?: Room): Room {
  if (source) {
    return {
      ...source,
      room_id: room.code,
      cabling_ready_date: room.cableReadyAt ?? null,
      install_ready_date: room.equipReadyAt ?? null,
      liquid_ready_date: room.liquidReadyAt ?? null,
    };
  }

  return {
    room_id: room.code,
    cabling_ready_date: room.cableReadyAt ?? null,
    install_ready_date: room.equipReadyAt ?? null,
    liquid_ready_date: room.liquidReadyAt ?? null,
    power_off_windows: [],
    note: room.readyUnknown ? '初始化页：机房 ready 待定' : null,
  };
}

function toContractPod(room: RoomRow, podId: string, source?: Pod): Pod {
  if (source) {
    return {
      ...source,
      pod_id: podId,
      room_id: room.code,
    };
  }

  return {
    pod_id: podId,
    room_id: room.code,
    compute_cabinet_count: 1,
    other_cabinet_count: 1,
    note: null,
  };
}

function toContractArrivals(room: RoomRow, fallbackArrivalDate: string | null): ArrivalItem[] {
  return room.pods.map((pod) => {
    const arrivalDate = pod.etaDate ?? (pod.arrival === 'arrived' ? fallbackArrivalDate : null);
    return {
      arrival_id: `arrival-${pod.id}`,
      pod_id: pod.id,
      device_type: '设备到货齐套',
      device_model: null,
      unit: '批',
      quantity: 1,
      arrival_date: arrivalDate,
      arrival_status: pod.arrival === 'arrived' ? '已到货' : pod.arrival === 'eta' ? '在途' : '未明',
      note: room.code,
    };
  });
}

function toContractTeam(team: TeamRow, source?: Team): Team {
  if (source) {
    return {
      ...source,
      team_id: team.id,
      size: team.n,
      experience: team.exp === 'full'
        ? '丰富'
        : source.experience && source.experience !== '丰富'
          ? source.experience
          : '一般',
      on_site: team.st === 'on',
    };
  }

  return {
    team_id: team.id,
    size: team.n,
    experience: team.exp === 'full' ? '丰富' : '一般',
    on_site: team.st === 'on',
    available_from: null,
  };
}

function toContractBatch(batch: BatchRow, source?: Batch): Batch {
  if (source) {
    return {
      ...source,
      batch_id: batch.id,
      batch_name: batch.name,
      pod_ids: [...batch.podIds],
      power_on_target_date: batch.powerOnDate || null,
      online_target_date: batch.goLiveDate || null,
    };
  }

  return {
    batch_id: batch.id,
    batch_name: batch.name,
    pod_ids: [...batch.podIds],
    power_on_target_date: batch.powerOnDate || null,
    online_target_date: batch.goLiveDate || null,
  };
}

const DEFAULT_RULE_CONFIG: RuleConfig = {
  concentrate_top_k: 5,
  skip_weekends: false,
  anchor_priority_override: null,
};

// Mock fallback only. Real /project-data mode must preserve InputBundle.activities.
const MOCK_SCHEDULE_TEMPLATE: ScheduleActivity[] = [
  {
    activity_id: 'room_ready',
    activity_name: '机房就位',
    phase: '站',
    scope: '机房级',
    activity_type: '机房准备',
    constraint_source: '站',
    duration_mode: '固定',
    standard_sla_days: 7,
    minimum_sla_days: 1,
    workload_rules: [],
    is_default_milestone: true,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'arrival',
    activity_name: '设备到货',
    phase: '货',
    scope: 'PoD级',
    activity_type: '到货',
    constraint_source: '货',
    duration_mode: '固定',
    standard_sla_days: 1,
    minimum_sla_days: 1,
    workload_rules: [],
    is_default_milestone: true,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'install',
    activity_name: '机柜上架安装',
    phase: '工程安装',
    scope: 'PoD级',
    activity_type: '普通',
    constraint_source: '人',
    duration_mode: '固定',
    standard_sla_days: 5,
    minimum_sla_days: 2,
    workload_rules: [],
    is_default_milestone: false,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'cabling',
    activity_name: '综合布线',
    phase: '工程安装',
    scope: 'PoD级',
    activity_type: '普通',
    constraint_source: '人',
    duration_mode: '固定',
    standard_sla_days: 4,
    minimum_sla_days: 2,
    workload_rules: [],
    is_default_milestone: false,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'power_on',
    activity_name: '上电点亮',
    phase: '上电联调',
    scope: '批次级',
    activity_type: '里程碑',
    constraint_source: null,
    duration_mode: '固定',
    standard_sla_days: 1,
    minimum_sla_days: 1,
    workload_rules: [],
    is_default_milestone: true,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'online',
    activity_name: '批次上线',
    phase: '上电联调',
    scope: '批次级',
    activity_type: '里程碑',
    constraint_source: null,
    duration_mode: '固定',
    standard_sla_days: 1,
    minimum_sla_days: 1,
    workload_rules: [],
    is_default_milestone: true,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
  {
    activity_id: 'handover',
    activity_name: '客户整体验收移交',
    phase: '验收交付',
    scope: '项目级',
    activity_type: '里程碑',
    constraint_source: null,
    duration_mode: '固定',
    standard_sla_days: 2,
    minimum_sla_days: 1,
    workload_rules: [],
    is_default_milestone: true,
    responsibility: null,
    note: null,
    risk_rule: null,
  },
];

// Mock fallback only. Real /project-data mode must preserve InputBundle.dependencies.
const MOCK_SCHEDULE_DEPENDENCIES: Dependency[] = [
  { from_activity_id: 'room_ready', to_activity_id: 'install', dep_type: 'FS' },
  { from_activity_id: 'arrival', to_activity_id: 'install', dep_type: 'FS' },
  { from_activity_id: 'install', to_activity_id: 'cabling', dep_type: 'FS' },
  { from_activity_id: 'cabling', to_activity_id: 'power_on', dep_type: 'FS' },
  { from_activity_id: 'power_on', to_activity_id: 'online', dep_type: 'FS' },
  { from_activity_id: 'online', to_activity_id: 'handover', dep_type: 'FS' },
];
