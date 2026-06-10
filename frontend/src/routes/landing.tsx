// @ts-nocheck
/* /landing · 项目选择落地页（无 LeftNav / 无 ClawRail）
 * 这是会议规定的"登录后第一屏" — 只展示项目列表 + 创建按钮。
 * 真正的项目空间（带 LeftNav + ClawRail）从 /cockpit 开始。
 */

import LandingScreen from '@/components/screens/landing';

export default function LandingPage() {
  return <LandingScreen />;
}
