import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const schemaDir = path.join(__dirname, "schema");
const outputPath = path.join(__dirname, "unified-activity-ontology-view.html");

const RETIRED_RISK_LEDGER_OBJECTS = new Set(["RiskItem"]);
const RETIRED_RISK_LEDGER_LINKS = new Set(["Assessment_Risks"]);
const RETIRED_RISK_LEDGER_ACTIONS = new Set(["UpdateRiskStatus", "AdoptDerivedRisk", "DismissDerivedRisk"]);
const RETIRED_RISK_LEDGER_VALUE_TYPES = new Set(["RiskState"]);

function readJson(fileName) {
  return JSON.parse(fs.readFileSync(path.join(schemaDir, fileName), "utf8"));
}

function cleanRiskLedgerText(value) {
  if (typeof value !== "string") return value;
  return value
    .replaceAll("RiskItem-shaped suggestion", "RiskSuggestion")
    .replaceAll("RiskItem 形态的建议记录", "RiskSuggestion 风险建议记录")
    .replaceAll("正式 RiskItem", "下游风险单")
    .replaceAll("RiskItem", "RiskSuggestion")
    .replaceAll("risk_item", "risk_suggestion");
}

function cleanRiskLedgerReferences(value) {
  if (typeof value === "string") return cleanRiskLedgerText(value);
  if (Array.isArray(value)) return value.map(cleanRiskLedgerReferences);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entryValue]) => [key, cleanRiskLedgerReferences(entryValue)])
    );
  }
  return value;
}

function actionReferencesRetiredRiskLedger(actionType) {
  const targetObject = actionType.targetObjectTypeApiName || "";
  if (RETIRED_RISK_LEDGER_ACTIONS.has(actionType.apiName) || RETIRED_RISK_LEDGER_OBJECTS.has(targetObject)) {
    return true;
  }
  return Object.values(actionType.parameters || {}).some(
    (parameter) =>
      parameter.dataType?.type === "ontologyObject" &&
      RETIRED_RISK_LEDGER_OBJECTS.has(parameter.dataType.objectTypeApiName || "")
  );
}

function displayName(entry) {
  return entry?.displayMetadata?.displayName || entry?.apiName || "";
}

function displayDescription(entry) {
  return entry?.displayMetadata?.description || entry?.description || "";
}

function dataTypeName(dataType) {
  if (!dataType) return "unknown";
  if (typeof dataType === "string") return dataType;
  if (dataType.type === "ontologyObject") {
    return `ontologyObject:${dataType.objectTypeApiName || "unknown"}`;
  }
  if (dataType.type === "array") {
    return `array<${dataTypeName(dataType.itemType || dataType.items)}>`;
  }
  if (dataType.type === "struct") {
    return "struct";
  }
  return dataType.type || JSON.stringify(dataType);
}

function summarizeProperty(property) {
  return {
    apiName: property.apiName,
    label: displayName(property),
    description: displayDescription(property),
    type: dataTypeName(property.dataType),
    required: Boolean(property.required),
    valueType: property.valueType || "",
    sourceColumnName: property.sourceColumnName || "",
  };
}

function summarizeParameter(apiName, parameter) {
  return {
    apiName,
    label: displayName({ apiName, ...parameter }),
    description: displayDescription(parameter),
    type: dataTypeName(parameter.dataType),
    objectType:
      parameter.dataType?.type === "ontologyObject"
        ? parameter.dataType.objectTypeApiName || ""
        : "",
    required: Boolean(parameter.required),
  };
}

function assignDomain(apiName, label) {
  const text = `${apiName} ${label}`.toLowerCase();
  const has = (...tokens) => tokens.some((token) => text.includes(token.toLowerCase()));

  if (
    has(
      "Contingency",
      "Decision",
      "Deliverability",
      "Gap",
      "Remediation",
      "Assumption",
      "预案",
      "决策",
      "整改",
      "差异",
      "假设"
    )
  ) {
    return "预案决策";
  }

  if (
    has(
      "Config",
      "Policy",
      "Requirement",
      "Strategy",
      "Snapshot",
      "Verification",
      "Matrix",
      "File",
      "Inventory",
      "TestCase",
      "Contract",
      "BasicInfo",
      "Version",
      "Layout",
      "Rule",
      "配置",
      "组网",
      "机房",
      "验收",
      "合同",
      "测试"
    )
  ) {
    return "配置资产";
  }

  if (
    has(
      "Participant",
      "Resource",
      "Capability",
      "Assignment",
      "SlaEstimate",
      "WorkCalendar",
      "CalendarException",
      "EquipmentRoom",
      "EquipmentArrival",
      "ActivityTemplate",
      "队伍",
      "日历",
      "到货",
      "模板"
    )
  ) {
    return "资源日历";
  }

  if (has("Evidence", "ParsedDocument", "ChapterNarrative", "Document", "证据", "文档", "章节正文")) {
    return "文档证据";
  }

  if (
    has(
      "Delivery",
      "Project",
      "Pod",
      "Supplier",
      "ChangeOrder",
      "Milestone",
      "Schedule",
      "Batch",
      "PlanRow",
      "交付",
      "项目",
      "供应商",
      "里程碑",
      "排期"
    )
  ) {
    return "交付排期";
  }

  return "其他";
}

function statusBreakdown(items) {
  return items.reduce((acc, item) => {
    acc[item.status || "UNKNOWN"] = (acc[item.status || "UNKNOWN"] || 0) + 1;
    return acc;
  }, {});
}

