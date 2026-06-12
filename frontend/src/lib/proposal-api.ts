/**
 * 交付预案 API 客户端
 *
 * 代理：/api → http://127.0.0.1:7401（vite.config.ts）
 */

const DEFAULT_PROJECT_ID = 'demo-project-001';

export interface NetPlaneRow {
  row_id: string;
  type: string;
  vendor: string;
  model: string;
  ver: string;
  qty: number;
  source: string;
  proposal_version: string | null;
  note: string | null;
}

export interface DeviceRoleItem {
  key: string;
  label: string;
}

export interface AvailableDeviceItem {
  vendor: string;
  device_model: string;
  device_version: string;
  boq_quantity: number;
}

export interface ClusterDeviceRow {
  row_id: string;
  source_net_plane_id: string | null;
  max_quantity: number;
  cluster_id: string | null;
  cluster_type: string;
  super_pod_id: string | null;
  storage_cluster_id: string | null;
  zone_id: string | null;
  ccae_cluster_id: string | null;
  dme_cluster_id: string | null;
  device_type: string;
  vendor: string;
  device_model: string;
  device_purpose: string | null;
  start_device_name: string | null;
  end_device_name: string | null;
  quantity: number;
  data_source: string;
  proposal_version: string | null;
}

export interface NetMgmtRow {
  row_id: string;
  server_role: string;
  server_model: string;
  quantity: number;
  data_source: string;
}

export interface NetPlaneOption {
  row_id: string;
  type: string;
  vendor: string;
  model: string;
  qty: number;
}

export interface WarningItem {
  code: string;
  message: string;
}

interface ApiResponse<T> {
  code: number;
  data: T;
  meta: { project_id: string; timestamp: string };
}

