// @ts-nocheck
import { AdminShell } from '@/components/admin-shell';
import AdminScreen from '@/components/screens/admin';
import { TweaksProvider } from '@/lib/tweaks-context';

/* G-1 · 管理员后台与项目空间分离：
 * 这里使用专属 AdminShell（无业务左导 / 无 ClawRail / 无项目下拉），
 * 和 /cockpit /preview /proposal /plan /design 等项目空间页面在视觉与导航上完全隔离。
 */
export default function AdminPage() {
  return (
    <TweaksProvider>
      <AdminShell>
        <AdminScreen />
      </AdminShell>
    </TweaksProvider>
  );
}
