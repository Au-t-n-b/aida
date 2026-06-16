import { TwinPhysicalPanel } from '@/components/twin/twin-world';

export default function TwinPhysicalPage() {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <TwinPhysicalPanel />
    </div>
  );
}
