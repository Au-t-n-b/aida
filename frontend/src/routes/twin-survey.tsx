import { SurveyTwinViewer } from '@/components/twin/survey-twin/survey-twin-viewer';

export default function TwinSurveyPage() {
  return (
    <div
      data-twin-survey="1"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
    >
      <SurveyTwinViewer />
    </div>
  );
}