function buildViewModel() {
  const objectsRaw = readJson("object-types.json");
  const linksRaw = readJson("link-types.json");
  const actionsRaw = readJson("action-types.json");
  const functionsRaw = readJson("function-types.json");
  const interfacesRaw = readJson("interface-types.json");
  const valueTypesRaw = readJson("value-types.json");

  const objects = Object.values(objectsRaw).filter((objectType) => !RETIRED_RISK_LEDGER_OBJECTS.has(objectType.apiName)).map((objectType) => {
    const label = displayName(objectType);
    return {
      apiName: objectType.apiName,
      label,
      description: displayDescription(objectType),
      status: objectType.status || "UNKNOWN",
      domain: assignDomain(objectType.apiName, label),
      interfaces: objectType.implementsInterfaces || [],
      primaryKeys: objectType.primaryKeyPropertyApiNames || [],
      titleProperty: objectType.titlePropertyApiName || "",
      contingencyChapter: objectType.contingencyChapter || "",
      properties: Object.values(objectType.properties || {}).map(summarizeProperty),
      localGeneration: objectType.localGeneration || null,
    };
  });

  const objectByName = new Map(objects.map((objectType) => [objectType.apiName, objectType]));

  const links = Object.values(linksRaw).filter((linkType) => {
    const from = linkType.objectTypeApiName;
    const to = linkType.linkedObjectTypeApiName;
    return (
      !RETIRED_RISK_LEDGER_LINKS.has(linkType.apiName) &&
      !RETIRED_RISK_LEDGER_OBJECTS.has(from) &&
      !RETIRED_RISK_LEDGER_OBJECTS.has(to)
    );
  }).map((linkType) => {
    const from = linkType.objectTypeApiName;
    const to = linkType.linkedObjectTypeApiName;
    const label = displayName(linkType);
    return {
      apiName: linkType.apiName,
      label,
      description: displayDescription(linkType),
      status: linkType.status || "UNKNOWN",
      from,
      to,
      fromLabel: objectByName.get(from)?.label || from,
      toLabel: objectByName.get(to)?.label || to,
      domain: objectByName.get(from)?.domain || objectByName.get(to)?.domain || "其他",
      cardinality: linkType.cardinality || "",
      model: linkType.relationshipModel || "",
      forwardLink: linkType.forwardLink
        ? {
            apiName: linkType.forwardLink.apiName || "",
            label: displayName(linkType.forwardLink),
            description: displayDescription(linkType.forwardLink),
          }
        : null,
      reverseLink: linkType.reverseLink
        ? {
            apiName: linkType.reverseLink.apiName || "",
            label: displayName(linkType.reverseLink),
            description: displayDescription(linkType.reverseLink),
          }
        : null,
      foreignKey: linkType.foreignKey || null,
      derivedMembership: linkType.derivedMembership || null,
      nameResolution: linkType.nameResolution || null,
      resolvedEdgeShape: linkType.resolvedEdgeShape || null,
      localGeneration: linkType.localGeneration || null,
    };
  });

  const actions = Object.values(actionsRaw).filter((actionType) => !actionReferencesRetiredRiskLedger(actionType)).map((actionType) => {
    const targetObject = actionType.targetObjectTypeApiName || "";
    const parameters = Object.entries(actionType.parameters || {}).map(([apiName, parameter]) =>
      summarizeParameter(apiName, parameter)
    );
    const touchedObjects = Array.from(
      new Set([targetObject, ...parameters.map((parameter) => parameter.objectType).filter(Boolean)].filter(Boolean))
    );
    const propertyWrites = Array.from(
      new Set(
        (actionType.edits || []).flatMap((edit) =>
          Object.keys(edit.propertyUpdates || {}).map((property) => {
            const targetParameter = edit.targetParameter || edit.objectParameter || "";
            return targetParameter ? `${targetParameter}.${property}` : property;
          })
        )
      )
    );
    const label = displayName(actionType);
    return {
      apiName: actionType.apiName,
      label,
      description: displayDescription(actionType),
      status: actionType.status || "UNKNOWN",
      targetObject,
      targetLabel: objectByName.get(targetObject)?.label || targetObject,
      domain: objectByName.get(targetObject)?.domain || assignDomain(actionType.apiName, label),
      parameters,
      edits: actionType.edits || [],
      propertyWrites,
      touchedObjects,
      rules: actionType.rules || [],
      stateTransitions: actionType.stateTransitions || [],
      strategy: actionType.strategy || null,
      submissionCriteria: actionType.submissionCriteria || null,
      targetConstraints: actionType.targetConstraints || null,
      writeback: actionType.writeback || null,
      sideEffects: actionType.sideEffects || null,
    };
  });

  const functions = Object.values(functionsRaw).map((functionType) => {
    const parameters = Object.entries(functionType.parameters || {}).map(([apiName, parameter]) =>
      summarizeParameter(apiName, parameter)
    );
    const label = displayName(functionType);
    return {
      apiName: functionType.apiName,
      label,
      kind: functionType.kind || "FUNCTION",
      description: displayDescription(functionType),
      status: functionType.status || "UNKNOWN",
      domain: assignDomain(functionType.apiName, label),
      parameters,
      returnType: functionType.returnType || null,
      sideEffects: functionType.sideEffects || null,
      binding: functionType.binding || null,
    };
  });

  const domains = Array.from(new Set(objects.map((objectType) => objectType.domain))).sort((a, b) => {
    const order = ["交付排期", "资源日历", "预案决策", "配置资产", "文档证据", "其他"];
    return order.indexOf(a) - order.indexOf(b);
  });

  const valueTypes = Object.values(valueTypesRaw)
    .filter((entry) => !RETIRED_RISK_LEDGER_VALUE_TYPES.has(entry.apiName))
    .map((entry) => ({
      apiName: entry.apiName,
      label: displayName(entry),
      description: displayDescription(entry),
      baseType: entry.baseType || entry.type || "",
    }));

  return cleanRiskLedgerReferences({
    title: "统一活动面本体",
    subtitle: "D:\\Code\\aida\\ontology\\schema 实际大本体视图",
    generatedAt: new Date().toISOString(),
    sourceFiles: [
      "ontology/schema/object-types.json",
      "ontology/schema/link-types.json",
      "ontology/schema/action-types.json",
      "ontology/schema/function-types.json",
      "ontology/schema/interface-types.json",
      "ontology/schema/value-types.json",
    ],
    counts: {
      objects: objects.length,
      links: links.length,
      actions: actions.length,
      functions: functions.length,
      interfaces: Object.keys(interfacesRaw).length,
      valueTypes: valueTypes.length,
    },
    statusBreakdown: {
      objects: statusBreakdown(objects),
      links: statusBreakdown(links),
      actions: statusBreakdown(actions),
      functions: statusBreakdown(functions),
    },
    domains,
    objects,
    links,
    actions,
    functions,
    interfaces: Object.values(interfacesRaw).map((entry) => ({
      apiName: entry.apiName,
      label: displayName(entry),
      description: displayDescription(entry),
      properties: entry.properties || [],
    })),
    valueTypes,
  });
}

function embeddedJson(value) {
  return JSON.stringify(value, null, 2).replace(/</g, "\\u003c");
}

