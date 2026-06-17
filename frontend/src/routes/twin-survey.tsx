import { SurveyTwinViewer } from '@/components/twin/survey-twin/survey-twin-viewer';

/** 实景孪生独立页（源自物理孪生的实景孪生 tab）· 孪生世界下与算力底座孪生 / 项目孪生平级 */
export default function TwinSurveyPage() {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <SurveyTwinViewer />
    </div>
  );
}
