import { AdminShell } from '@/components/admin-shell';
import EvalsScreen from '@/components/screens/evals';
import { TweaksProvider } from '@/lib/tweaks-context';

export default function EvalsPage() {
  return (
    <TweaksProvider>
      <AdminShell>
        <EvalsScreen />
      </AdminShell>
    </TweaksProvider>
  );
}