const AUTH_HEADERS: Record<string, string> = {
  'X-User-Role': 'td',
  'X-User-Account': 'dev',
};

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const hasBody = options?.body != null;
  const baseHeaders: Record<string, string> = { ...AUTH_HEADERS };
  if (hasBody) baseHeaders['Content-Type'] = 'application/json';
  const res = await fetch(url, {
    ...options,
    headers: { ...baseHeaders, ...(options?.headers as Record<string, string> | undefined) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === 'string') throw new Error(detail);
    if (detail && typeof detail === 'object' && 'message' in detail)
      throw new Error((detail as { message: string }).message);
    throw new Error(`HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  const json: ApiResponse<T> = await res.json();
  return json.data;
}

export const proposalApi = {
  listNetPlanes(projectId = DEFAULT_PROJECT_ID) {
    return request<{ rows: NetPlaneRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane`,
    );
  },

  listDeviceRoles(projectId = DEFAULT_PROJECT_ID) {
    return request<{ device_roles: DeviceRoleItem[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/device-roles`,
    );
  },

  listAvailableDevices(projectId = DEFAULT_PROJECT_ID) {
    return request<{ devices: AvailableDeviceItem[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/available-devices`,
    );
  },

  exportNetPlanes(rows: NetPlaneRow[], projectId = DEFAULT_PROJECT_ID) {
    return request<{ saved_path: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },

  createNetPlane(sourceRowId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<{ row: NetPlaneRow }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane`,
      {
        method: 'POST',
        body: JSON.stringify({ source_row_id: sourceRowId }),
      },
    );
  },

  updateNetPlane(
    rowId: string,
    patch: {
      type?: string;
      vendor?: string;
      model?: string;
      ver?: string;
      qty?: number;
      source?: string;
      note?: string | null;
    },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<{ row: NetPlaneRow; warnings: WarningItem[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/${rowId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      },
    );
  },

  deleteNetPlane(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<{ deleted: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.1/net-plane/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },

  listNetPlaneOptions(projectId = DEFAULT_PROJECT_ID) {
    return request<{ options: NetPlaneOption[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/net-plane-options`,
    );
  },

  listNetMgmt(projectId = DEFAULT_PROJECT_ID) {
    return request<{ rows: NetMgmtRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt`,
    );
  },

  initializeNetMgmt(projectId = DEFAULT_PROJECT_ID) {
    return request<{ rows: NetMgmtRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/initialize`,
      { method: 'POST' },
    );
  },

  updateNetMgmt(
    rowId: string,
    patch: { server_model?: string; quantity?: number },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<NetMgmtRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/${rowId}`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
  },

  deleteNetMgmt(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/${rowId}`,
      { method: 'DELETE' },
    );
  },

  exportNetMgmt(rows: NetMgmtRow[], projectId = DEFAULT_PROJECT_ID) {
    return request<{ saved_path: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.2/net-mgmt/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },

  listClusterDevices(projectId = DEFAULT_PROJECT_ID) {
    return request<{ rows: ClusterDeviceRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list`,
    );
  },

  createClusterDevice(sourceNetPlaneId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<ClusterDeviceRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list`,
      {
        method: 'POST',
        body: JSON.stringify({ source_net_plane_id: sourceNetPlaneId }),
      },
    );
  },

  updateClusterDevice(
    rowId: string,
    patch: {
      cluster_id?: string;
      cluster_type?: string;
      super_pod_id?: string;
      storage_cluster_id?: string;
      zone_id?: string;
      ccae_cluster_id?: string;
      dme_cluster_id?: string;
      device_type?: string;
      device_purpose?: string;
      start_device_name?: string;
      end_device_name?: string;
      quantity?: number;
    },
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<ClusterDeviceRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/${rowId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(patch),
      },
    );
  },

  deleteClusterDevice(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },

  exportClusterDevices(rows: ClusterDeviceRow[], projectId = DEFAULT_PROJECT_ID) {
    return request<{ saved_path: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/5.3/cluster-device-list/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },
};

export interface RoomRackRow {
  row_id: string;
  pod_name: string;
  room_name: string;
  compute: string;
  bus: string;
  param_leaf: string;
  biz_leaf: string;
  mgmt: string;
  sample_leaf: string;
  data_source: string;
}

export interface DeviceInfoItem {
  section: string;
  device_model: string;
  device_role: string;
  device_qty: string;
  card_model: string;
  card_qty: number | null;
  source_basename: string;
}

export const roomRackApi = {
  list(projectId = DEFAULT_PROJECT_ID) {
    return request<{ rows: RoomRackRow[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack`,
    );
  },

  create(
    data: Partial<Omit<RoomRackRow, 'row_id' | 'data_source'>>,
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<RoomRackRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) },
    );
  },

  createAfter(
    sourceRowId: string,
    data: Partial<Omit<RoomRackRow, 'row_id' | 'data_source'>>,
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<RoomRackRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack?source_row_id=${encodeURIComponent(sourceRowId)}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) },
    );
  },

  update(
    rowId: string,
    data: Partial<Omit<RoomRackRow, 'row_id' | 'data_source'>>,
    projectId = DEFAULT_PROJECT_ID,
  ) {
    return request<RoomRackRow>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/${rowId}`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) },
    );
  },

  delete(rowId: string, projectId = DEFAULT_PROJECT_ID) {
    return request<void>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/${rowId}?confirm=true`,
      { method: 'DELETE' },
    );
  },

  export(rows: RoomRackRow[], projectId = DEFAULT_PROJECT_ID) {
    return request<{ saved_path: string }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/room-rack/export`,
      { method: 'POST', body: JSON.stringify({ rows }) },
    );
  },

  listDeviceInfoTable(projectId = DEFAULT_PROJECT_ID) {
    return request<{ items: DeviceInfoItem[] }>(
      `/api/v1/projects/${projectId}/proposal/chapters/7.1/device-info-table`,
    );
  },
};

export class ProposalApiError extends Error {
  code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = 'ProposalApiError';
    this.code = code;
  }
}

export interface DraftManifest {
  workingVersionLabel: string;
  status: string;
  etag?: string;
  dirty?: boolean;
}

export interface CumulativeChangeEntry {
  section: string;
  field: string;
  before: string;
  after: string;
  source: string;
  editable?: boolean;
}

export interface ManifestActivity {
  updatedBy?: string;
  updatedAt?: string;
  etag?: string;
}

export interface ProposalVersionItem {
  proposalVersion: string;
  status: string;
  label: string;
  tone: string;
  isLatest: boolean;
  isEditable: boolean;
}

