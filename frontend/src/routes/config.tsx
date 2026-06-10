// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import { ConfigScreen } from '@/components/screens/system';
import { TweaksProvider } from '@/lib/tweaks-context';

export default function ConfigPage() {
  return (
    <TweaksProvider>
      <AppShell breadcrumbs={['配置中心']}>
        <ConfigScreen />
      </AppShell>
    </TweaksProvider>
  );
}
