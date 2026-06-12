'use client';

import { ProposalChapterCard } from '../primitives';

interface PodRack {
  pod: string;
  room: string;
  compute: string;
  bus: string;
  paramLeaf: string;
  bizLeaf: string;
  mgmt: string;
  sampleLeaf: string;
}

const POD_RACKS: PodRack[] = [
  { pod: 'POD1', room: '401', compute: 'A01,A02,A03,A04,A05,A06,A11,A12,A13,A14,A15,A16', bus: 'A07,A08,A09,A10', paramLeaf: 'A17,A18', bizLeaf: 'A17,A18', mgmt: 'A17,A18', sampleLeaf: '' },
  { pod: 'POD2', room: '401', compute: 'B01,B02,B03,B04,B05,B06,B11,B12,B13,B14,B15,B16', bus: 'B07,B08,B09,B10', paramLeaf: 'B17,B18', bizLeaf: 'B17,B18', mgmt: 'B17,B18', sampleLeaf: '' },
  { pod: 'POD3', room: '401', compute: 'C01,C02,C03,C04,C05,C06,C11,C12,C13,C14,C15,C16', bus: 'C07,C08,C09,C10', paramLeaf: 'C17,C18', bizLeaf: 'C17,C18', mgmt: 'C17,C18', sampleLeaf: '' },
  { pod: 'POD4', room: '401', compute: 'D01,D02,D03,D04,D05,D06,D11,D12,D13,D14,D15,D16', bus: 'D07,D08,D09,D10', paramLeaf: 'D17,D18', bizLeaf: 'D17,D18', mgmt: 'D17,D18', sampleLeaf: '' },
  { pod: 'POD5', room: '402', compute: 'A01,A02,A03,A04,A05,A06,A11,A12,A13,A14,A15,A16', bus: 'A07,A08,A09,A10', paramLeaf: 'A17,A18', bizLeaf: 'A17,A18', mgmt: 'A17,A18', sampleLeaf: '' },
  { pod: 'POD6', room: '402', compute: 'B01,B02,B03,B04,B05,B06,B11,B12,B13,B14,B15,B16', bus: 'B07,B08,B09,B10', paramLeaf: 'B17,B18', bizLeaf: 'B17,B18', mgmt: 'B17,B18', sampleLeaf: '' },
  { pod: 'POD7', room: '402', compute: 'C01,C02,C03,C04,C05,C06,C11,C12,C13,C14,C15,C16', bus: 'C07,C08,C09,C10', paramLeaf: 'C17,C18', bizLeaf: 'C17,C18', mgmt: 'C17,C18', sampleLeaf: '' },
  { pod: 'POD8', room: '402', compute: 'D01,D02,D03,D04,D05,D06,D11,D12,D13,D14,D15,D16', bus: 'D07,D08,D09,D10', paramLeaf: 'D17,D18', bizLeaf: 'D17,D18', mgmt: 'D17,D18', sampleLeaf: '' },
  { pod: 'POD9', room: '403', compute: 'A01,A02,A03,A04,A05,A06,A11,A12,A13,A14,A15,A16', bus: 'A07,A08,A09,A10', paramLeaf: 'A17,A18', bizLeaf: 'A17,A18', mgmt: 'A17,A18', sampleLeaf: '' },
];

const COLS: { key: keyof PodRack; label: string; w?: number }[] = [
  { key: 'pod', label: 'PoD名称', w: 84 },
  { key: 'room', label: '机房名称', w: 88 },
  { key: 'compute', label: '计算柜', w: 230 },
  { key: 'bus', label: '总线柜', w: 130 },
  { key: 'paramLeaf', label: '参数面Leaf柜', w: 130 },
  { key: 'bizLeaf', label: '业务面Leaf柜', w: 130 },
  { key: 'mgmt', label: '管理面柜', w: 130 },
  { key: 'sampleLeaf', label: '样本面Leaf柜', w: 130 },
];

export function RoomChapter() {
  return (
    <ProposalChapterCard id="panel-rooms" title="7. 机房信息">
      <div className="overflow-x-auto rounded-md border border-slate-100">
        <table className="w-full min-w-[1040px] border-collapse text-sm">
          <colgroup>
            {COLS.map((c) => (
              <col key={c.key} style={c.w ? { width: c.w } : undefined} />
            ))}
          </colgroup>
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              {COLS.map((c) => (
                <th key={c.key} className="px-3 py-2.5 font-semibold">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {POD_RACKS.map((r) => (
              <tr key={r.pod} className="border-t border-slate-100 align-top">
                {COLS.map((c) => (
                  <td key={c.key} className="break-words px-3 py-2.5">
                    {r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProposalChapterCard>
  );
}
