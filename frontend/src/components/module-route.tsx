// @ts-nocheck
'use client';

import { useState, useRef, useEffect } from 'react';
import { useTweaks } from '../lib/tweaks-context';
import { MODULE_SCHEMAS } from '../data/modules-data';
import { ModuleHeader, WarRoomWorkbench } from './war-room';
import { RightRail } from './right-rail';
import { Avatar, ChatMessage, ThoughtTrace, HITLOptions, ToolApprovalCard, ChatComposer, ThinkingDots } from './chat';
import { Button } from './primitives';

const STAGE_MAP = {
  guide:     { idx: 0, phase: 0 },
  decide:    { idx: 1, phase: 0 },
  upload:    { idx: 2, phase: 0 },
  execute:   { idx: 3, phase: 2 },
  synthesize:{ idx: 4, phase: 3 },
  finish:    { idx: 5, phase: 4 },
};

function buildChatForStage(schema, stage) {
  const msgs = [];
  const s = stage?.toLowerCase() || 'guide';

  msgs.push({
    id: 'welcome',
    kind: 'ai',
    author: 'AIDA',
    text: schema.welcome,
    timestamp: '10:00',
  });

  if (s === 'guide') return msgs;

  if (s === 'decide' || s !== 'guide') {
    msgs.push({ id: 'decide-ask', kind: 'ai', author: 'AIDA', text: schema.decideAsk, timestamp: '10:01' });
    msgs.push({ id: 'decide-hitl', kind: 'hitl', schema, timestamp: '10:01' });
  }

  if (s === 'decide') return msgs;

  msgs.push({ id: 'decide-done', kind: 'user', author: '张伟', text: '已选择作业场景，请继续。', timestamp: '10:03' });
  msgs.push({ id: 'upload-ask', kind: 'ai', author: 'AIDA', text: schema.uploadAsk, timestamp: '10:03' });

  if (s === 'upload') return msgs;

  msgs.push({ id: 'upload-done', kind: 'user', author: '张伟', text: '文件已上传，共 ' + (schema.files?.length || 2) + ' 个。', timestamp: '10:08' });

  if (s === 'execute' || s === 'synthesize' || s === 'finish') {
    msgs.push({
      id: 'tool-approval',
      kind: 'tool',
      tool: `${schema.skillNames?.[0] || 'analysis'}.run`,
      params: { module: schema.key, files: schema.files?.map(f => f.name) || [] },
      timestamp: '10:09',
    });
    msgs.push({ id: 'execute-ask', kind: 'ai', author: 'AIDA', text: schema.executeAsk, timestamp: '10:09' });
    msgs.push({ id: 'trace', kind: 'trace', items: [`初始化 ${schema.skillNames?.[0]}`, `加载模型权重`, `开始并行处理`], timestamp: '10:10' });
  }

  if (s === 'synthesize' || s === 'finish') {
    msgs.push({ id: 'synth-done', kind: 'ai', author: 'AIDA', text: '分析完成，正在生成摘要报告…', timestamp: '10:24' });
  }

  if (s === 'finish') {
    msgs.push({ id: 'finish-ask', kind: 'ai', author: 'AIDA', text: schema.finishAsk, timestamp: '10:26' });
  }

  return msgs;
}

/* 5.25 + 5.27 · 售前继承 + 多模态解析 (C-1 / C-4)
 * 5.25 L55:18 "售前公勘里发现的问题…重点判定…不需要再重新卡来"
 * 5.27 SVG "维保建议书多模态解析" + "陈卓数据血缘抽取" */
function PresaleInheritBanner({ moduleKey }) {
  const [enabled, setEnabled] = useState(true);

  /* 不同模块继承的内容不同 */
  const INHERIT_BY_MODULE = {
    survey:   { source: '售前公勘 PPT_K1903', items: '12 项已勘察 / 3 项遗留问题', target: '本次工勘可跳过 12 项重做' },
    modeling: { source: 'HLD-K1903-v2',       items: '24 个网络段 / 8 个机房',     target: '建模仿真自动加载基线' },
    install:  { source: 'BOQ + CAD 底图',     items: '47 设备 / 14 机房',           target: '安装清单自动填充' },
    deploy:   { source: '测试用例集 v2',      items: '47 测试用例',                  target: '调测自动跑预定义脚本' },
  };
  const meta = INHERIT_BY_MODULE[moduleKey] || INHERIT_BY_MODULE.survey;

  return (
    <div className={`presale-banner${enabled ? ' on' : ''}`}>
      <div className="presale-banner-toggle">
        <label className="presale-switch">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => setEnabled(e.target.checked)}
          />
          <span className="presale-switch-slider" />
        </label>
        <div className="presale-banner-text">
          <strong>售前继承</strong> · 来自 {meta.source}
          <span className="presale-banner-items">{meta.items}</span>
        </div>
        <div className="presale-banner-target">
          {enabled ? <>✓ {meta.target}</> : '已关闭：本模块从零开始'}
        </div>
      </div>
      <div className="presale-banner-modal">
        <strong>多模态解析</strong>
        <span className="multimodal-chip">PDF</span>
        <span className="multimodal-chip">DOCX</span>
        <span className="multimodal-chip">XLSX</span>
        <span className="multimodal-chip">DWG</span>
        <span className="multimodal-chip stale">CAD 兜底手填</span>
      </div>
    </div>
  );
}

