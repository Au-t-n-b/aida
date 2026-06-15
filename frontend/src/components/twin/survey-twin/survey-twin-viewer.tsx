import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  IconCheck,
  IconDownload,
  IconRefresh,
  IconSettings,
  IconUpload,
} from '@/components/icons';
import { agentBase } from '@/lib/runtimeBase';
import './survey-twin.css';

// 与 useSduiStream 同源：SOG 资产端点（/api/sog/*、/data/sog-assets/*）挂在 aida/agent 上。
const AGENT_BASE = agentBase();
// 必须用站点根路径：页面在 /twin/survey 时 ./sog-viewer 会错误解析为 /twin/sog-viewer（404）
const VIEWER_BASE = '/sog-viewer/index.html';

const STATUS_LABEL_DEFAULTS = {
  normal: '正常',
  abnormal: '异常',
} as const;

type HotspotMode = keyof typeof STATUS_LABEL_DEFAULTS;

type Hotspot = {
  id: string;
  title: string;
  text: string;
  mode: HotspotMode | 'abnormal' | 'normal';
  statusLabel: string;
  position: [number, number, number];
};

type SogScene = {
  id: string;
  name: string;
  status: 'ready' | 'training';
  uploadedAt: string;
  assetId?: string | null;
  sourceVideoName?: string;
  sceneExists?: boolean;
  contentUrl?: string;
  settingsUrl?: string;
  hotspotsUrl?: string;
};

type SogAsset = {
  id: string;
  contentUrl: string;
  settingsUrl: string;
  hotspotsUrl: string;
};

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const json = (await response.json().catch(() => ({}))) as { error?: string; detail?: string };
  if (!response.ok) {
    throw new Error(json.error || json.detail || '请求失败');
  }
  return json as T;
}

function sceneToAsset(scene: SogScene): SogAsset | null {
  const assetId = scene.assetId || scene.id;
  if (!assetId || scene.status !== 'ready') return null;
  return {
    id: assetId,
    contentUrl: scene.contentUrl
      ? `${AGENT_BASE}${scene.contentUrl}`
      : `${AGENT_BASE}/data/sog-assets/${assetId}/scene.sog`,
    settingsUrl: scene.settingsUrl
      ? `${AGENT_BASE}${scene.settingsUrl}`
      : `${AGENT_BASE}/api/sog/assets/${assetId}/settings`,
    hotspotsUrl: scene.hotspotsUrl
      ? `${AGENT_BASE}${scene.hotspotsUrl}`
      : `${AGENT_BASE}/api/sog/assets/${assetId}/hotspots`,
  };
}

function buildViewerUrl(asset: SogAsset, useWebgl: boolean) {
  const params = new URLSearchParams({
    lang: 'zh-CN',
    settings: asset.settingsUrl,
    content: asset.contentUrl,
    noanim: '1',
    v: String(Date.now()),
  });
  if (useWebgl) {
    params.set('webgl', '1');
  }
  return `${VIEWER_BASE}?${params.toString()}`;
}

function formatDate(value?: string) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function trainingProgress(uploadedAt: string, now: number) {
  const start = new Date(uploadedAt).getTime();
  if (!Number.isFinite(start)) return 0;
  const elapsedMs = Math.max(0, now - start);
  return Math.min(90, Math.floor(elapsedMs / (5 * 60 * 1000)));
}