export interface VersionInfoMetadata {
  proposalVersion: string;
  projectName: string;
  createdBy?: string;
  createdAt?: string;
  updatedBy?: string;
  updatedAt?: string;
}

export type DeliveryChannel = '华为' | '客户';

export interface MaintenanceSlaRow {
  row_id: string;
  service_item: string;
  sla_level: string;
  response_time: string;
  recovery_time: string;
  data_source: string;
}

export interface MaintenanceStrategyRow {
  row_id: string;
  strategy_name: string;
  content: string;
  data_source: string;
}

export interface ServiceContentRow {
  row_id: string;
  service_name: string;
  description: string;
  data_source: string;
}

export interface ServiceDeliveryUiRow {
  row_id: string;
  module: string;
  channel: DeliveryChannel;
  content: string;
  data_source: string;
}

export interface DeviceInfoRow {
  row_id: string;
  device_name: string;
  device_model: string;
  device_role: string;
  vendor: string;
  quantity: number;
  data_source: string;
}

export function getDefaultProjectId(): string {
  return DEFAULT_PROJECT_ID;
}

export function formatProposalDateTime(dt?: string): string {
  if (!dt) return '—';
  return dt;
}

export function useProposalApiHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-User-Role': 'td',
    'X-User-Account': 'dev',
  };
}

export async function fetchDraft(projectId: string, _headers?: Record<string, string>) {
  return request<{ manifest?: DraftManifest } & Record<string, unknown>>(
    `/api/v1/projects/${projectId}/proposal/draft`,
  );
}

export async function fetchVersions(projectId: string, _headers?: Record<string, string>) {
  const data = await request<{ versions: ProposalVersionItem[] }>(
    `/api/v1/projects/${projectId}/proposal/versions`,
  );
  return data.versions ?? [];
}

export async function fetchVersionSnapshot(
  projectId: string,
  version: string,
  _headers?: Record<string, string>,
) {
  return request<Record<string, unknown>>(
    `/api/v1/projects/${projectId}/proposal/versions/${version}`,
  );
}

export async function saveDraft(
  projectId: string,
  _headers: Record<string, string>,
  _payload: Record<string, unknown>,
  _etag?: string,
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (_etag) headers['If-Match'] = _etag;
  return request<{ etag?: string; workingVersionLabel?: string; metadata?: Record<string, unknown>; createdBy?: string }>(
    `/api/v1/projects/${projectId}/proposal/draft`,
    { method: 'PUT', headers, body: JSON.stringify(_payload) },
  );
}

export async function releaseAndDecide(
  projectId: string,
  _headers: Record<string, string>,
  _payload: Record<string, unknown>,
) {
  return request<{ progress?: Array<Record<string, unknown>> }>(
    `/api/v1/projects/${projectId}/proposal/release`,
    { method: 'POST', body: JSON.stringify(_payload) },
  );
}

export async function exportDocument(
  projectId: string,
  _headers: Record<string, string>,
  version: string,
): Promise<Blob> {
  const res = await fetch(
    `/api/v1/projects/${projectId}/proposal/export/document?version=${encodeURIComponent(version)}`,
    { headers: { ...AUTH_HEADERS, ..._headers } },
  );
  if (!res.ok) throw new ProposalApiError(`导出失败 (HTTP ${res.status})`, 'EXPORT_FAILED');
  return res.blob();
}

export async function loadChangeLogForDraft(
  _projectId: string,
  _headers: Record<string, string>,
  _draftData: unknown,
): Promise<CumulativeChangeEntry[]> {
  return [];
}

export async function loadChangeLogThroughVersion(
  _projectId: string,
  _headers: Record<string, string>,
  _version: string,
  _draftData: unknown,
): Promise<CumulativeChangeEntry[]> {
  return [];
}

