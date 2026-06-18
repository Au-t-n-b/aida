import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { readScheduleUploadPersistenceMode, shouldPersistUploadedScheduleChanges } from '@/features/schedule/config/schedule-stage';
import { ensureScheduleBaseline, loadProjectData } from '@/features/schedule/services/schedule';
import { INITIAL_BATCHES, INITIAL_ROOMS, INITIAL_TEAMS, type BatchRow, type RoomRow, type TeamRow } from './plan-board/data/plan';
import { PlanBoard, type PlanBoardInitialData, type PlanBoardMode } from './plan-board/plan-board';

type BatchStage = {
  batchId: string;
  stage: PlanBoardMode;
  missingRoomReady: string[];
  missingArrival: string[];
};

type StageResolution = {
  mode: PlanBoardMode;
  data: PlanBoardInitialData;
  dataSource: 'api' | 'mock';
  batchStages: BatchStage[];
  mountKey: string;
};

function cloneRows<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function hasRoomReady(room: RoomRow): boolean {
  return Boolean(room.cableReadyAt || room.equipReadyAt || room.liquidReadyAt);
}

function batchStagesFor(batches: BatchRow[], rooms: RoomRow[]): BatchStage[] {
  const podToRoom = new Map<string, RoomRow>();
  rooms.forEach((room) => room.pods.forEach((pod) => podToRoom.set(pod.id, room)));

  return batches.map((batch) => {
    const roomIds = new Set<string>();
    const missingArrival: string[] = [];

    batch.podIds.forEach((podId) => {
      const room = podToRoom.get(podId);
      if (!room) {
        missingArrival.push(podId);
        return;
      }
      roomIds.add(room.code);
      const pod = room.pods.find((item) => item.id === podId);
      if (!pod || pod.arrival === 'unknown') missingArrival.push(podId);
    });

    const missingRoomReady = Array.from(roomIds).filter((roomId) => {
      const room = rooms.find((item) => item.code === roomId);
      return !room || !hasRoomReady(room);
    });

    return {
      batchId: batch.id,
      stage: missingRoomReady.length || missingArrival.length ? 'init' : 'adjust',
      missingRoomReady,
      missingArrival,
    };
  });
}

function resolveMode(batchStages: BatchStage[], baselineReady: boolean): PlanBoardMode {
  if (batchStages.some((batch) => batch.stage === 'init')) return 'init';
  return baselineReady ? 'adjust' : 'init';
}

function hasInitStage(batchStages: BatchStage[]): boolean {
  return batchStages.some((batch) => batch.stage === 'init');
}

function mountKeyFor(legacyStage: PlanBoardMode | undefined, dataSource: StageResolution['dataSource']): string {
  return `loaded:${legacyStage ?? 'auto'}:${dataSource}`;
}

function mockScheduleData(): PlanBoardInitialData {
  return {
    rooms: cloneRows(INITIAL_ROOMS),
    batches: cloneRows(INITIAL_BATCHES),
    teams: cloneRows(INITIAL_TEAMS),
  };
}

function mockInitScheduleData(): PlanBoardInitialData {
  const data = mockScheduleData();
  return {
    ...data,
    rooms: data.rooms.map((room) => ({
      ...room,
      site: 'pending',
      readyUnknown: true,
      cableReadyAt: undefined,
      equipReadyAt: undefined,
      liquidReadyAt: undefined,
      pods: room.pods.map((pod) => ({
        ...pod,
        arrival: 'unknown',
        etaLabel: '待定',
        etaDate: undefined,
        status: 'pending',
      })),
    })),
  };
}

export default function PlanScheduleScreen({ legacyStage }: { legacyStage?: PlanBoardMode }) {
  const [resolution, setResolution] = useState<StageResolution | null>(null);
  const runtimeStageSeq = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const projectResult = await loadProjectData({ signal: controller.signal });
      if (controller.signal.aborted) return;

      const data = projectResult.source === 'api'
        ? projectResult.data
        : legacyStage === 'init'
          ? mockInitScheduleData()
          : mockScheduleData();
      const dataSource = projectResult.source === 'api' ? 'api' : 'mock';
      const batchStages = batchStagesFor(data.batches, data.rooms);
      const needsInit = hasInitStage(batchStages);
      let baselineReady = (dataSource === 'mock' && !needsInit) || legacyStage === 'adjust';

      if (!needsInit && dataSource === 'api') {
        const baseline = await ensureScheduleBaseline(data);
        if (controller.signal.aborted) return;
        baselineReady = baseline.source === 'api';
      }

      const mode = legacyStage ?? resolveMode(batchStages, baselineReady);
      console.info('[T-022] /plan stage resolved', { mode, legacy_stage: legacyStage, data_source: dataSource, baseline_ready: baselineReady, batch_stages: batchStages });
      setResolution({ mode, data, dataSource, batchStages, mountKey: mountKeyFor(legacyStage, dataSource) });
    })();

    return () => controller.abort();
  }, [legacyStage]);

  const handleRuntimeDataChange = useCallback(async (data: PlanBoardInitialData, reason: 'upload') => {
    const seq = ++runtimeStageSeq.current;
    const dataSource = resolution?.dataSource ?? 'mock';
    const persistenceMode = readScheduleUploadPersistenceMode();
    const persistRequested = shouldPersistUploadedScheduleChanges(persistenceMode);
    const batchStages = batchStagesFor(data.batches, data.rooms);
    const needsInit = hasInitStage(batchStages);
    let baselineReady = dataSource === 'mock' && !needsInit;
    let baselineSource: 'api' | 'mock' | 'skipped' = needsInit ? 'skipped' : dataSource === 'mock' ? 'mock' : 'skipped';

    if (persistRequested) {
      console.info('[T-053] PROD upload persistence selected; persistent write is reserved for T-054', { reason });
    }

    if (!needsInit && dataSource === 'api') {
      const baseline = await ensureScheduleBaseline(data);
      if (runtimeStageSeq.current !== seq) return;
      baselineReady = baseline.source === 'api';
      baselineSource = baseline.source;
    }

    const mode = legacyStage ?? resolveMode(batchStages, baselineReady);
    console.info('[T-053] /plan runtime stage resolved', {
      mode,
      reason,
      legacy_stage: legacyStage,
      data_source: dataSource,
      upload_persistence_mode: persistenceMode,
      baseline_ready: baselineReady,
      baseline_source: baselineSource,
      batch_stages: batchStages,
    });
    setResolution(prev => ({
      mode,
      data,
      dataSource,
      batchStages,
      mountKey: prev?.mountKey ?? mountKeyFor(legacyStage, dataSource),
    }));
  }, [legacyStage, resolution?.dataSource]);

  const boardKey = useMemo(() => {
    return resolution?.mountKey ?? 'loading';
  }, [resolution?.mountKey]);

  if (!resolution) {
    return <PlanBoard key={boardKey} mode="init" />;
  }

  return <PlanBoard key={boardKey} mode={resolution.mode} initialData={resolution.data} onRuntimeDataChange={handleRuntimeDataChange} />;
}