export default function ModuleRoute({ moduleKey }) {
  const { tweaks, setTweak } = useTweaks();
  const effectiveKey = moduleKey || tweaks.module;
  const schema = MODULE_SCHEMAS[effectiveKey] || MODULE_SCHEMAS.survey;
  const stage = tweaks.stage;
  const stageData = STAGE_MAP[stage] || STAGE_MAP.guide;

  const [previewFile, setPreviewFile] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [userMessages, setUserMessages] = useState([]);
  const chatEndRef = useRef(null);

  const baseMsgs = buildChatForStage(schema, stage);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [baseMsgs.length, userMessages.length]);

  function handleSend(text) {
    setUserMessages(m => [...m, { id: Date.now(), kind: 'user', author: '张伟', text, timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }]);
  }

  const allMessages = [...baseMsgs, ...userMessages];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <ModuleHeader schema={schema} stage={stage} />
      <PresaleInheritBanner moduleKey={effectiveKey} />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Chat panel */}
        <aside style={{ width: 'var(--chat-w)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0, background: 'var(--surface)' }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '10px 10px 0' }} className="claw-scroll">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {allMessages.map((msg) => {
                if (msg.kind === 'ai') {
                  return (
                    <ChatMessage key={msg.id} author={msg.author} kind="ai" timestamp={msg.timestamp}>
                      {msg.text}
                    </ChatMessage>
                  );
                }
                if (msg.kind === 'user') {
                  return (
                    <ChatMessage key={msg.id} author={msg.author} kind="user" timestamp={msg.timestamp}>
                      {msg.text}
                    </ChatMessage>
                  );
                }
                if (msg.kind === 'hitl') {
                  return (
                    <div key={msg.id} style={{ paddingLeft: 34 }}>
                      <HITLOptions
                        title={msg.schema.hitl.title}
                        hint={msg.schema.hitl.hint}
                        options={msg.schema.hitl.options}
                        multi={msg.schema.hitl.multi}
                        locked={stage !== 'decide'}
                        onSubmit={(sel) => {
                          setTweak('stage', 'upload');
                        }}
                      />
                    </div>
                  );
                }
                if (msg.kind === 'tool') {
                  return (
                    <div key={msg.id} style={{ paddingLeft: 34 }}>
                      <ToolApprovalCard
                        tool={msg.tool}
                        params={msg.params}
                        decided={stage !== 'upload' ? 'run' : undefined}
                        onRun={() => setTweak('stage', 'execute')}
                        onCancel={() => {}}
                      />
                    </div>
                  );
                }
                if (msg.kind === 'trace') {
                  return (
                    <div key={msg.id} style={{ paddingLeft: 34 }}>
                      <ThoughtTrace items={msg.items} active={stage === 'execute'} />
                    </div>
                  );
                }
                return null;
              })}
              {stage === 'execute' && <div style={{ paddingLeft: 34 }}><ThinkingDots /></div>}
            </div>
            <div ref={chatEndRef} />
          </div>
          <ChatComposer onSend={handleSend} model="claude-opus-4-7" disabled={stage === 'execute'} />
        </aside>

        {/* Workbench */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--zinc-50)' }}>
          <WarRoomWorkbench
            schema={schema}
            stage={stage}
            phase={stageData.phase}
            onPreview={setPreviewFile}
            onStart={() => setTweak('stage', 'decide')}
          />

          {/* Stage navigation buttons */}
          <div style={{ padding: 'var(--sp-2) var(--pad-panel)', borderTop: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            {stage !== 'guide' && (
              <Button variant="secondary" size="sm" onClick={() => {
                const keys = Object.keys(STAGE_MAP);
                const cur = keys.indexOf(stage);
                if (cur > 0) setTweak('stage', keys[cur - 1]);
              }}>← 上一步</Button>
            )}
            {stage !== 'finish' && (
              <Button variant="primary" size="sm" onClick={() => {
                const keys = Object.keys(STAGE_MAP);
                const cur = keys.indexOf(stage);
                if (cur < keys.length - 1) setTweak('stage', keys[cur + 1]);
              }}>下一步 →</Button>
            )}
            {stage === 'finish' && (
              <Button variant="primary" size="sm">提交交付基线 ✓</Button>
            )}
          </div>
        </div>

        {/* Right rail */}
        <RightRail previewFile={previewFile} onClosePreview={() => setPreviewFile(null)} />
      </div>
    </div>
  );
}
