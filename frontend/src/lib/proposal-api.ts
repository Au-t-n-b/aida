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

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
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
