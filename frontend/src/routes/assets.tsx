// @ts-nocheck
import { AppShell } from '@/components/app-shell';
import { AssetsScreen } from '@/components/screens/system';
import { TweaksProvider } from '@/lib/tweaks-context';

export default function AssetsPage() {
  return (
    <TweaksProvider>
      <AppShell breadcrumbs={['资产中心']}>
        <AssetsScreen />
      </AppShell>
    </TweaksProvider>
  );
}