function trainingCountdown(uploadedAt: string, now: number) {
  const start = new Date(uploadedAt).getTime();
  if (!Number.isFinite(start)) return '计算中';
  const target = start + 90 * 5 * 60 * 1000;
  const remainingMs = Math.max(0, target - now);
  if (remainingMs <= 0) return '即将完成';
  const totalSeconds = Math.ceil(remainingMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (hours > 0) return `${hours}小时 ${pad(minutes)}分 ${pad(seconds)}秒`;
  return `${minutes}分 ${pad(seconds)}秒`;
}

function chooseInitialScene(scenes: SogScene[]) {
  return scenes.find((scene) => scene.status === 'ready') || scenes[scenes.length - 1] || null;
}

export function SurveyTwinViewer() {
  const viewerFrameRef = useRef<HTMLIFrameElement>(null);
  const hotspotDialogRef = useRef<HTMLDialogElement>(null);
  const deleteSceneDialogRef = useRef<HTMLDialogElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadWatchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [scenes, setScenes] = useState<SogScene[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string>('');
  const [fileStatus, setFileStatus] = useState('正在加载场景列表…');
  const [currentHotspots, setCurrentHotspots] = useState<Hotspot[]>([]);
  const [pendingPosition, setPendingPosition] = useState<[number, number, number] | null>(null);
  const [editingHotspotId, setEditingHotspotId] = useState<string | null>(null);
  const [isHotspotEditing, setIsHotspotEditing] = useState(false);
  const [hotspotPanelCollapsed, setHotspotPanelCollapsed] = useState(false);
  const [useWebgl, setUseWebgl] = useState(
    () => localStorage.getItem('sog-viewer-renderer') === 'webgl',
  );
  const [dialogTitle, setDialogTitle] = useState('新增标签');
  const [hotspotTitle, setHotspotTitle] = useState('');
  const [hotspotText, setHotspotText] = useState('');
  const [hotspotMode, setHotspotMode] = useState<HotspotMode>('normal');
  const [hotspotStatusLabel, setHotspotStatusLabel] = useState<string>(STATUS_LABEL_DEFAULTS.normal);
  const [statusLabelAuto, setStatusLabelAuto] = useState(true);
  const [viewerSrc, setViewerSrc] = useState('');
  const [now, setNow] = useState(() => Date.now());
  const [isUploading, setIsUploading] = useState(false);
  const [editingSceneId, setEditingSceneId] = useState('');
  const [editingSceneName, setEditingSceneName] = useState('');
  const [scenePendingDelete, setScenePendingDelete] = useState<SogScene | null>(null);

  const selectedScene = useMemo(
    () => scenes.find((scene) => scene.id === selectedSceneId) || null,
    [scenes, selectedSceneId],
  );
  const currentAsset = useMemo(
    () => (selectedScene ? sceneToAsset(selectedScene) : null),
    [selectedScene],
  );

  const applyViewerSrc = useCallback((asset: SogAsset, webgl: boolean) => {
    const url = buildViewerUrl(asset, webgl);
    setViewerSrc(url);
    if (viewerFrameRef.current) {
      viewerFrameRef.current.src = url;
    }
  }, []);

  const syncHotspotsToViewer = useCallback((hotspots: Hotspot[]) => {
    const frame = viewerFrameRef.current;
    const targetWindow = frame?.contentWindow;
    if (!targetWindow) return;
    let targetOrigin = window.location.origin;
    try {
      targetOrigin = new URL(frame?.src || VIEWER_BASE, window.location.href).origin;
    } catch {
      targetOrigin = window.location.origin;
    }
    targetWindow.postMessage(
      {
        type: 'sog-hotspots:update',
        payload: { hotspots },
      },
      targetOrigin,
    );
  }, []);

  const watchViewerLoad = useCallback(
    (asset: SogAsset) => {
      if (loadWatchTimerRef.current) {
        clearTimeout(loadWatchTimerRef.current);
      }
      loadWatchTimerRef.current = setTimeout(() => {
        const frame = viewerFrameRef.current;
        if (!frame || asset.id !== currentAsset?.id || useWebgl) return;
        const text = frame.contentDocument?.getElementById('loadingText')?.textContent || '';
        const progress = Number.parseInt(text, 10);
        if (Number.isFinite(progress) && progress <= 2) {
          setUseWebgl(true);
          localStorage.setItem('sog-viewer-renderer', 'webgl');
          setFileStatus('加载停留时间较长，已切换到兼容模式重新加载');
          applyViewerSrc(asset, true);
        }
      }, 25000);
    },
    [applyViewerSrc, currentAsset?.id, useWebgl],
  );

  const loadSceneAsset = useCallback(
    async (scene: SogScene, asset: SogAsset) => {
      applyViewerSrc(asset, useWebgl);
      try {
        const hotspots = await requestJson<Hotspot[]>(asset.hotspotsUrl);
        setCurrentHotspots(hotspots);
        setFileStatus(`${scene.name}，已加载 ${hotspots.length} 个标签`);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (message.includes('scene.sog not found') || message.includes('404')) {
          setFileStatus('3D 场景文件未就绪，请确认历史场景文件已部署');
        } else if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
          setFileStatus('无法连接 Agent（7401），请确认后端已启动');
        } else {
          setFileStatus(`加载失败：${message}`);
        }
      }
      watchViewerLoad(asset);
    },
    [applyViewerSrc, useWebgl, watchViewerLoad],
  );

  const refreshScenes = useCallback(async (preferredId?: string) => {
    const list = await requestJson<SogScene[]>(`${AGENT_BASE}/api/sog/scenes`);
    setScenes(list);
    const next = preferredId
      ? list.find((scene) => scene.id === preferredId) || chooseInitialScene(list)
      : chooseInitialScene(list);
    setSelectedSceneId(next?.id || '');
    if (!next) setFileStatus('暂无 3D 场景');
  }, []);

  useEffect(() => {
    void refreshScenes().catch((error) => {
      const message = error instanceof Error ? error.message : String(error);
      setFileStatus(`场景列表加载失败：${message}`);
    });
    return () => {
      if (loadWatchTimerRef.current) {
        clearTimeout(loadWatchTimerRef.current);
      }
    };
  }, [refreshScenes]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedScene) return;
    setIsHotspotEditing(false);
    setHotspotPanelCollapsed(false);
    if (selectedScene.status === 'training') {
      setViewerSrc('');
      setCurrentHotspots([]);
      setFileStatus(`${selectedScene.name} 正在生成 3D 场景`);
      return;
    }
    const asset = sceneToAsset(selectedScene);
    if (!asset || !selectedScene.sceneExists) {
      setViewerSrc('');
      setCurrentHotspots([]);
      setFileStatus('3D 场景文件未就绪，请确认历史场景文件已部署');
      return;
    }
    void loadSceneAsset(selectedScene, asset);
  }, [loadSceneAsset, selectedScene]);

  useEffect(() => {
    if (selectedScene && currentAsset && selectedScene.status === 'ready' && selectedScene.sceneExists) {
      applyViewerSrc(currentAsset, useWebgl);
      watchViewerLoad(currentAsset);
    }
  }, [useWebgl, selectedScene, currentAsset, applyViewerSrc, watchViewerLoad]);

  const saveHotspots = useCallback(
    async (hotspots: Hotspot[]) => {
      if (!currentAsset) return;
      const saved = await requestJson<Hotspot[]>(currentAsset.hotspotsUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hotspots),
      });
      setCurrentHotspots(saved);
      syncHotspotsToViewer(saved);
    },
    [currentAsset, syncHotspotsToViewer],
  );

  useEffect(() => {
    const handleViewerMessage = (event: MessageEvent) => {
      if (event.source !== viewerFrameRef.current?.contentWindow) return;
      const data = event.data as { event?: string; payload?: Record<string, unknown>; type?: string } | null;
      if (data?.type === 'sog-viewer-probe') {
        void fetch(`${AGENT_BASE}/api/sog/probe-events`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: data.event || 'viewer.probe',
            payload: data.payload || {},
            sceneId: selectedScene?.id || null,
            assetId: currentAsset?.id || null,
            viewerSrc,
            pageStatus: fileStatus,
          }),
        }).catch(() => {});
      }
    };
    window.addEventListener('message', handleViewerMessage);
    return () => window.removeEventListener('message', handleViewerMessage);
  }, [currentAsset?.id, fileStatus, selectedScene?.id, viewerSrc]);

  const resetHotspotForm = ({
    title = '',
    text = '',
    mode = 'normal' as HotspotMode,
    statusLabel = STATUS_LABEL_DEFAULTS.normal as string,
  }: {
    title?: string;
    text?: string;
    mode?: HotspotMode;
    statusLabel?: string;
  } = {}) => {
    setHotspotTitle(title);
    setHotspotText(text);
    setHotspotMode(mode);
    const label = statusLabel || STATUS_LABEL_DEFAULTS[mode];
    setHotspotStatusLabel(label);
    setStatusLabelAuto(label === STATUS_LABEL_DEFAULTS[mode]);
  };

  const openEditDialog = (hotspot: Hotspot) => {
    setEditingHotspotId(hotspot.id);
    setPendingPosition(hotspot.position);
    setDialogTitle('编辑标签');
    resetHotspotForm({
      title: hotspot.title || '',
      text: hotspot.text || '',
      mode: hotspot.mode === 'abnormal' ? 'abnormal' : 'normal',
      statusLabel: hotspot.statusLabel,
    });
    hotspotDialogRef.current?.showModal();
  };

  const handlePick = async (event: React.MouseEvent<HTMLDivElement>) => {
    if (!currentAsset) return;
    const frame = viewerFrameRef.current;
    const viewer = (frame?.contentWindow as { sse?: { viewer?: { picker?: { pick: (x: number, y: number) => Promise<{ x: number; y: number; z: number } | null> } } } } | null)?.sse?.viewer;
    if (!viewer?.picker || !frame) {
      setFileStatus('场景尚未准备好，请稍后再设置标签');
      return;
    }
    const rect = frame.getBoundingClientRect();
    const pickX = (event.clientX - rect.left) / rect.width;
    const pickY = (event.clientY - rect.top) / rect.height;
    const position = await viewer.picker.pick(pickX, pickY);
    if (!position) {
      setFileStatus('没有拾取到场景表面，请换一个位置点击');
      return;
    }
    setPendingPosition([position.x, position.y, position.z]);
    setEditingHotspotId(null);
    setDialogTitle('新增标签');
    resetHotspotForm();
    hotspotDialogRef.current?.showModal();
  };

  const handleSubmitHotspot = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!currentAsset || !pendingPosition) return;
    const hotspot: Hotspot = {
      id: editingHotspotId || `hotspot-${Date.now()}`,
      title: hotspotTitle,
      text: hotspotText,
      mode: hotspotMode === 'abnormal' ? 'abnormal' : 'normal',
      statusLabel: hotspotStatusLabel.trim() || STATUS_LABEL_DEFAULTS[hotspotMode],
      position: pendingPosition,
    };
    const wasEditing = Boolean(editingHotspotId);
    const nextHotspots = wasEditing
      ? currentHotspots.map((item) => (item.id === editingHotspotId ? { ...item, ...hotspot } : item))
      : [...currentHotspots, hotspot];
    await saveHotspots(nextHotspots);
    hotspotDialogRef.current?.close();
    setPendingPosition(null);
    setEditingHotspotId(null);
    setFileStatus(
      wasEditing
        ? `标签已更新，当前共有 ${nextHotspots.length} 个标签`
        : `标签已保存，当前共有 ${nextHotspots.length} 个标签`,
    );
  };

  const deleteHotspot = async (hotspotId: string) => {
    const next = currentHotspots.filter((item) => item.id !== hotspotId);
    await saveHotspots(next);
    setFileStatus(`标签已删除，当前共有 ${next.length} 个标签`);
  };

  const handleUpload = async (file: File | null | undefined) => {
    if (!file) return;
    setIsUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const scene = await requestJson<SogScene>(`${AGENT_BASE}/api/sog/scenes/upload`, {
        method: 'POST',
        body: form,
      });
      await refreshScenes(scene.id);
      setFileStatus(`${scene.name} 正在生成 3D 场景`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFileStatus(`上传失败：${message}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const beginSceneRename = (scene: SogScene) => {
    setEditingSceneId(scene.id);
    setEditingSceneName(scene.name);
  };

  const cancelSceneRename = () => {
    setEditingSceneId('');
    setEditingSceneName('');
  };

  const saveSceneName = async (scene: SogScene) => {
    const name = editingSceneName.trim();
    if (!name) {
      setFileStatus('场景名称不能为空');
      return;
    }
    try {
      const updated = await requestJson<SogScene>(`${AGENT_BASE}/api/sog/scenes/${scene.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      setScenes((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setFileStatus(`已重命名为 ${updated.name}`);
      cancelSceneRename();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFileStatus(`重命名失败：${message}`);
    }
  };

  const openDeleteSceneDialog = (scene: SogScene) => {
    setScenePendingDelete(scene);
    deleteSceneDialogRef.current?.showModal();
  };

  const closeDeleteSceneDialog = () => {
    setScenePendingDelete(null);
    deleteSceneDialogRef.current?.close();
  };

  const deleteScene = async () => {
    if (!scenePendingDelete) return;
    try {
      await requestJson<{ deleted: boolean }>(`${AGENT_BASE}/api/sog/scenes/${scenePendingDelete.id}`, {
        method: 'DELETE',
      });
      const remainingScenes = scenes.filter((scene) => scene.id !== scenePendingDelete.id);
      setScenes(remainingScenes);
      if (scenePendingDelete.id === selectedSceneId) {
        const next = chooseInitialScene(remainingScenes);
        setSelectedSceneId(next?.id || '');
        if (!next) {
          setViewerSrc('');
          setCurrentHotspots([]);
          setFileStatus('暂无 3D 场景');
        }
      }
      setFileStatus(`已删除场景 ${scenePendingDelete.name}`);
      closeDeleteSceneDialog();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setFileStatus(`删除失败：${message}`);
    }
  };

  const selectedProgress = selectedScene?.status === 'training'
    ? trainingProgress(selectedScene.uploadedAt, now)
    : 0;
  const selectedCountdown = selectedScene?.status === 'training'
    ? trainingCountdown(selectedScene.uploadedAt, now)
    : '';

  return (
    <div className="st-root">
      <aside className="st-sidebar" aria-label="实景孪生场景列表">
        <div className="st-sidebarHead">
          <div>
            <h1>实景孪生</h1>
            <p>视频建模与 3D 场景浏览</p>
          </div>
          <button
            type="button"
            className="st-iconButton"
            title="刷新场景"
            onClick={() => void refreshScenes(selectedSceneId)}
          >
            <IconRefresh size={15} />
          </button>
        </div>

        <input
          ref={fileInputRef}
          className="st-fileInput"
          type="file"
          accept="video/*"
          onChange={(event) => void handleUpload(event.currentTarget.files?.[0])}
        />
        <button
          type="button"
          className="st-uploadButton"
          disabled={isUploading}
          onClick={() => fileInputRef.current?.click()}
        >
          <IconUpload size={15} />
          {isUploading ? '上传中' : '上传视频'}
        </button>

        <div className="st-sceneList">
          {scenes.length === 0 ? (
            <p className="st-emptyText">暂无 3D 场景</p>
          ) : (
            scenes.map((scene) => {
              const isEditing = editingSceneId === scene.id;
              return (
                <article
                  key={scene.id}
                  className={`st-sceneItem ${scene.id === selectedSceneId ? 'is-active' : ''}`}
                >
                  <div
                    role="button"
                    tabIndex={0}
                    className="st-sceneSelect"
                    onClick={() => setSelectedSceneId(scene.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelectedSceneId(scene.id);
                      }
                    }}
                  >
                    {isEditing ? (
                      <input
                        className="st-sceneNameInput"
                        value={editingSceneName}
                        autoFocus
                        maxLength={40}
                        onClick={(event) => event.stopPropagation()}
                        onChange={(event) => setEditingSceneName(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            void saveSceneName(scene);
                          }
                          if (event.key === 'Escape') {
                            event.preventDefault();
                            cancelSceneRename();
                          }
                        }}
                      />
                    ) : (
                      <span className="st-sceneNameRow">
                        <span className="st-sceneName">{scene.name}</span>
                        <span className="st-sceneInlineActions">
                          <button
                            type="button"
                            className="st-sceneIconAction"
                            title="修改场景名"
                            aria-label={`修改场景名：${scene.name}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              beginSceneRename(scene);
                            }}
                          >
                            <svg viewBox="0 0 16 16" aria-hidden="true">
                              <path d="M10.9 2.1 13.9 5.1 5.7 13.3 2.4 14 3.1 10.7 10.9 2.1Z" />
                              <path d="M9.8 3.2 12.8 6.2" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            className="st-sceneIconAction st-deleteSceneAction"
                            title="删除场景"
                            aria-label={`删除场景：${scene.name}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              openDeleteSceneDialog(scene);
                            }}
                          >
                            <svg viewBox="0 0 16 16" aria-hidden="true">
                              <path d="M5.5 2.5h5l.6 1.4H14" />
                              <path d="M2.5 3.9h11" />
                              <path d="M4 5.2 4.6 14h6.8l.6-8.8" />
                              <path d="M6.7 7.1v4.7M9.3 7.1v4.7" />
                            </svg>
                          </button>
                        </span>
                      </span>
                    )}
                    <span className="st-sceneMeta">{formatDate(scene.uploadedAt)}</span>
                  </div>
                  <div className="st-sceneSide">
                    <span className={`st-statusTag ${scene.status === 'ready' ? 'is-ready' : 'is-training'}`}>
                      {scene.status === 'ready' ? '已完成' : '训练中'}
                    </span>
                    {isEditing ? (
                      <span className="st-sceneEditActions">
                        <button type="button" onClick={() => void saveSceneName(scene)}>保存</button>
                        <button type="button" onClick={cancelSceneRename}>取消</button>
                      </span>
                    ) : null}
                  </div>
                </article>
              );
            })
          )}
        </div>
      </aside>

      <main className="st-main">
        <section className="st-topbar" aria-label="实景孪生状态栏">
          <div className="st-titleBlock">
            <h2>{selectedScene?.name || '实景孪生'}</h2>
            <p>{fileStatus}</p>
          </div>
          {selectedScene?.status === 'ready' && selectedScene.sceneExists && currentAsset && (
            <div className="st-actions">
              <button
                type="button"
                className={`st-button ${!isHotspotEditing ? 'st-active' : ''}`}
                aria-pressed={!isHotspotEditing}
                onClick={() => setIsHotspotEditing(false)}
              >
                浏览
              </button>
              <button
                type="button"
                className={`st-button ${isHotspotEditing ? 'st-active' : ''}`}
                aria-pressed={isHotspotEditing}
                onClick={() => setIsHotspotEditing(true)}
              >
                <IconSettings size={14} />
                标签
              </button>
              <button
                type="button"
                className="st-button"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(currentHotspots, null, 2)], {
                    type: 'application/json',
                  });
                  const url = URL.createObjectURL(blob);
                  const link = document.createElement('a');
                  link.href = url;
                  link.download = `${currentAsset.id}-hotspots.json`;
                  link.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <IconDownload size={14} />
                导出
              </button>
              <button
                type="button"
                className={`st-button ${useWebgl ? 'st-active' : ''}`}
                onClick={() => {
                  const next = !useWebgl;
                  setUseWebgl(next);
                  localStorage.setItem('sog-viewer-renderer', next ? 'webgl' : 'webgpu');
                  setFileStatus(next ? '已切换到兼容模式，正在重新加载' : '已切换到默认模式，正在重新加载');
                }}
              >
                兼容模式
              </button>
              <button
                type="button"
                className="st-button"
                onClick={async () => {
                  if (viewerFrameRef.current?.requestFullscreen) {
                    await viewerFrameRef.current.requestFullscreen();
                  }
                }}
              >
                全屏
              </button>
            </div>
          )}
        </section>

        <section className="st-viewerShell" aria-label="三维预览区">
          {selectedScene?.status === 'training' ? (
            <div className="st-trainingShell">
              <div className="st-trainingCard">
                <div className="st-trainingIcon">
                  <IconRefresh size={22} />
                </div>
                <h2>3D 场景生成中</h2>
                <p>视频已上传，系统正在生成 3D 场景，请稍后查看。</p>
                <div className="st-progressTrack" aria-label={`训练进度 ${selectedProgress}%`}>
                  <div className="st-progressFill" style={{ width: `${selectedProgress}%` }} />
                </div>
                <div className="st-trainingMeta">
                  <span>进度 {selectedProgress}%</span>
                  <span>预计剩余 {selectedCountdown}</span>
                  <span>上传时间 {formatDate(selectedScene.uploadedAt)}</span>
                  <span className="st-statusTag is-training">训练中</span>
                </div>
              </div>
            </div>
          ) : selectedScene && selectedScene.sceneExists && viewerSrc ? (
            <>
              <iframe
                ref={viewerFrameRef}
                title="实景孪生三维预览"
                allow="fullscreen; xr-spatial-tracking; pointer-lock"
                src={viewerSrc}
              />
              {isHotspotEditing && (
                <div className="st-pickLayer" onClick={(event) => void handlePick(event)}>
                  <div className="st-pickHint">点击场景中的物体位置创建标签</div>
                </div>
              )}
              {isHotspotEditing && !hotspotPanelCollapsed && (
                <aside className="st-hotspotPanel" aria-label="标签编辑面板">
                  <div className="st-panelHeader">
                    <h2>标签列表</h2>
                    <span>{currentHotspots.length} 个</span>
                    <button
                      type="button"
                      className="st-panelIconButton"
                      onClick={() => setHotspotPanelCollapsed(true)}
                    >
                      收起
                    </button>
                  </div>
                  <div className="st-hotspotList">
                    {currentHotspots.length === 0 ? (
                      <p className="st-emptyText">还没有标签。点击场景中的位置可新增。</p>
                    ) : (
                      currentHotspots.map((hotspot, index) => (
                        <article key={hotspot.id} className="st-hotspotItem">
                          <div className="st-hotspotItemText">
                            <strong>{hotspot.title || `标签 ${index + 1}`}</strong>
                            <span
                              className={`st-hotspotStatus ${
                                hotspot.mode === 'abnormal' ? 'st-abnormal' : 'st-normal'
                              }`}
                            >
                              {hotspot.statusLabel || STATUS_LABEL_DEFAULTS[hotspot.mode === 'abnormal' ? 'abnormal' : 'normal']}
                            </span>
                            <span>{hotspot.text || '无说明'}</span>
                          </div>
                          <div className="st-hotspotItemActions">
                            <button
                              type="button"
                              className="st-editHotspotButton"
                              onClick={() => openEditDialog(hotspot)}
                            >
                              编辑
                            </button>
                            <button
                              type="button"
                              className="st-deleteHotspotButton"
                              onClick={() => void deleteHotspot(hotspot.id)}
                            >
                              删除
                            </button>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                </aside>
              )}
              {isHotspotEditing && hotspotPanelCollapsed && (
                <button
                  type="button"
                  className="st-expandHotspotPanel"
                  onClick={() => setHotspotPanelCollapsed(false)}
                >
                  展开标签列表
                </button>
              )}
            </>
          ) : (
            <div className="st-emptyViewer">
              <div className="st-emptyViewerCard">
                <IconCheck size={22} />
                <h2>3D 场景文件未就绪</h2>
                <p>请选择已完成的场景，或确认历史 3D 场景文件已经部署。</p>
              </div>
            </div>
          )}
        </section>
      </main>

      <dialog ref={hotspotDialogRef} className="st-hotspotDialog">
        <form onSubmit={(event) => void handleSubmitHotspot(event)}>
          <h2>{dialogTitle}</h2>
          <label>
            <span>标题</span>
            <input
              value={hotspotTitle}
              maxLength={40}
              placeholder="卡片标题"
              required
              onChange={(event) => setHotspotTitle(event.target.value)}
            />
          </label>
          <label>
            <span>说明</span>
            <textarea
              value={hotspotText}
              maxLength={120}
              rows={3}
              placeholder="卡片内容"
              onChange={(event) => setHotspotText(event.target.value)}
            />
          </label>
          <div className="st-statusFields">
            <label>
              <span>状态</span>
              <select
                value={hotspotMode}
                onChange={(event) => {
                  const mode = event.target.value as HotspotMode;
                  setHotspotMode(mode);
                  if (statusLabelAuto) {
                    setHotspotStatusLabel(STATUS_LABEL_DEFAULTS[mode]);
                  }
                }}
              >
                <option value="normal">正常</option>
                <option value="abnormal">异常</option>
              </select>
            </label>
            <label>
              <span>状态标签</span>
              <input
                value={hotspotStatusLabel}
                maxLength={20}
                onChange={(event) => {
                  setHotspotStatusLabel(event.target.value);
                  setStatusLabelAuto(false);
                }}
              />
            </label>
          </div>
          <div className="st-dialogActions">
            <button
              type="button"
              className="st-button"
              onClick={() => {
                setPendingPosition(null);
                setEditingHotspotId(null);
                hotspotDialogRef.current?.close();
              }}
            >
              取消
            </button>
            <button type="submit" className="st-button st-active">
              保存标签
            </button>
          </div>
        </form>
      </dialog>
      <dialog ref={deleteSceneDialogRef} className="st-hotspotDialog st-confirmDialog">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void deleteScene();
          }}
        >
          <h2>删除场景</h2>
          <p className="st-confirmWarning">
            确认删除「{scenePendingDelete?.name || '该场景'}」吗？删除后无法恢复。
          </p>
          <div className="st-dialogActions">
            <button type="button" className="st-button" onClick={closeDeleteSceneDialog}>
              取消
            </button>
            <button type="submit" className="st-button st-dangerButton">
              确认删除
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
