export type ScheduleUploadPersistenceMode = 'demo' | 'prod';

const PROD_MODE = 'prod';
const STORAGE_KEY = 'aida_schedule_upload_persistence';

function normalizeMode(value: string | null | undefined): ScheduleUploadPersistenceMode {
  return value?.toLowerCase() === PROD_MODE ? 'prod' : 'demo';
}

export function readScheduleUploadPersistenceMode(): ScheduleUploadPersistenceMode {
  const envMode = normalizeMode(import.meta.env.VITE_SCHEDULE_UPLOAD_PERSISTENCE);
  if (envMode === 'prod') return envMode;
  if (typeof window === 'undefined') return envMode;
  try {
    return normalizeMode(window.localStorage?.getItem(STORAGE_KEY));
  } catch (error) {
    console.warn('[T-053] failed to read schedule upload persistence mode', error);
    return envMode;
  }
}

export function shouldPersistUploadedScheduleChanges(mode = readScheduleUploadPersistenceMode()): boolean {
  return mode === 'prod';
}