function htmlTemplate(viewModel) {
  const data = embeddedJson(viewModel);
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${viewModel.title} · 大视图</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #14213d;
      --muted: #607087;
      --line: #d8e1ec;
      --paper: #fbfcf7;
      --panel: #ffffff;
      --panel-2: #f3f8f5;
      --steel: #2d4f64;
      --teal: #087f7b;
      --green: #3d8b5f;
      --amber: #b7791f;
      --rose: #b8325d;
      --violet: #6554c0;
      --cyan: #177e9a;
      --shadow: 0 18px 55px rgba(27, 50, 78, 0.12);
      --mono: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
      --sans: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        linear-gradient(120deg, rgba(8, 127, 123, 0.08), transparent 34%),
        linear-gradient(240deg, rgba(183, 121, 31, 0.10), transparent 38%),
        var(--paper);
      font-family: var(--sans);
    }

    button, input, select { font: inherit; }

    .page {
      width: min(1780px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 22px 0 32px;
    }

    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(340px, 0.6fr);
      gap: 18px;
      align-items: stretch;
      margin-bottom: 16px;
    }

    .hero-main, .source-panel, .toolbar, .stage, .list-panel {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.86);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
      border-radius: 8px;
    }

    .hero-main {
      padding: 24px 26px 22px;
      position: relative;
      overflow: hidden;
    }

    .eyebrow {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      color: var(--teal);
      font-family: var(--mono);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 700;
    }

    h1 {
      margin: 10px 0 8px;
      font-size: clamp(30px, 4vw, 54px);
      line-height: 1.04;
      letter-spacing: 0;
      font-weight: 820;
    }

    .lead {
      max-width: 880px;
      margin: 0;
      color: #40516a;
      font-size: 16px;
      line-height: 1.7;
    }

    .source-panel {
      padding: 18px;
      display: grid;
      align-content: start;
      gap: 12px;
    }

    .source-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .metric {
      border: 1px solid #dce7df;
      background: #fbfdf8;
      border-radius: 8px;
      padding: 10px 11px;
    }

    .metric strong {
      display: block;
      color: var(--steel);
      font-family: var(--mono);
      font-size: 24px;
      line-height: 1.1;
    }

    .metric span {
      color: var(--muted);
      font-size: 12px;
    }

    .source-line {
      color: var(--muted);
      font-family: var(--mono);
      font-size: 11px;
      line-height: 1.55;
      word-break: break-all;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }

    .toolbar {
      display: grid;
      grid-template-columns: minmax(240px, 1fr) 170px minmax(360px, auto);
      gap: 10px;
      align-items: center;
      padding: 12px;
      margin-bottom: 14px;
    }

    .toolbar input[type="search"], .toolbar select {
      width: 100%;
      height: 38px;
      border: 1px solid #ccdae7;
      border-radius: 7px;
      background: #fff;
      color: var(--ink);
      padding: 0 12px;
      outline: none;
    }

    .toolbar input[type="search"]:focus, .toolbar select:focus {
      border-color: var(--teal);
      box-shadow: 0 0 0 3px rgba(8, 127, 123, 0.13);
    }

    .toggles {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
      align-items: center;
    }

    .toggle, .chip, .required-chip, .domain-tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      color: #38516c;
      padding: 6px 9px;
      font-size: 12px;
      white-space: nowrap;
    }

    .toggle input { accent-color: var(--teal); }

    .stage {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 420px;
      min-height: 860px;
      overflow: hidden;
      margin-bottom: 14px;
    }

    .canvas-wrap {
      position: relative;
      min-width: 0;
      background:
        linear-gradient(90deg, rgba(20, 33, 61, 0.045) 1px, transparent 1px),
        linear-gradient(180deg, rgba(20, 33, 61, 0.045) 1px, transparent 1px),
        #fbfdf9;
      background-size: 34px 34px;
      border-right: 1px solid var(--line);
    }

    #graph {
      width: 100%;
      height: 100%;
      display: block;
      min-height: 860px;
      cursor: default;
    }

    .domain-bg {
      fill: rgba(255, 255, 255, 0.62);
      stroke-width: 1.1;
      stroke-dasharray: 7 6;
    }

    .domain-label {
      font-size: 14px;
      font-weight: 760;
      fill: #34465f;
    }

    .domain-count {
      font-family: var(--mono);
      font-size: 11px;
      fill: #6b7a90;
    }

    .edge {
      fill: none;
      stroke: #8aa0b8;
      stroke-width: 1.2;
      opacity: 0.64;
    }

    .edge-label {
      fill: #42556d;
      font-size: 10px;
      paint-order: stroke;
      stroke: rgba(255, 255, 255, 0.9);
      stroke-width: 5px;
      stroke-linejoin: round;
      pointer-events: none;
    }

    .action-edge {
      fill: none;
      stroke: var(--rose);
      stroke-width: 1;
      stroke-dasharray: 4 4;
      opacity: 0.42;
    }

    .function-edge {
      fill: none;
      stroke: var(--violet);
      stroke-width: 1;
      stroke-dasharray: 2 5;
      opacity: 0.36;
    }

    .node rect, .action-node rect, .function-node rect {
      rx: 7;
      stroke-width: 1.2;
      filter: drop-shadow(0 8px 14px rgba(31, 52, 75, 0.12));
      cursor: pointer;
    }

    .node text, .action-node text, .function-node text {
      pointer-events: none;
      font-size: 12px;
      font-weight: 720;
      fill: #13223a;
    }

    .node .api, .action-node .api, .function-node .api {
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 520;
      fill: #5f6f84;
    }

    .node.selected rect, .action-node.selected rect, .function-node.selected rect {
      stroke: #101820;
      stroke-width: 2.3;
      filter: drop-shadow(0 10px 18px rgba(8, 127, 123, 0.22));
    }

    .inspector {
      padding: 18px;
      overflow: auto;
      max-height: 860px;
      background: linear-gradient(180deg, #ffffff, #f8fbf5);
    }

    .inspector h2 {
      margin: 0 0 7px;
      font-size: 23px;
      line-height: 1.2;
      letter-spacing: 0;
    }

    .inspector .api-name {
      color: var(--teal);
      font-family: var(--mono);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .desc {
      color: #53657a;
      line-height: 1.62;
      margin: 10px 0 14px;
      font-size: 13px;
    }

    .detail-block {
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 12px;
    }

    .detail-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      color: #223955;
      font-weight: 780;
      font-size: 13px;
    }

    .kv {
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 7px;
      padding: 5px 0;
      color: #455870;
      font-size: 12px;
      border-bottom: 1px solid rgba(216, 225, 236, 0.6);
    }

    .kv b {
      color: #20334e;
      font-weight: 760;
    }

    .mini-list {
      display: grid;
      gap: 7px;
    }

    .mini-row {
      border: 1px solid #dce5ed;
      background: #fff;
      border-radius: 7px;
      padding: 8px;
      font-size: 12px;
      line-height: 1.45;
      cursor: pointer;
    }

    .mini-row:hover { border-color: var(--teal); }

    .mono {
      font-family: var(--mono);
    }

    .list-panel {
      overflow: hidden;
    }

    .list-header {
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: center;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      background: #fffefb;
    }

    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .tab, .action-button {
      height: 34px;
      border: 1px solid #c9d8e5;
      border-radius: 7px;
      background: #fff;
      color: #274159;
      padding: 0 11px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 710;
    }

    .tab.active {
      background: #17324d;
      color: #fff;
      border-color: #17324d;
    }

    .action-button:hover, .tab:hover {
      border-color: var(--teal);
    }

    .table-wrap {
      overflow: auto;
      max-height: 520px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      background: #fff;
    }

    th, td {
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid #e3ebf1;
      vertical-align: top;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #edf5f0;
      color: #274159;
      font-size: 11px;
      font-family: var(--mono);
    }

    tr { cursor: pointer; }
    tbody tr:hover { background: #f6fbf8; }

    .required-chip {
      color: #0f6d43;
      border-color: rgba(61, 139, 95, 0.35);
      background: rgba(61, 139, 95, 0.08);
    }

    .domain-tag {
      color: #26384f;
      background: #f7f3e9;
      border-color: #e5d8bb;
    }

    @media (max-width: 1180px) {
      .hero, .stage { grid-template-columns: 1fr; }
      .canvas-wrap { border-right: 0; border-bottom: 1px solid var(--line); }
      .toolbar { grid-template-columns: 1fr 1fr; }
      .toggles { justify-content: flex-start; }
      .inspector { max-height: none; }
    }

    @media (max-width: 720px) {
      .page { width: min(100vw - 18px, 1780px); padding-top: 10px; }
      .toolbar { grid-template-columns: 1fr; }
      .source-grid { grid-template-columns: 1fr 1fr; }
      .list-header { align-items: flex-start; flex-direction: column; }
      .hero-main { padding: 18px; }
      #graph { min-height: 760px; }
      .stage { min-height: auto; }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero" aria-labelledby="title">
      <div class="hero-main">
        <span class="eyebrow">Schema Registry · Big View</span>
        <h1 id="title">统一活动面本体 · 大视图</h1>
        <p class="lead">按当前 <span class="mono">ontology/schema</span> 实际注册表生成：对象层 ObjectType、关联层 LinkType、动作层 ActionType，以及 Function / Skill 能力层。页面内嵌完整视图模型，供查看、筛选、导出和后续处理。</p>
      </div>
      <aside class="source-panel" aria-label="schema source summary">
        <div class="source-grid" id="metrics"></div>
        <div class="source-line" id="sourceLine"></div>
      </aside>
    </section>

    <section class="toolbar" aria-label="filters">
      <input id="search" type="search" placeholder="搜索对象 / 动作 / 关联 / 字段 / 描述" />
      <select id="domainFilter"></select>
      <div class="toggles">
        <label class="toggle"><input type="checkbox" id="showLinks" checked />关联</label>
        <label class="toggle"><input type="checkbox" id="showActions" checked />动作</label>
        <label class="toggle"><input type="checkbox" id="showFunctions" />能力</label>
        <button class="action-button" id="exportJson">导出 JSON</button>
        <button class="action-button" id="exportCsv">导出当前表 CSV</button>
      </div>
    </section>

    <section class="stage">
      <div class="canvas-wrap">
        <svg id="graph" viewBox="0 0 1280 1100" role="img" aria-label="统一活动面本体对象动作关联图"></svg>
      </div>
      <aside class="inspector" id="inspector" aria-label="selected ontology item"></aside>
    </section>

    <section class="list-panel">
      <div class="list-header">
        <div class="tabs" id="tabs"></div>
        <div class="chip" id="tableMeta"></div>
      </div>
      <div class="table-wrap">
        <table id="dataTable"></table>
      </div>
    </section>
  </main>

  <script>
    const VIEW_MODEL = ${data};
    window.ONTOLOGY_VIEW_MODEL = VIEW_MODEL;
  </script>
  <script>
    const $ = (selector) => document.querySelector(selector);
    const svgNS = "http://www.w3.org/2000/svg";
    const domainOrder = ["交付排期", "资源日历", "预案决策", "配置资产", "文档证据", "其他"];
    const domainColors = {
      "交付排期": { fill: "#eaf5f4", stroke: "#087f7b", node: "#c9e9e5" },
      "资源日历": { fill: "#f4f6e7", stroke: "#718f2e", node: "#e1eab9" },
      "预案决策": { fill: "#fff2eb", stroke: "#b7791f", node: "#f7d8ab" },
      "配置资产": { fill: "#eef1fb", stroke: "#6554c0", node: "#d6d9f5" },
      "文档证据": { fill: "#eef8fb", stroke: "#177e9a", node: "#c9e9f2" },
      "其他": { fill: "#f5f3ef", stroke: "#6f7785", node: "#e2dfd7" },
    };
    const domainBoxes = {
      "交付排期": { x: 38, y: 54, w: 342, h: 270 },
      "资源日历": { x: 412, y: 54, w: 326, h: 270 },
      "预案决策": { x: 772, y: 54, w: 458, h: 270 },
      "配置资产": { x: 38, y: 364, w: 700, h: 300 },
      "文档证据": { x: 772, y: 364, w: 458, h: 132 },
      "其他": { x: 772, y: 530, w: 458, h: 134 },
    };

    const state = {
      q: "",
      domain: "all",
      showLinks: true,
      showActions: true,
      showFunctions: false,
      table: "objects",
      selected: { kind: "summary", id: "" },
    };

    const byObject = new Map(VIEW_MODEL.objects.map((item) => [item.apiName, item]));
    const byLink = new Map(VIEW_MODEL.links.map((item) => [item.apiName, item]));
    const byAction = new Map(VIEW_MODEL.actions.map((item) => [item.apiName, item]));
    const byFunction = new Map(VIEW_MODEL.functions.map((item) => [item.apiName, item]));

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function createSvg(tag, attrs = {}, text = "") {
      const element = document.createElementNS(svgNS, tag);
      Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
      if (text !== "") element.textContent = text;
      return element;
    }

    function labelOfObject(apiName) {
      return byObject.get(apiName)?.label || apiName || "未指定";
    }

    function shortLabel(value, limit = 14) {
      const text = String(value || "");
      if (text.length <= limit) return text;
      return text.slice(0, Math.max(1, limit - 1)) + "…";
    }

    function searchableText(item) {
      const { status, ...searchable } = item || {};
      return JSON.stringify(searchable).toLowerCase();
    }

    function matches(item) {
      if (state.domain !== "all" && item.domain !== state.domain) return false;
      if (!state.q) return true;
      return searchableText(item).includes(state.q);
    }

    function filteredObjects() {
      const direct = VIEW_MODEL.objects.filter(matches);
      if (state.q) {
        const objectNames = new Set(direct.map((item) => item.apiName));
        VIEW_MODEL.links.filter(matches).forEach((link) => {
          objectNames.add(link.from);
          objectNames.add(link.to);
        });
        VIEW_MODEL.actions.filter(matches).forEach((action) => {
          action.touchedObjects.forEach((objectName) => objectNames.add(objectName));
        });
        return VIEW_MODEL.objects.filter((item) => objectNames.has(item.apiName));
      }
      return direct;
    }

    function filteredLinks(objectSet) {
      if (!state.showLinks) return [];
      return VIEW_MODEL.links.filter((link) => {
        if (!objectSet.has(link.from) || !objectSet.has(link.to)) return false;
        if (state.domain !== "all" && link.domain !== state.domain) return false;
        if (!state.q) return true;
        return searchableText(link).includes(state.q) || searchableText(byObject.get(link.from)).includes(state.q) || searchableText(byObject.get(link.to)).includes(state.q);
      });
    }

    function filteredActions(objectSet) {
      if (!state.showActions) return [];
      return VIEW_MODEL.actions.filter((action) => {
        if (action.targetObject && !objectSet.has(action.targetObject)) return false;
        if (state.domain !== "all" && action.domain !== state.domain) return false;
        if (!state.q) return true;
        return searchableText(action).includes(state.q);
      });
    }

    function filteredFunctions() {
      if (!state.showFunctions) return [];
      return VIEW_MODEL.functions.filter(matches);
    }

    function layoutObjects(objects) {
      const positions = new Map();
      domainOrder.forEach((domain) => {
        const box = domainBoxes[domain];
        if (!box) return;
        const items = objects.filter((item) => item.domain === domain);
        if (!items.length) return;
        const cols = Math.max(1, Math.ceil(Math.sqrt(items.length * (box.w / Math.max(1, box.h)))));
        const rows = Math.ceil(items.length / cols);
        const stepX = box.w / cols;
        const stepY = box.h / rows;
        items.forEach((item, index) => {
          const col = index % cols;
          const row = Math.floor(index / cols);
          positions.set(item.apiName, {
            x: box.x + stepX * col + stepX / 2,
            y: box.y + 52 + stepY * row + Math.max(0, stepY - 56) / 2,
          });
        });
      });
      return positions;
    }

    function pathBetween(a, b, offset = 0) {
      if (!a || !b) return "";
      if (Math.abs(a.x - b.x) < 3 && Math.abs(a.y - b.y) < 3) {
        const r = 38 + offset;
        return \`M \${a.x - 10} \${a.y - 18} C \${a.x - r} \${a.y - r} \${a.x + r} \${a.y - r} \${a.x + 10} \${a.y - 18}\`;
      }
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const len = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const nx = -dy / len;
      const ny = dx / len;
      const curve = Math.min(62, Math.max(18, len * 0.13)) + offset;
      return \`M \${a.x} \${a.y} Q \${mx + nx * curve} \${my + ny * curve} \${b.x} \${b.y}\`;
    }

    function addGraphLayer(id) {
      const group = createSvg("g", { id });
      $("#graph").appendChild(group);
      return group;
    }

    function clearGraph() {
      $("#graph").replaceChildren();
    }

    function drawGraph() {
      clearGraph();
      const objects = filteredObjects();
      const objectSet = new Set(objects.map((item) => item.apiName));
      const links = filteredLinks(objectSet);
      const actions = filteredActions(objectSet);
      const functions = filteredFunctions();
      const positions = layoutObjects(objects);

      const domainLayer = addGraphLayer("domains");
      const linkLayer = addGraphLayer("links");
      const actionEdgeLayer = addGraphLayer("actionEdges");
      const nodeLayer = addGraphLayer("nodes");
      const actionLayer = addGraphLayer("actions");
      const functionLayer = addGraphLayer("functions");

      domainOrder.forEach((domain) => {
        const box = domainBoxes[domain];
        if (!box) return;
        const count = objects.filter((item) => item.domain === domain).length;
        if (!count && state.domain !== domain) return;
        const color = domainColors[domain] || domainColors["其他"];
        domainLayer.appendChild(createSvg("rect", {
          class: "domain-bg",
          x: box.x,
          y: box.y,
          width: box.w,
          height: box.h,
          rx: 8,
          fill: color.fill,
          stroke: color.stroke,
          opacity: count ? "1" : "0.28",
        }));
        domainLayer.appendChild(createSvg("text", { class: "domain-label", x: box.x + 16, y: box.y + 24 }, domain));
        domainLayer.appendChild(createSvg("text", { class: "domain-count", x: box.x + 16, y: box.y + 42 }, \`\${count} ObjectType\`));
      });

      links.forEach((link, index) => {
        const a = positions.get(link.from);
        const b = positions.get(link.to);
        if (!a || !b) return;
        const path = createSvg("path", {
          class: "edge",
          d: pathBetween(a, b, (index % 5) * 6),
          "data-kind": "link",
          "data-id": link.apiName,
        });
        path.addEventListener("click", (event) => {
          event.stopPropagation();
          selectItem("link", link.apiName);
        });
        linkLayer.appendChild(path);
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        if (state.q || links.length < 32 || index % 4 === 0) {
          linkLayer.appendChild(createSvg("text", {
            class: "edge-label",
            x: midX,
            y: midY - 4 - ((index % 3) * 8),
            "text-anchor": "middle",
          }, shortLabel(link.label || link.apiName, 12)));
        }
      });

      objects.forEach((objectType) => {
        const position = positions.get(objectType.apiName);
        if (!position) return;
        const label = objectType.label || objectType.apiName;
        const width = Math.max(106, Math.min(178, label.length * 15 + 34));
        const height = 42;
        const color = domainColors[objectType.domain] || domainColors["其他"];
        const group = createSvg("g", {
          class: \`node \${state.selected.kind === "object" && state.selected.id === objectType.apiName ? "selected" : ""}\`,
          transform: \`translate(\${position.x - width / 2}, \${position.y - height / 2})\`,
          "data-kind": "object",
          "data-id": objectType.apiName,
        });
        group.appendChild(createSvg("rect", {
          width,
          height,
          fill: color.node,
          stroke: color.stroke,
        }));
        group.appendChild(createSvg("title", {}, label + "\\n" + objectType.apiName));
        group.appendChild(createSvg("text", { x: width / 2, y: 18, "text-anchor": "middle" }, shortLabel(label, 9)));
        group.appendChild(createSvg("text", { class: "api", x: width / 2, y: 32, "text-anchor": "middle" }, shortLabel(objectType.apiName, 19)));
        group.addEventListener("click", (event) => {
          event.stopPropagation();
          selectItem("object", objectType.apiName);
        });
        nodeLayer.appendChild(group);
      });

      if (actions.length) {
        actionLayer.appendChild(createSvg("rect", {
          class: "domain-bg",
          x: 38,
          y: 708,
          width: 1192,
          height: 206,
          rx: 8,
          fill: "#fff7fa",
          stroke: "#b8325d",
        }));
        actionLayer.appendChild(createSvg("text", { class: "domain-label", x: 54, y: 734 }, "动作层 ActionType"));
        actionLayer.appendChild(createSvg("text", { class: "domain-count", x: 54, y: 752 }, actions.length + " ActionType · 点击动作看参数 / 写回 / 规则"));
      }

      actions.forEach((action, index) => {
        const targetPosition = positions.get(action.targetObject);
        const col = index % 7;
        const row = Math.floor(index / 7);
        const x = 54 + col * 168;
        const y = 770 + row * 32;
        const width = 152;
        const center = { x: x + width / 2, y: y + 15 };
        if (targetPosition) {
          actionEdgeLayer.appendChild(createSvg("path", {
            class: "action-edge",
            d: pathBetween(center, targetPosition, 6),
          }));
        }
        const label = action.label || action.apiName;
        const group = createSvg("g", {
          class: \`action-node \${state.selected.kind === "action" && state.selected.id === action.apiName ? "selected" : ""}\`,
          transform: \`translate(\${x}, \${y})\`,
          "data-kind": "action",
          "data-id": action.apiName,
        });
        group.appendChild(createSvg("title", {}, label + "\\n" + action.apiName + "\\ntarget: " + (action.targetObject || "未声明")));
        group.appendChild(createSvg("rect", {
          width,
          height: 30,
          fill: "#ffe3ec",
          stroke: "#b8325d",
        }));
        group.appendChild(createSvg("text", { x: width / 2, y: 13, "text-anchor": "middle" }, shortLabel(label, 10)));
        group.appendChild(createSvg("text", { class: "api", x: width / 2, y: 25, "text-anchor": "middle" }, shortLabel(action.targetObject || action.apiName, 18)));
        group.addEventListener("click", (event) => {
          event.stopPropagation();
          selectItem("action", action.apiName);
        });
        actionLayer.appendChild(group);
      });

      if (functions.length) {
        functionLayer.appendChild(createSvg("rect", {
          class: "domain-bg",
          x: 38,
          y: 942,
          width: 1192,
          height: 120,
          rx: 8,
          fill: "#f3f0ff",
          stroke: "#6554c0",
        }));
        functionLayer.appendChild(createSvg("text", { class: "domain-label", x: 54, y: 968 }, "能力层 Function / Skill"));
        functions.forEach((fn, index) => {
          const x = 58 + (index % 5) * 234;
          const y = 986 + Math.floor(index / 5) * 34;
          const width = Math.max(150, Math.min(212, (fn.label || fn.apiName).length * 12 + 40));
          const group = createSvg("g", {
            class: \`function-node \${state.selected.kind === "function" && state.selected.id === fn.apiName ? "selected" : ""}\`,
            transform: \`translate(\${x}, \${Math.min(y, 1040)})\`,
            "data-kind": "function",
            "data-id": fn.apiName,
          });
          group.appendChild(createSvg("title", {}, (fn.label || fn.apiName) + "\\n" + fn.apiName));
          group.appendChild(createSvg("rect", {
            width,
            height: 34,
            fill: "#ece7ff",
            stroke: "#6554c0",
          }));
          group.appendChild(createSvg("text", { x: width / 2, y: 14, "text-anchor": "middle" }, shortLabel(fn.label || fn.apiName, 12)));
          group.appendChild(createSvg("text", { class: "api", x: width / 2, y: 27, "text-anchor": "middle" }, fn.kind));
          group.addEventListener("click", (event) => {
            event.stopPropagation();
            selectItem("function", fn.apiName);
          });
          functionLayer.appendChild(group);
        });
      }

      $("#graph").onclick = () => selectItem("summary", "");
    }

    function renderSummary() {
      const counts = VIEW_MODEL.counts;
      $("#inspector").innerHTML = \`
        <h2>统一活动面本体</h2>
        <div class="api-name">window.ONTOLOGY_VIEW_MODEL</div>
        <p class="desc">当前页面直接由 schema registry 生成，数据已嵌入本 HTML。选择图中的对象、关联或动作可查看详情；筛选会同步影响图谱和下方清单。</p>
        <div class="detail-block">
          <div class="detail-title">总体规模</div>
          <div class="kv"><b>ObjectType</b><span>\${counts.objects}</span></div>
          <div class="kv"><b>LinkType</b><span>\${counts.links}</span></div>
          <div class="kv"><b>ActionType</b><span>\${counts.actions}</span></div>
          <div class="kv"><b>Function/Skill</b><span>\${counts.functions}</span></div>
          <div class="kv"><b>Interface</b><span>\${counts.interfaces}</span></div>
          <div class="kv"><b>ValueType</b><span>\${counts.valueTypes}</span></div>
        </div>
        <div class="detail-block">
          <div class="detail-title">业务域</div>
          <div class="mini-list">
            \${VIEW_MODEL.domains.map((domain) => {
              const count = VIEW_MODEL.objects.filter((item) => item.domain === domain).length;
              return \`<div class="mini-row" data-domain="\${escapeHtml(domain)}"><b>\${escapeHtml(domain)}</b><br><span class="mono">\${count} ObjectType</span></div>\`;
            }).join("")}
          </div>
        </div>\`;
      $("#inspector").querySelectorAll("[data-domain]").forEach((row) => {
        row.addEventListener("click", () => {
          state.domain = row.getAttribute("data-domain");
          $("#domainFilter").value = state.domain;
          render();
        });
      });
    }

    function renderObject(item) {
      const links = VIEW_MODEL.links.filter((link) => link.from === item.apiName || link.to === item.apiName);
      const actions = VIEW_MODEL.actions.filter((action) => action.touchedObjects.includes(item.apiName));
      $("#inspector").innerHTML = \`
        <h2>\${escapeHtml(item.label)}</h2>
        <div class="api-name">\${escapeHtml(item.apiName)}</div>
        <p class="desc">\${escapeHtml(item.description || "无描述")}</p>
        <div><span class="domain-tag">\${escapeHtml(item.domain)}</span> \${item.interfaces.map((iface) => \`<span class="chip mono">\${escapeHtml(iface)}</span>\`).join(" ")}</div>
        <div class="detail-block">
          <div class="detail-title">对象定义</div>
          <div class="kv"><b>主键</b><span class="mono">\${escapeHtml(item.primaryKeys.join(", ") || "未声明")}</span></div>
          <div class="kv"><b>标题属性</b><span class="mono">\${escapeHtml(item.titleProperty || "未声明")}</span></div>
          <div class="kv"><b>属性数</b><span>\${item.properties.length}</span></div>
        </div>
        <div class="detail-block">
          <div class="detail-title">属性 <span>\${item.properties.length}</span></div>
          <div class="mini-list">
            \${item.properties.map((property) => \`
              <div class="mini-row">
                <b>\${escapeHtml(property.label || property.apiName)}</b>
                <span class="mono">\${escapeHtml(property.apiName)}</span>
                \${property.required ? '<span class="required-chip">required</span>' : ""}
                <br><span class="mono">\${escapeHtml(property.type)}</span>
                \${property.description ? \`<br>\${escapeHtml(property.description)}\` : ""}
              </div>\`).join("")}
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-title">关联 LinkType <span>\${links.length}</span></div>
          <div class="mini-list">
            \${links.map((link) => \`
              <div class="mini-row" data-kind="link" data-id="\${escapeHtml(link.apiName)}">
                <b>\${escapeHtml(link.label)}</b>
                <br><span class="mono">\${escapeHtml(link.from)} → \${escapeHtml(link.to)}</span>
                <br>\${escapeHtml(link.cardinality)} · \${escapeHtml(link.model)}
              </div>\`).join("") || '<div class="mini-row">无直接关联</div>'}
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-title">动作 ActionType <span>\${actions.length}</span></div>
          <div class="mini-list">
            \${actions.map((action) => \`
              <div class="mini-row" data-kind="action" data-id="\${escapeHtml(action.apiName)}">
                <b>\${escapeHtml(action.label)}</b>
                <br><span class="mono">\${escapeHtml(action.apiName)}</span>
              </div>\`).join("") || '<div class="mini-row">无直接动作</div>'}
          </div>
        </div>\`;
      wireInspectorRows();
    }

    function renderLink(item) {
      $("#inspector").innerHTML = \`
        <h2>\${escapeHtml(item.label)}</h2>
        <div class="api-name">\${escapeHtml(item.apiName)}</div>
        <p class="desc">\${escapeHtml(item.description || "无描述")}</p>
        <div><span class="domain-tag">\${escapeHtml(item.domain)}</span></div>
        <div class="detail-block">
          <div class="detail-title">端点</div>
          <div class="kv"><b>from</b><span><button class="tab" data-kind="object" data-id="\${escapeHtml(item.from)}">\${escapeHtml(item.fromLabel)}</button> <span class="mono">\${escapeHtml(item.from)}</span></span></div>
          <div class="kv"><b>to</b><span><button class="tab" data-kind="object" data-id="\${escapeHtml(item.to)}">\${escapeHtml(item.toLabel)}</button> <span class="mono">\${escapeHtml(item.to)}</span></span></div>
          <div class="kv"><b>基数</b><span class="mono">\${escapeHtml(item.cardinality || "未声明")}</span></div>
          <div class="kv"><b>模型</b><span class="mono">\${escapeHtml(item.model || "未声明")}</span></div>
        </div>
        <div class="detail-block">
          <div class="detail-title">方向语义</div>
          <div class="kv"><b>forward</b><span>\${escapeHtml(item.forwardLink?.label || item.forwardLink?.apiName || "未声明")}</span></div>
          <div class="kv"><b>reverse</b><span>\${escapeHtml(item.reverseLink?.label || item.reverseLink?.apiName || "未声明")}</span></div>
        </div>
        <div class="detail-block">
          <div class="detail-title">绑定细节</div>
          <pre class="mini-row mono">\${escapeHtml(JSON.stringify({
            foreignKey: item.foreignKey,
            derivedMembership: item.derivedMembership,
            nameResolution: item.nameResolution,
            resolvedEdgeShape: item.resolvedEdgeShape
          }, null, 2))}</pre>
        </div>\`;
      wireInspectorRows();
    }

    function renderAction(item) {
      $("#inspector").innerHTML = \`
        <h2>\${escapeHtml(item.label)}</h2>
        <div class="api-name">\${escapeHtml(item.apiName)}</div>
        <p class="desc">\${escapeHtml(item.description || "无描述")}</p>
        <div><span class="domain-tag">\${escapeHtml(item.domain)}</span></div>
        <div class="detail-block">
          <div class="detail-title">动作目标</div>
          <div class="kv"><b>target</b><span><button class="tab" data-kind="object" data-id="\${escapeHtml(item.targetObject)}">\${escapeHtml(item.targetLabel || item.targetObject || "未声明")}</button> <span class="mono">\${escapeHtml(item.targetObject)}</span></span></div>
          <div class="kv"><b>touches</b><span class="mono">\${escapeHtml(item.touchedObjects.join(", ") || "未声明")}</span></div>
          <div class="kv"><b>writes</b><span class="mono">\${escapeHtml(item.propertyWrites.join(", ") || "未声明")}</span></div>
        </div>
        <div class="detail-block">
          <div class="detail-title">参数 <span>\${item.parameters.length}</span></div>
          <div class="mini-list">
            \${item.parameters.map((parameter) => \`
              <div class="mini-row">
                <b>\${escapeHtml(parameter.label || parameter.apiName)}</b> <span class="mono">\${escapeHtml(parameter.apiName)}</span>
                \${parameter.required ? '<span class="required-chip">required</span>' : ""}
                <br><span class="mono">\${escapeHtml(parameter.type)}</span>
                \${parameter.description ? \`<br>\${escapeHtml(parameter.description)}\` : ""}
              </div>\`).join("")}
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-title">规则 / 写回</div>
          <pre class="mini-row mono">\${escapeHtml(JSON.stringify({
            edits: item.edits,
            rules: item.rules,
            stateTransitions: item.stateTransitions,
            strategy: item.strategy,
            submissionCriteria: item.submissionCriteria,
            targetConstraints: item.targetConstraints,
            writeback: item.writeback,
            sideEffects: item.sideEffects
          }, null, 2))}</pre>
        </div>\`;
      wireInspectorRows();
    }

    function renderFunction(item) {
      $("#inspector").innerHTML = \`
        <h2>\${escapeHtml(item.label)}</h2>
        <div class="api-name">\${escapeHtml(item.apiName)}</div>
        <p class="desc">\${escapeHtml(item.description || "无描述")}</p>
        <div><span class="domain-tag">\${escapeHtml(item.kind)}</span></div>
        <div class="detail-block">
          <div class="detail-title">参数</div>
          <div class="mini-list">
            \${item.parameters.map((parameter) => \`
              <div class="mini-row">
                <b>\${escapeHtml(parameter.label || parameter.apiName)}</b> <span class="mono">\${escapeHtml(parameter.apiName)}</span>
                \${parameter.required ? '<span class="required-chip">required</span>' : ""}
                <br><span class="mono">\${escapeHtml(parameter.type)}</span>
              </div>\`).join("") || '<div class="mini-row">无参数</div>'}
          </div>
        </div>
        <div class="detail-block">
          <div class="detail-title">返回与绑定</div>
          <pre class="mini-row mono">\${escapeHtml(JSON.stringify({
            returnType: item.returnType,
            sideEffects: item.sideEffects,
            binding: item.binding
          }, null, 2))}</pre>
        </div>\`;
    }

    function wireInspectorRows() {
      $("#inspector").querySelectorAll("[data-kind][data-id]").forEach((element) => {
        element.addEventListener("click", () => selectItem(element.getAttribute("data-kind"), element.getAttribute("data-id")));
      });
    }

    function renderInspector() {
      if (state.selected.kind === "object") return renderObject(byObject.get(state.selected.id));
      if (state.selected.kind === "link") return renderLink(byLink.get(state.selected.id));
      if (state.selected.kind === "action") return renderAction(byAction.get(state.selected.id));
      if (state.selected.kind === "function") return renderFunction(byFunction.get(state.selected.id));
      return renderSummary();
    }

    function selectItem(kind, id) {
      state.selected = { kind, id };
      renderGraphOnly();
      renderInspector();
    }

    function renderMetrics() {
      const metrics = [
        ["ObjectType", VIEW_MODEL.counts.objects],
        ["LinkType", VIEW_MODEL.counts.links],
        ["ActionType", VIEW_MODEL.counts.actions],
        ["Function/Skill", VIEW_MODEL.counts.functions],
        ["Interface", VIEW_MODEL.counts.interfaces],
        ["ValueType", VIEW_MODEL.counts.valueTypes],
      ];
      $("#metrics").innerHTML = metrics.map(([label, value]) => \`<div class="metric"><strong>\${value}</strong><span>\${label}</span></div>\`).join("");
      $("#sourceLine").innerHTML = \`
        生成时间：\${escapeHtml(VIEW_MODEL.generatedAt)}<br>
        来源：\${VIEW_MODEL.sourceFiles.map(escapeHtml).join(" · ")}
      \`;
    }

    function renderFilters() {
      $("#domainFilter").innerHTML = \`<option value="all">全部业务域</option>\${VIEW_MODEL.domains.map((domain) => \`<option value="\${escapeHtml(domain)}">\${escapeHtml(domain)}</option>\`).join("")}\`;
      $("#domainFilter").value = state.domain;
      $("#search").value = state.q;
      $("#showLinks").checked = state.showLinks;
      $("#showActions").checked = state.showActions;
      $("#showFunctions").checked = state.showFunctions;
    }

    function tableRows() {
      if (state.table === "objects") return filteredObjects();
      if (state.table === "links") {
        const objectSet = new Set(filteredObjects().map((item) => item.apiName));
        return VIEW_MODEL.links.filter((item) => {
          if (state.domain !== "all" && item.domain !== state.domain) return false;
          if (state.q && !searchableText(item).includes(state.q)) return false;
          return objectSet.has(item.from) || objectSet.has(item.to);
        });
      }
      if (state.table === "actions") {
        return VIEW_MODEL.actions.filter((item) => {
          if (state.domain !== "all" && item.domain !== state.domain) return false;
          if (state.q && !searchableText(item).includes(state.q)) return false;
          return true;
        });
      }
      return VIEW_MODEL.functions.filter((item) => {
        if (state.domain !== "all" && item.domain !== state.domain) return false;
        if (state.q && !searchableText(item).includes(state.q)) return false;
        return true;
      });
    }

    function renderTabs() {
      const tabs = [
        ["objects", "对象"],
        ["links", "关联"],
        ["actions", "动作"],
        ["functions", "能力"],
      ];
      $("#tabs").innerHTML = tabs.map(([key, label]) => \`<button class="tab \${state.table === key ? "active" : ""}" data-tab="\${key}">\${label}</button>\`).join("");
      $("#tabs").querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", () => {
          state.table = button.getAttribute("data-tab");
          renderTable();
          renderTabs();
        });
      });
    }

    function renderTable() {
      const rows = tableRows();
      $("#tableMeta").textContent = \`\${rows.length} rows · \${state.table}\`;
      if (state.table === "objects") {
        $("#dataTable").innerHTML = \`
          <thead><tr><th>displayName</th><th>apiName</th><th>domain</th><th>pk</th><th>properties</th><th>interfaces</th></tr></thead>
          <tbody>\${rows.map((item) => \`
            <tr data-kind="object" data-id="\${escapeHtml(item.apiName)}">
              <td><b>\${escapeHtml(item.label)}</b></td>
              <td class="mono">\${escapeHtml(item.apiName)}</td>
              <td>\${escapeHtml(item.domain)}</td>
              <td class="mono">\${escapeHtml(item.primaryKeys.join(", "))}</td>
              <td>\${item.properties.length}</td>
              <td class="mono">\${escapeHtml(item.interfaces.join(", "))}</td>
            </tr>\`).join("")}</tbody>\`;
      } else if (state.table === "links") {
        $("#dataTable").innerHTML = \`
          <thead><tr><th>displayName</th><th>apiName</th><th>from</th><th>to</th><th>cardinality</th><th>model</th></tr></thead>
          <tbody>\${rows.map((item) => \`
            <tr data-kind="link" data-id="\${escapeHtml(item.apiName)}">
              <td><b>\${escapeHtml(item.label)}</b></td>
              <td class="mono">\${escapeHtml(item.apiName)}</td>
              <td class="mono">\${escapeHtml(item.from)}</td>
              <td class="mono">\${escapeHtml(item.to)}</td>
              <td class="mono">\${escapeHtml(item.cardinality)}</td>
              <td class="mono">\${escapeHtml(item.model)}</td>
            </tr>\`).join("")}</tbody>\`;
      } else if (state.table === "actions") {
        $("#dataTable").innerHTML = \`
          <thead><tr><th>displayName</th><th>apiName</th><th>target</th><th>parameters</th><th>writes</th></tr></thead>
          <tbody>\${rows.map((item) => \`
            <tr data-kind="action" data-id="\${escapeHtml(item.apiName)}">
              <td><b>\${escapeHtml(item.label)}</b></td>
              <td class="mono">\${escapeHtml(item.apiName)}</td>
              <td class="mono">\${escapeHtml(item.targetObject)}</td>
              <td>\${item.parameters.length}</td>
              <td class="mono">\${escapeHtml(item.propertyWrites.join(", "))}</td>
            </tr>\`).join("")}</tbody>\`;
      } else {
        $("#dataTable").innerHTML = \`
          <thead><tr><th>displayName</th><th>apiName</th><th>kind</th><th>parameters</th><th>binding</th></tr></thead>
          <tbody>\${rows.map((item) => \`
            <tr data-kind="function" data-id="\${escapeHtml(item.apiName)}">
              <td><b>\${escapeHtml(item.label)}</b></td>
              <td class="mono">\${escapeHtml(item.apiName)}</td>
              <td class="mono">\${escapeHtml(item.kind)}</td>
              <td>\${item.parameters.length}</td>
              <td class="mono">\${escapeHtml(item.binding ? [item.binding.module, item.binding.function].filter(Boolean).join(".") : "")}</td>
            </tr>\`).join("")}</tbody>\`;
      }
      $("#dataTable").querySelectorAll("[data-kind][data-id]").forEach((row) => {
        row.addEventListener("click", () => selectItem(row.getAttribute("data-kind"), row.getAttribute("data-id")));
      });
    }

    function renderGraphOnly() {
      drawGraph();
    }

    function render() {
      renderGraphOnly();
      renderInspector();
      renderTabs();
      renderTable();
    }

    function download(name, content, type) {
      const blob = new Blob([content], { type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    }

    function csvEscape(value) {
      const text = String(value ?? "");
      if (/[",\\n]/.test(text)) return \`"\${text.replace(/"/g, '""')}"\`;
      return text;
    }

    function exportCsv() {
      const rows = tableRows();
      const flatRows = rows.map((row) => {
        if (state.table === "objects") return {
          displayName: row.label,
          apiName: row.apiName,
          domain: row.domain,
          primaryKeys: row.primaryKeys.join("|"),
          propertyCount: row.properties.length,
          interfaces: row.interfaces.join("|"),
        };
        if (state.table === "links") return {
          displayName: row.label,
          apiName: row.apiName,
          from: row.from,
          to: row.to,
          cardinality: row.cardinality,
          model: row.model,
        };
        if (state.table === "actions") return {
          displayName: row.label,
          apiName: row.apiName,
          targetObject: row.targetObject,
          parameters: row.parameters.map((item) => item.apiName).join("|"),
          propertyWrites: row.propertyWrites.join("|"),
          touchedObjects: row.touchedObjects.join("|"),
        };
        return {
          displayName: row.label,
          apiName: row.apiName,
          kind: row.kind,
          parameters: row.parameters.map((item) => item.apiName).join("|"),
          binding: row.binding ? [row.binding.module, row.binding.function].filter(Boolean).join(".") : "",
        };
      });
      const headers = Object.keys(flatRows[0] || { empty: "" });
      const csv = [headers.join(","), ...flatRows.map((row) => headers.map((header) => csvEscape(row[header])).join(","))].join("\\n");
      download(\`ontology-\${state.table}.csv\`, csv, "text/csv;charset=utf-8");
    }

    function bindEvents() {
      $("#search").addEventListener("input", (event) => {
        state.q = event.target.value.trim().toLowerCase();
        render();
      });
      $("#domainFilter").addEventListener("change", (event) => {
        state.domain = event.target.value;
        render();
      });
      $("#showLinks").addEventListener("change", (event) => {
        state.showLinks = event.target.checked;
        render();
      });
      $("#showActions").addEventListener("change", (event) => {
        state.showActions = event.target.checked;
        render();
      });
      $("#showFunctions").addEventListener("change", (event) => {
        state.showFunctions = event.target.checked;
        render();
      });
      $("#exportJson").addEventListener("click", () => download("unified-activity-ontology-view-model.json", JSON.stringify(VIEW_MODEL, null, 2), "application/json;charset=utf-8"));
      $("#exportCsv").addEventListener("click", exportCsv);
    }

    renderMetrics();
    renderFilters();
    bindEvents();
    render();
  </script>
</body>
</html>`;
}

const viewModel = buildViewModel();
fs.writeFileSync(outputPath, htmlTemplate(viewModel), "utf8");
console.log(`Generated ${outputPath}`);
console.log(
  JSON.stringify(
    {
      objects: viewModel.counts.objects,
      links: viewModel.counts.links,
      actions: viewModel.counts.actions,
      functions: viewModel.counts.functions,
      output: outputPath,
    },
    null,
    2
  )
);
