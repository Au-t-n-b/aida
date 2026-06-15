import type { CurrentProject } from '@/lib/current-project';

/** TopBar 项目下拉 · G-3 多角色 chip 演示数据 */
export type ProjectRoleChip = { role: 'PD' | 'TD' | 'PCM' | 'TL' | 'OCC'; name: string };

export type ProjectMini = {
  id: string;
  name: string;
  code?: string;
  roles: ProjectRoleChip[];
};

export const PROJECT_LIST_MINI: ProjectMini[] = [
  {
    id: 'K1903',
    name: '京东三期',
    roles: [
      { role: 'PD', name: '李伟' },
      { role: 'TD', name: '何博' },
      { role: 'PCM', name: '王婷' },
      { role: 'OCC', name: '黎芳' },
    ],
  },
  {
    id: 'A1',
    name: 'A1 智算集群一期',
    roles: [
      { role: 'PD', name: '李伟' },
      { role: 'TD', name: '王明' },
      { role: 'TL', name: '调试组 K' },
    ],
  },
  {
    id: 'B2',
    name: 'B2 智算中心',
    roles: [
      { role: 'PD', name: '李伟' },
      { role: 'TD', name: '赵丹' },
      { role: 'TL', name: '施工队 07' },
    ],
  },
  {
    id: 'C3',
    name: 'C3 算力底座扩容',
    roles: [
      { role: 'PD', name: '周晗' },
      { role: 'TD', name: '王明' },
    ],
  },
];

/** 与 TopBar `.topbar-project-name` 展示文本一致 */
export function resolveTopBarProjectDisplayName(project: CurrentProject | null): string {
  const currentId = project?.id ?? PROJECT_LIST_MINI[0]!.id;
  return (
    project?.name
    ?? PROJECT_LIST_MINI.find((p) => p.id === currentId)?.name
    ?? PROJECT_LIST_MINI[0]!.name
  );
}