export function resolveVersionInfoMetadata(
  data: unknown,
  fallback: VersionInfoMetadata,
  _verItem?: ProposalVersionItem,
): VersionInfoMetadata {
  const d = data as Record<string, unknown>;
  const meta = (d.metadata ?? {}) as Record<string, unknown>;
  const manifest = (d.manifest ?? {}) as Record<string, unknown>;
  return {
    proposalVersion: String(manifest.workingVersionLabel ?? fallback.proposalVersion),
    projectName: fallback.projectName,
    createdBy: String(meta.createdBy ?? manifest.createdBy ?? fallback.createdBy ?? ''),
    createdAt: String(meta.createdAt ?? manifest.createdAt ?? fallback.createdAt ?? ''),
    updatedBy: String(meta.updatedBy ?? manifest.updatedBy ?? fallback.updatedBy ?? ''),
    updatedAt: String(meta.updatedAt ?? manifest.updatedAt ?? fallback.updatedAt ?? ''),
  };
}

export function manualLogToChangeRecords(
  log: CumulativeChangeEntry[],
): Array<Record<string, unknown>> {
  return log.map((e) => ({ section: e.section, field: e.field, before: e.before, after: e.after }));
}

export async function fetchMaintenanceSla(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: MaintenanceSlaRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.4/maintenance-sla`,
  );
}

export async function fetchMaintenanceStrategy(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: MaintenanceStrategyRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.3/maintenance-strategy`,
  );
}

export async function fetchServiceContent(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: ServiceContentRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.2/service-content`,
  );
}

export async function fetchServiceDeliveryUi(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: ServiceDeliveryUiRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.1/service-delivery-ui`,
  );
}

export async function initializeServiceDeliveryUi(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: ServiceDeliveryUiRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.1/service-delivery-ui/initialize`,
    { method: 'POST' },
  );
}

export async function parseMaintenanceBoq(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: MaintenanceSlaRow[] }>(
    `/api/v1/projects/${projectId}/proposal/parse/maintenance-boq`,
    { method: 'POST' },
  );
}

export async function parseMaintenanceProposalDoc(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: MaintenanceStrategyRow[] }>(
    `/api/v1/projects/${projectId}/proposal/parse/maintenance-boq`,
    { method: 'POST' },
  );
}

export async function parseServiceBoq(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: ServiceContentRow[] }>(
    `/api/v1/projects/${projectId}/proposal/parse/service-boq`,
    { method: 'POST' },
  );
}

export async function patchMaintenanceSlaRow(
  projectId: string,
  rowId: string,
  patch: Record<string, unknown>,
  _headers?: Record<string, string>,
) {
  return request<MaintenanceSlaRow>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.4/maintenance-sla/${rowId}`,
    { method: 'PATCH', body: JSON.stringify(patch) },
  );
}

export async function patchMaintenanceStrategyRow(
  projectId: string,
  rowId: string,
  patch: Record<string, unknown>,
  _headers?: Record<string, string>,
) {
  return request<MaintenanceStrategyRow>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.3/maintenance-strategy/${rowId}`,
    { method: 'PATCH', body: JSON.stringify(patch) },
  );
}

export async function patchServiceDeliveryUiRow(
  projectId: string,
  rowId: string,
  patch: Record<string, unknown>,
  _headers?: Record<string, string>,
) {
  return request<ServiceDeliveryUiRow>(
    `/api/v1/projects/${projectId}/proposal/chapters/8.1/service-delivery-ui/${rowId}`,
    { method: 'PATCH', body: JSON.stringify(patch) },
  );
}

export async function fetchDeviceInfo(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: DeviceInfoRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/2/device-info`,
  );
}

export async function patchDeviceInfoRow(
  projectId: string,
  rowId: string,
  patch: Record<string, unknown>,
  _headers?: Record<string, string>,
) {
  return request<DeviceInfoRow>(
    `/api/v1/projects/${projectId}/proposal/chapters/2/device-info/${rowId}`,
    { method: 'PATCH', body: JSON.stringify(patch) },
  );
}

export async function parseDeviceBoq(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: DeviceInfoRow[] }>(
    `/api/v1/projects/${projectId}/proposal/parse/device-boq`,
    { method: 'POST' },
  );
}

export function deviceRowsNeedEnrichment(_rows: DeviceInfoRow[]): boolean {
  return false;
}

export async function enrichDeviceInfo(projectId: string, _headers?: Record<string, string>) {
  return request<{ rows: DeviceInfoRow[] }>(
    `/api/v1/projects/${projectId}/proposal/chapters/2/device-info/enrich`,
    { method: 'POST' },
  );
}
