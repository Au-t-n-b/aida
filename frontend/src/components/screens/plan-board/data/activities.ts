/* AIDA 排期 · 活动依赖图数据
 * 由 data/activities.json 转为类型化 TS（对齐 B 的 satisfies 数据约定，免改 tsconfig 开 resolveJsonModule）。
 * 源: 交付项目-整体梳理\01_交付背景\00_背景文档\ZJYD 测试项目ww_交付计划.xlsx · 81 活动 · schema v1
 */
export type Activity = {
  id: string;
  name: string;
  parentId: string | null;
  level: number;
  slaDays: number | null;
  depNames: string[];
  batch: number | null;
  remoteTeam: string | null;
  siteTeam: string | null;
  owner: string | null;
  constraintSource: string;
};

export const ACTIVITIES = [
  {
    "id": "2.0",
    "name": "L1机房准备",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "站"
  },
  {
    "id": "2.3",
    "name": "机房改造实施",
    "parentId": "2.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "未指定责任人",
    "constraintSource": "站"
  },
  {
    "id": "_seq.2",
    "name": "机房改造液冷完成",
    "parentId": null,
    "level": 3,
    "slaDays": 7,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": null,
    "constraintSource": "站"
  },
  {
    "id": "3.0",
    "name": "工程勘测",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "3.1",
    "name": "现场勘测",
    "parentId": "3.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "站"
  },
  {
    "id": "3.2",
    "name": "远程视频辅助",
    "parentId": "3.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "侯克照 00578443",
    "constraintSource": "人"
  },
  {
    "id": "3.3",
    "name": "输出工勘报告",
    "parentId": "3.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "现场勘测",
      "远程视频辅助"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "侯克照 00578443",
    "constraintSource": "人"
  },
  {
    "id": "3.4",
    "name": "工程勘测报告评审",
    "parentId": "3.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "输出工勘报告"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "4.0",
    "name": "建模仿真",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "4.1",
    "name": "信息分析与确认",
    "parentId": "4.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "张志峰 00486208",
    "constraintSource": "人"
  },
  {
    "id": "4.2",
    "name": "建模仿真设计",
    "parentId": "4.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "信息分析与确认"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "张志峰 00486208",
    "constraintSource": "人"
  },
  {
    "id": "4.3",
    "name": "建模仿真初稿评审",
    "parentId": "4.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "建模仿真设计"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "张志峰 00486208",
    "constraintSource": "人"
  },
  {
    "id": "4.4",
    "name": "建模仿真终稿输出",
    "parentId": "4.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "建模仿真初稿评审"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "张志峰 00486208",
    "constraintSource": "人"
  },
  {
    "id": "5.0",
    "name": "低阶设计",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "5.1",
    "name": "集群LLD设计",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "工程勘测报告评审",
      "建模仿真终稿输出"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "张宏枫  00933673",
    "constraintSource": "人"
  },
  {
    "id": "5.2",
    "name": "计算子系统LLD设计",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "工程勘测报告评审",
      "建模仿真终稿输出"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "张宏枫  00933673",
    "constraintSource": "人"
  },
  {
    "id": "5.3",
    "name": "网络子系统LLD设计",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "工程勘测报告评审",
      "建模仿真终稿输出"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "网络专家",
    "constraintSource": "人"
  },
  {
    "id": "5.4",
    "name": "存储子系统LLD设计",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "工程勘测报告评审",
      "建模仿真终稿输出"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "朱建忠 00867300",
    "constraintSource": "人"
  },
  {
    "id": "5.6",
    "name": "集群验收方案设计",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "工程勘测报告评审",
      "建模仿真终稿输出"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "叶志勇 00817972",
    "constraintSource": "人"
  },
  {
    "id": "5.7",
    "name": "低阶设计评审",
    "parentId": "5.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "集群LLD设计",
      "计算子系统LLD设计",
      "网络子系统LLD设计",
      "存储子系统LLD设计",
      "集群验收方案设计"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "13.0",
    "name": "工具准备",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "13.1",
    "name": "工程安装调测工具准备",
    "parentId": "13.0",
    "level": 3,
    "slaDays": 10,
    "depNames": [],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "6.0",
    "name": "到货",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "货"
  },
  {
    "id": "6.4",
    "name": "通用线缆到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 2,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "6.9",
    "name": "网络到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 4,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "6.7",
    "name": "通算到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 3,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "6.5",
    "name": "灵衢线缆到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 6,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "_seq.27",
    "name": "总线设备柜到货(含开箱验货)",
    "parentId": null,
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": null,
    "constraintSource": "货"
  },
  {
    "id": "6.2",
    "name": "计算柜到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "6.11",
    "name": "转运与设备静置",
    "parentId": "6.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "总线设备柜到货（含开箱验货）",
      "计算柜到货（含开箱验货）"
    ],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "人"
  },
  {
    "id": "6.8",
    "name": "存储到货（含开箱验货）",
    "parentId": "6.0",
    "level": 2,
    "slaDays": null,
    "depNames": [],
    "batch": 7,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "货"
  },
  {
    "id": "7.0",
    "name": "工程安装",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.1",
    "name": "机房洁净度测试",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 10,
    "depNames": [
      "机房改造实施"
    ],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "站"
  },
  {
    "id": "7.2",
    "name": "综合布线与成端-通用线缆",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 4,
    "depNames": [
      "低阶设计评审",
      "通用线缆到货（含开箱验货）",
      "机房洁净度测试"
    ],
    "batch": 2,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "人"
  },
  {
    "id": "7.13",
    "name": "网络设备安装",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "机房改造实施",
      "低阶设计评审",
      "网络到货（含开箱验货）"
    ],
    "batch": 4,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.14",
    "name": "网络设备上电",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "网络设备安装",
      "综合布线与成端-通用线缆"
    ],
    "batch": 4,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.15",
    "name": "网络设备硬件验收",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "网络设备上电"
    ],
    "batch": 4,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.7",
    "name": "通算服务器安装",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "机房改造实施",
      "低阶设计评审",
      "通算到货（含开箱验货）"
    ],
    "batch": 3,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.8",
    "name": "通算设备上电",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "综合布线与成端-通用线缆",
      "通算服务器安装"
    ],
    "batch": 3,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.9",
    "name": "通算设备硬件验收",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "通算设备上电"
    ],
    "batch": 3,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.3",
    "name": "综合布线与成端-灵衢线缆",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 12,
    "depNames": [
      "低阶设计评审",
      "灵衢线缆到货（含开箱验货）",
      "机房洁净度测试"
    ],
    "batch": 6,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "人"
  },
  {
    "id": "7.1",
    "name": "存储设备安装",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "机房改造实施",
      "低阶设计评审",
      "存储到货（含开箱验货）"
    ],
    "batch": 7,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "未指定责任人",
    "constraintSource": "人"
  },
  {
    "id": "7.11",
    "name": "存储设备上电",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "存储设备安装",
      "综合布线与成端-通用线缆"
    ],
    "batch": 7,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.12",
    "name": "存储设备硬件验收",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "存储设备上电"
    ],
    "batch": 7,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.44",
    "name": "总线设备柜安装",
    "parentId": null,
    "level": 3,
    "slaDays": 1,
    "depNames": [],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.45",
    "name": "总线设备柜设备上电",
    "parentId": null,
    "level": 3,
    "slaDays": 2,
    "depNames": [],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.46",
    "name": "总线设备柜设备验收",
    "parentId": null,
    "level": 3,
    "slaDays": 7,
    "depNames": [],
    "batch": 5,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.19",
    "name": "液冷计算柜安装",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 1,
    "depNames": [
      "机房改造实施",
      "低阶设计评审",
      "转运与设备静置"
    ],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.2",
    "name": "液冷计算柜设备上电",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "液冷计算柜安装",
      "综合布线与成端-灵衢线缆"
    ],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "7.21",
    "name": "液冷计算柜验收",
    "parentId": "7.0",
    "level": 3,
    "slaDays": 7,
    "depNames": [
      "液冷计算柜设备上电"
    ],
    "batch": 5,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.0",
    "name": "单机调测",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.1",
    "name": "基础网络配置",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "网络设备上电"
    ],
    "batch": 4,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.7",
    "name": "网络子系统部署调测",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "基础网络配置"
    ],
    "batch": 4,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.15",
    "name": "网络子系统验证",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "网络子系统部署调测"
    ],
    "batch": 4,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.3",
    "name": "设备硬装初始化-通算服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "通算设备上电"
    ],
    "batch": 3,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.9",
    "name": "计算子系统部署调测-通算服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "设备硬装初始化-通算服务器"
    ],
    "batch": 3,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.56",
    "name": "计算子系统验证-通算服务器",
    "parentId": null,
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "计算子系统部署调测-通算服务器"
    ],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.4",
    "name": "设备硬装初始化-存储服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "存储设备上电"
    ],
    "batch": 7,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.58",
    "name": "设备硬装初始化-灵衢网络",
    "parentId": null,
    "level": 3,
    "slaDays": 2,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.11",
    "name": "存储子系统部署调测",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "设备硬装初始化-存储服务器"
    ],
    "batch": 7,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.14",
    "name": "存储子系统验证",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "存储子系统部署调测"
    ],
    "batch": 7,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.2",
    "name": "设备硬装初始化-智算服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "液冷计算柜设备上电"
    ],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.6",
    "name": "智算硬件压测",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "设备硬装初始化-智算服务器"
    ],
    "batch": 5,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.8",
    "name": "计算子系统部署调测-智算服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "设备硬装初始化-智算服务器"
    ],
    "batch": 5,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "8.12",
    "name": "计算子系统验证-智算服务器",
    "parentId": "8.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "计算子系统部署调测-智算服务器"
    ],
    "batch": 5,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.65",
    "name": "计算子系统部署调测-灵衢网络",
    "parentId": null,
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "设备硬装初始化-灵衢网络"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "_seq.66",
    "name": "计算子系统验证-灵衢网络",
    "parentId": null,
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "计算子系统部署调测-灵衢网络"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.2",
    "name": "网络管理系统对接",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "网络子系统部署调测"
    ],
    "batch": 4,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.3",
    "name": "存储管理系统对接",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "存储子系统部署调测"
    ],
    "batch": 7,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.1",
    "name": "计算管理系统对接",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "计算子系统部署调测-智算服务器"
    ],
    "batch": 5,
    "remoteTeam": "R",
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.0",
    "name": "集群调测",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.4",
    "name": "线序及光链路质量排查",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "计算子系统部署调测-灵衢网络",
      "存储子系统部署调测",
      "网络子系统部署调测",
      "计算子系统部署调测-智算服务器",
      "计算子系统部署调测-通算服务器"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.5",
    "name": "综合布线整改",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 4,
    "depNames": [
      "线序及光链路质量排查"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.8",
    "name": "集群性能调优",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "集群系统集成测试"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.6",
    "name": "集群通信配置测试",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "计算子系统验证-智算服务器",
      "计算子系统验证-灵衢网络",
      "存储子系统验证",
      "网络子系统验证",
      "计算子系统验证-通算服务器",
      "综合布线整改"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "9.7",
    "name": "集群系统集成测试",
    "parentId": "9.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "集群通信配置测试"
    ],
    "batch": null,
    "remoteTeam": "R",
    "siteTeam": "S",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "12.0",
    "name": "验收测试",
    "parentId": null,
    "level": 1,
    "slaDays": null,
    "depNames": [],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": null,
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "12.1",
    "name": "客户集群验收",
    "parentId": "12.0",
    "level": 3,
    "slaDays": 10,
    "depNames": [
      "集群系统集成测试"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "12.2",
    "name": "输出验收报告",
    "parentId": "12.0",
    "level": 3,
    "slaDays": 5,
    "depNames": [
      "客户集群验收"
    ],
    "batch": null,
    "remoteTeam": "S",
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "12.3",
    "name": "验收报告沟通",
    "parentId": "12.0",
    "level": 3,
    "slaDays": 3,
    "depNames": [
      "输出验收报告"
    ],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "胡德华 00952466",
    "constraintSource": "人"
  },
  {
    "id": "12.4",
    "name": "移交",
    "parentId": "12.0",
    "level": 3,
    "slaDays": 2,
    "depNames": [
      "验收报告沟通"
    ],
    "batch": null,
    "remoteTeam": null,
    "siteTeam": "R",
    "owner": "汪伟 00468566",
    "constraintSource": "人"
  }
] satisfies Activity[];
