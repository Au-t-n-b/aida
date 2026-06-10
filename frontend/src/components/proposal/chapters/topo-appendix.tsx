'use client';

import TopologyDiagram from '../../topology-diagram';
import { ProposalChapterCard, ProposalKpiRow } from '../primitives';

export function TopoAppendixChapter() {
  return (
    <ProposalChapterCard id="panel-topo" title="附录 · 集群规划与拓扑" variant="secondary">
      <ProposalKpiRow
        items={[
          { label: '训练节点', value: '384 节点' },
          { label: '机房 / PoD', value: '6 机房 · 36 PoD' },
          { label: '互联', value: '400G RoCE 全互联' },
        ]}
      />
      <TopologyDiagram />
    </ProposalChapterCard>
  );
}
