/**
 * 为 SDUI 递归列表生成稳定 React key：优先 node.id，否则基于节点内容摘要 + 父路径与下标保证同级唯一。
 */

import type { SduiNode } from '@/lib/sdui';

function hashDjb2Hex(input: string): string {
  let h = 5381;
  for (let i = 0; i < input.length; i++) {
    h = (h * 33) ^ input.charCodeAt(i);
  }
  return (h >>> 0).toString(16);
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String((value as { type?: string })?.type ?? 'node');
  }
}

export function stableChildKey(node: SduiNode, index: number, parentKey: string): string {
  const rawId = (node as { id?: unknown }).id;
  if (typeof rawId === 'string' && rawId.trim()) {
    // 同级可重复 id（如多轮 cv-user）→ 追加 index 保证 React key 唯一
    return `id:${rawId.trim()}:i:${index}`;
  }
  const sig = safeStringify(node);
  const h = hashDjb2Hex(sig);
  return `${parentKey}/n:${h}:i:${index}`;
}
