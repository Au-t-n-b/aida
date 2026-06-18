import { useParams } from 'react-router-dom';
import ModuleRoute from '@/components/module-route';
import SkillAgentScreen from '@/components/screens/survey-agent';
import { ALL_MODULES, MODULE_SCHEMAS } from '@/data/modules-data';
import { useSkillRegistry, selectRouteMap } from '@/data/skill-registry';
import { isSystemDesignFull } from '@/config/design-skill';

const MODULE_DISPLAY_NAMES: Record<string, string> = {
  install: '设备安装',
  deploy: '部署调测',
};

const MODULE_NEXT: Record<string, { label: string; to: string }> = isSystemDesignFull
  ? { modeling: { label: '进入系统设计', to: '/module/design?autostart=1' } }
  : {};

function ModuleInner({ moduleKey }: { moduleKey: string }) {
  const skills = useSkillRegistry();
  const skillId = selectRouteMap(skills)[moduleKey];

  const schema = MODULE_SCHEMAS[moduleKey as keyof typeof MODULE_SCHEMAS] as
    | { name?: string; subtitle?: string }
    | undefined;
  const moduleEntry = ALL_MODULES.find((m) => m.key === moduleKey);
  const name =
    schema?.name ?? moduleEntry?.name ?? MODULE_DISPLAY_NAMES[moduleKey] ?? moduleKey;
  const nextModule = MODULE_NEXT[moduleKey];

  if (skillId) {
    return (
      <SkillAgentScreen
        key={skillId}
        skillId={skillId}
        title={name}
        description={schema?.subtitle ?? moduleEntry?.desc}
        nextModule={nextModule}
      />
    );
  }

  return <ModuleRoute moduleKey={moduleKey} />;
}

export default function ModuleRoutePage() {
  const { key: rawKey } = useParams();
  const key = rawKey ?? 'survey';
  return <ModuleInner moduleKey={key} />;
}
