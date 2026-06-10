import { useParams } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import ModuleRoute from '@/components/module-route';
import SkillAgentScreen from '@/components/screens/survey-agent';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';
import { MODULE_SCHEMAS } from '@/data/modules-data';

/* 前端模块 key → 后端 skill_id：已注册后端 skill 的模块走 SDUI 通用作业界面 */
const MODULE_TO_SKILL: Record<string, string> = {
  survey: 'zhgk',
  modeling: 'guihua',
  design: 'xtsj',    // 系统设计（a3 智能网络开局）· dispatch 模式 PoC
  install: 'device_install',
};

function ModuleInner({ moduleKey }: { moduleKey: string }) {
  const { tweaks, setTweak } = useTweaks();
  const schema = MODULE_SCHEMAS[moduleKey as keyof typeof MODULE_SCHEMAS];
  const name = schema?.name || moduleKey;
  const skillId = MODULE_TO_SKILL[moduleKey];

  /* 有后端 skill 的模块走 LangGraph Agent 工作台（SDUI 通用界面）；其它沿用 mock ModuleRoute */
  if (skillId) {
    return (
      <AppShell
        breadcrumbs={['交付作业', name]}
        withClaw
        clawRail={
          <ClawRail
            collapsed={tweaks.clawCollapsed}
            onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
            width={tweaks.clawWidth}
            onResize={(w: number) => setTweak('clawWidth', w)}
          />
        }
      >
        <SkillAgentScreen skillId={skillId} title={name} description={schema?.subtitle} />
      </AppShell>
    );
  }

  return (
    <AppShell breadcrumbs={['交付模块', name]}>
      <ModuleRoute moduleKey={moduleKey} />
    </AppShell>
  );
}

export default function ModuleRoutePage() {
  const { key: rawKey } = useParams();
  const key = rawKey ?? 'survey';

  return (
    <TweaksProvider>
      <ModuleInner moduleKey={key} />
      <TweaksPanel />
    </TweaksProvider>
  );
}
