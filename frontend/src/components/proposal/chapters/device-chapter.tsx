'use client';

import { ProposalChapterCard } from '../primitives';
import { COMPUTE_DEVICES } from '../proposal-data';

const SOURCE_TEXT: Record<string, string> = { BOQ: '自动解析', HLD: '人工录入', 人工: '人工录入' };
const srcLabel = (s: string) => SOURCE_TEXT[s] ?? s;

export function DeviceChapter() {
  return (
    <ProposalChapterCard id="sec-ch-2" title="2. 设备配置信息">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full table-fixed border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
              <th className="px-3 py-2.5 font-semibold">设备型号</th>
              <th className="px-3 py-2.5 font-semibold">产品编码</th>
              <th className="px-3 py-2.5 font-semibold">版本</th>
              <th className="px-3 py-2.5 font-semibold">生命周期</th>
              <th className="px-3 py-2.5 font-semibold">数量</th>
              <th className="px-3 py-2.5 font-semibold">设备U高</th>
              <th className="px-3 py-2.5 font-semibold">来源</th>
            </tr>
          </thead>
          <tbody>
            {COMPUTE_DEVICES.map((d, i) => (
              <tr key={i} className="border-t border-slate-100 text-slate-700">
                <td className="px-3 py-2.5">
                  <span className="block max-w-[160px] truncate" title={d.model}>
                    {d.model}
                  </span>
                </td>
                <td className="px-3 py-2.5 font-mono text-xs text-slate-600">{d.code}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-slate-600">{d.ver}</td>
                <td className="px-3 py-2.5">{d.lifecycle}</td>
                <td className="px-3 py-2.5">{d.qty}</td>
                <td className="px-3 py-2.5">{d.unitSpace}</td>
                <td className="px-3 py-2.5 text-slate-500">{srcLabel(d.source)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProposalChapterCard>
  );
}
