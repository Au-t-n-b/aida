import { useParams } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import ModuleRoute from '@/components/module-route';
import SkillAgentScreen from '@/components/screens/survey-agent';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';
import { ALL_MODULES, MODULE_SCHEMAS } from '@/data/modules-data';
import { MODULE_TO_SKILL } from '@/data/module-skill-map';
import { isSystemDesignFull } from '@/config/design-skill';

/** 已接 LangGraph skill、但尚未写入 MODULE_SCHEMAS 的模块展示名 */
const MODULE_DISPLAY_NAMES: Record<string, string> = {
  install: '设备安装',
  deploy: '部署调测',
};

/* 模块衔接：建模仿真 → 系统设计（xtsj PoC 模式下禁用 autostart） */
const MODULE_NEXT: Record<string, { label: string; to: string }> = isSystemDesignFull
  ? { modeling: { label: '进入系统设计', to: '/module/design?autostart=1' } }
  : {};

function ModuleInner({ moduleKey }: { moduleKey: string }) {
  const { tweaks, setTweak } = useTweaks();
  const schema = MODULE_SCHEMAS[moduleKey as keyof typeof MODULE_SCHEMAS];
  const moduleEntry = ALL_MODULES.find(m => m.key === moduleKey);
  const name = schema?.name ?? moduleEntry?.name ?? MODULE_DISPLAY_NAMES[moduleKey] ?? moduleKey;
  const skillId = MODULE_TO_SKILL[moduleKey];
  const nextModule = MODULE_NEXT[moduleKey];

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
        <SkillAgentScreen
          key={skillId}
          skillId={skillId}
          title={name}
          description={schema?.subtitle ?? moduleEntry?.desc}
          nextModule={nextModule}
        />
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
