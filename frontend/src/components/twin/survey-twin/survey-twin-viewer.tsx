import { useCallback, useEffect, useRef, useState } from 'react';
import './survey-twin.css';

// 与 useSduiStream 同源：SOG 资产端点（/api/sog/*、/data/sog-assets/*）挂在 aida/agent 上。
const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';
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

type SogAsset = {
  id: string;
  contentUrl: string;
  settingsUrl: string;
  hotspotsUrl: string;
};

const CHANNEL1_ASSET: SogAsset = {
  id: 'channel1',
  contentUrl: `${AGENT_BASE}/data/sog-assets/channel1/scene.sog`,
  settingsUrl: `${AGENT_BASE}/api/sog/assets/channel1/settings`,
  hotspotsUrl: `${AGENT_BASE}/api/sog/assets/channel1/hotspots`,
};

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const json = (await response.json().catch(() => ({}))) as { error?: string; detail?: string };
  if (!response.ok) {
    throw new Error(json.error || json.detail || '请求失败');
  }
  return json as T;
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

export function SurveyTwinViewer() {
  const viewerFrameRef = useRef<HTMLIFrameElement>(null);
  const hotspotDialogRef = useRef<HTMLDialogElement>(null);
  const loadWatchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [fileStatus, setFileStatus] = useState('正在加载通道1.sog…');
  const [currentAsset, setCurrentAsset] = useState<SogAsset | null>(null);
  const [currentHotspots, setCurrentHotspots] = useState<Hotspot[]>([]);
  const [pendingPosition, setPendingPosition] = useState<[number, number, number] | null>(null);
  const [editingHotspotId, setEditingHotspotId] = useState<string | null>(null);
  const [isHotspotEditing, setIsHotspotEditing] = useState(false);
  const [hotspotPanelCollapsed, setHotspotPanelCollapsed] = useState(false);
  const [useWebgl, setUseWebgl] = useState(
    () => localStorage.getItem('sog-viewer-renderer') === 'webgl',
  );
  const [dialogTitle, setDialogTitle] = useState('新增热点');
  const [hotspotTitle, setHotspotTitle] = useState('');
  const [hotspotText, setHotspotText] = useState('');
  const [hotspotMode, setHotspotMode] = useState<HotspotMode>('normal');
  const [hotspotStatusLabel, setHotspotStatusLabel] = useState<string>(STATUS_LABEL_DEFAULTS.normal);
  const [statusLabelAuto, setStatusLabelAuto] = useState(true);

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
          setViewerSrc(buildViewerUrl(asset, true));
          frame.src = buildViewerUrl(asset, true);
        }
      }, 25000);
    },
    [currentAsset?.id, useWebgl],
  );

  const [viewerSrc, setViewerSrc] = useState(() => buildViewerUrl(CHANNEL1_ASSET, useWebgl));

  const applyViewerSrc = useCallback(
    (asset: SogAsset, webgl: boolean) => {
      const url = buildViewerUrl(asset, webgl);
      setViewerSrc(url);
      if (viewerFrameRef.current) {
        viewerFrameRef.current.src = url;
      }
    },
    [],
  );

  const loadAsset = useCallback(
    async (asset: SogAsset, label: string) => {
      setCurrentAsset(asset);
      applyViewerSrc(asset, useWebgl);
      try {
        const hotspots = await requestJson<Hotspot[]>(asset.hotspotsUrl);
        setCurrentHotspots(hotspots);
        setFileStatus(`${label}，已加载 ${hotspots.length} 个热点`);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (message.includes('scene.sog not found') || message.includes('404')) {
          setFileStatus('缺少 data/sog-assets/channel1/scene.sog，请按安装手册部署通道1文件');
        } else if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
          setFileStatus('无法连接 Agent（7401），请确认后端已启动');
        } else {
          setFileStatus(`加载失败：${message}`);
        }
      }
      watchViewerLoad(asset);
    },
    [useWebgl, watchViewerLoad, applyViewerSrc],
  );

  const saveHotspots = useCallback(
    async (hotspots: Hotspot[]) => {
      if (!currentAsset) return;
      const saved = await requestJson<Hotspot[]>(currentAsset.hotspotsUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hotspots),
      });
      setCurrentHotspots(saved);
      applyViewerSrc(currentAsset, useWebgl);
      watchViewerLoad(currentAsset);
    },
    [currentAsset, useWebgl, watchViewerLoad, applyViewerSrc],
  );

  useEffect(() => {
    void loadAsset(CHANNEL1_ASSET, '正在浏览预置文件：通道1.sog');
    return () => {
      if (loadWatchTimerRef.current) {
        clearTimeout(loadWatchTimerRef.current);
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (currentAsset) {
      applyViewerSrc(currentAsset, useWebgl);
      watchViewerLoad(currentAsset);
    }
  }, [useWebgl, currentAsset, applyViewerSrc, watchViewerLoad]);

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
    setDialogTitle('编辑热点');
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
      setFileStatus('场景尚未准备好，请稍后再设置热点');
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
    setDialogTitle('新增热点');
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
        ? `热点已更新，当前共有 ${nextHotspots.length} 个热点`
        : `热点已保存，当前共有 ${nextHotspots.length} 个热点`,
    );
  };

  const deleteHotspot = async (hotspotId: string) => {
    const next = currentHotspots.filter((item) => item.id !== hotspotId);
    await saveHotspots(next);
    setFileStatus(`热点已删除，当前共有 ${next.length} 个热点`);
  };

  return (
    <div className="st-root">
      <section className="st-toolbar" aria-label="工勘孪生工具栏">
        <div className="st-titleBlock">
          <h1>工勘孪生</h1>
          <p>{fileStatus}</p>
        </div>
        <div className="st-actions">
          <button
            type="button"
            className={`st-button ${!isHotspotEditing ? 'st-active' : ''}`}
            aria-pressed={!isHotspotEditing}
            onClick={() => setIsHotspotEditing(false)}
          >
            浏览模式
          </button>
          <button
            type="button"
            className={`st-button ${isHotspotEditing ? 'st-active' : ''}`}
            aria-pressed={isHotspotEditing}
            onClick={() => setIsHotspotEditing(true)}
          >
            编辑热点模式
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
              link.download = currentAsset ? `${currentAsset.id}-hotspots.json` : 'hotspots.json';
              link.click();
              URL.revokeObjectURL(url);
            }}
          >
            导出热点
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
            {useWebgl ? '兼容模式：开' : '兼容模式：关'}
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
            全屏查看
          </button>
        </div>
      </section>

      <section className="st-viewerShell" aria-label="三维预览区">
        <iframe
          ref={viewerFrameRef}
          title="工勘孪生三维预览"
          allow="fullscreen; xr-spatial-tracking; pointer-lock"
          src={viewerSrc}
        />
        {isHotspotEditing && (
          <div className="st-pickLayer" onClick={(event) => void handlePick(event)}>
            <div className="st-pickHint">点击场景中的物体位置创建热点</div>
          </div>
        )}
        {isHotspotEditing && !hotspotPanelCollapsed && (
          <aside className="st-hotspotPanel" aria-label="热点编辑面板">
            <div className="st-panelHeader">
              <h2>热点列表</h2>
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
                <p className="st-emptyText">还没有热点。点击场景中的位置可新增。</p>
              ) : (
                currentHotspots.map((hotspot, index) => (
                  <article key={hotspot.id} className="st-hotspotItem">
                    <div className="st-hotspotItemText">
                      <strong>{hotspot.title || `热点 ${index + 1}`}</strong>
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
            展开热点列表
          </button>
        )}
      </section>

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
              保存热点
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
