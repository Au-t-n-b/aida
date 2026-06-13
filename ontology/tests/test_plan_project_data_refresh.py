import csv
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook


ONTOLOGY_DIR = Path(__file__).resolve().parents[1]
if str(ONTOLOGY_DIR) not in sys.path:
    sys.path.insert(0, str(ONTOLOGY_DIR))


def _write_book(path: Path, rows: list[list[object]], *, sheet: str = "sheet0") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def _create_structured_project_data(root: Path) -> None:
    _write_book(
        root / "01_活动定义" / "A3-液冷-活动定义.xlsx",
        [
            ["ACTIVITY_ID", "ACTIVITY_NAME", "SLA"],
            ["2.3", "机房改造实施", "5"],
        ],
    )
    _write_book(
        root / "02_活动依赖" / "A3-液冷-活动依赖.xlsx",
        [
            [
                "REL_ID",
                "STAGE",
                "FROM_STAGE",
                "DEST_STAGE",
                "VERSION",
                "PROJECT_ID",
                "PROJECT_SCENE",
                "PRODUCT_FORM",
                "COOLING_METHOD",
                "CATEGORY",
                "PRODUCT_GROUP",
                "FROM_ACTIVITY_ID",
                "FROM_ACTIVITY_NAME",
                "DEST_ACTIVITY_ID",
                "DEST_ACTIVITY_NAME",
            ],
            ["r1", "1", "1", "1", "1", "p1", "集群集成", "A3", "liquid", "", "", "2.1", "机房准备", "2.3", "机房改造实施"],
        ],
    )
    _write_book(
        root / "04_计划基线" / "计划基线0609.xlsx",
        [
            ["序号", "一级活动", "二级活动", "SS", "SF", "FS", "FF", "所属阶段", "备注", "标准工时", "极限工时", "工时备注", "分工", "风险判断逻辑", "风险名称", "风险描述", "风险影响", "风险应对预案", "预案对应的责任人"],
            [],
            ["2.3", "L1机房准备", "机房改造实施", "", "", "", "", "机房准备", "", "10", "6", "", "施工", "", "工期风险", "低于标准工期", "影响上电", "补充施工队", "PM"],
        ],
        sheet="集群集成 + A3液冷场景活动&依赖&工时(1014）",
    )
    _write_book(
        root / "05_机房机柜信息" / "机房机柜信息表.xlsx",
        [
            ["PoD名称", "机房名称", "计算柜", "总线柜", "参数面Leaf柜", "样本面Leaf柜", "业务面Leaf柜", "管理面柜"],
            ["B2DH401-POD01", "B2DH401", "C01", "B01", "", "", "", "M01"],
        ],
        sheet="Sheet1",
    )
    _write_book(
        root / "06_到货表" / "04 JD三期_A3液冷到货表_260309.xlsx",
        [
            ["ID", "管理单元", "设备类型", "型号", "总配置", "单位", "数量", "到货日期", "备注", "机房", "PoD"],
            ["1", "B2DH401-POD01", "计算柜", "Atlas 900 A3", "48卡", "柜", "12", "2026-01-10", "", "B2DH401", "POD01"],
        ],
        sheet="JD三期",
    )
    _write_book(
        root / "07_项目人员信息" / "03 项目人员信息表_JD_0114.xlsx",
        [
            ["姓名", "工号", "角色", "备注"],
            ["张三", "001", "PD", "项目经理"],
        ],
        sheet="Sheet1",
    )
    _write_book(
        root / "08_施工队伍信息" / "施工队伍信息.xlsx",
        [
            ["队伍编号", "人数", "经验等级", "在场状态"],
            ["1", "8", "经验充分", "在场"],
        ],
        sheet="Sheet1",
    )
    _write_book(
        root / "09_批次信息" / "批次信息.xlsx",
        [
            ["批次名", "上电目标日期", "上线目标日期", "该批包含的PoD"],
            ["批次1", "2026-01-21", "2026-02-04", "B2DH401-POD01"],
        ],
        sheet="Sheet1",
    )
    _write_book(
        root / "10_输出文件" / "交付计划表.xlsx",
        [
            [
                "ID",
                "TODO_ID",
                "SERIAL_NUMBER",
                "ACTIVITY_ID",
                "ACTIVITY_NAME",
                "TASK_RANK",
                "PARENT_ID",
                "PROJECT_ID",
                "INSTRUCTION",
                "FORMAT_INSTRUCTION",
                "SRC_AGENT",
                "TARGET_AGENT",
                "START_DATE",
                "END_DATE",
                "ACTUAL_START_DATE",
                "ACTUAL_END_DATE",
                "STATUS",
                "PROCESS",
                "PRINCIPAL",
                "OWNER",
                "SCENE",
                "CREATED_BY",
                "CREATED_AT",
                "UPDATED_BY",
                "UPDATED_AT",
                "GROUP_ID",
                "RAW_EQUIPMENT_LIST",
                "REMARK",
                "MANAGEMENT_UNIT",
                "MANUAL_PROCESS",
                "REAL_MANAGEMENT_UNIT",
            ],
            ["1", "", "row-1", "2.3", "机房改造实施", "1", "-1", "p1", "", "", "remote", "onsite", "2026-01-01", "2026-01-05", "", "", "未开始", "", "张三", "张三", "", "", "", "", "", "", "Atlas", "", "B2DH401-POD01", "", "B2DH401-POD01"],
        ],
    )
    _write_book(
        root / "11_风险信息" / "风险信息.xlsx",
        [
            ["id", "modified", "project_id", "issue_id", "name", "rule_id", "description", "level", "owner", "effect", "progress", "status"],
            ["r1", "1", "p1", "issue-1", "排期风险", "rule-1", "资源不足", "中", "张三", "影响上电", "新增", "打开"],
        ],
    )


class PlanProjectDataRefreshTests(unittest.TestCase):
    def test_structured_project_data_package_builds_auxiliary_plan_snapshots(self):
        refresh = importlib.import_module("refresh_plan_project_data")
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _create_structured_project_data(root)

            bundle = refresh.load_source_bundle(root)
            auxiliary = refresh.build_auxiliary_plan_rows(bundle, "京东")

        self.assertEqual(len(auxiliary["EquipmentRoom"]), 1)
        self.assertEqual(auxiliary["EquipmentRoom"][0]["roomKey"], "京东::room::B2DH401")
        self.assertEqual(auxiliary["EquipmentRoom"][0]["podKeys"], "B2DH401-POD01")
        self.assertIn("计算柜", json.loads(auxiliary["EquipmentRoom"][0]["roomConditionJson"])[0]["cabinets"])
        self.assertEqual(auxiliary["EquipmentArrivalItem"][0]["arrivalItemKey"], "京东::arrival::1")
        self.assertEqual(auxiliary["DeliveryBatch"][0]["batchKey"], "京东::batch::批次1")
        self.assertEqual(auxiliary["ProjectParticipant"][0]["partyType"], "PERSON")
        self.assertTrue(any(row["partyName"] == "施工队伍" for row in auxiliary["ProjectParticipant"]))
        self.assertEqual(auxiliary["ResourceTeam"][0]["participantKey"], "京东::participant::construction")
        self.assertEqual(auxiliary["ActivityTemplate"][0]["baseStandardSlaDays"], "10")
        self.assertEqual(auxiliary["ScheduleRisk"][0]["riskKey"], "京东::schedule_risk::r1")

    def test_auxiliary_plan_snapshots_are_written_with_schema_columns(self):
        refresh = importlib.import_module("refresh_plan_project_data")
        rows = {
            "EquipmentArrivalItem": [
                {
                    "arrivalItemKey": "京东::arrival::1",
                    "projectKey": "京东",
                    "itemId": "1",
                    "equipmentType": "计算柜",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            refresh.write_auxiliary_plan_csvs(output_dir, rows)
            csv_path = output_dir / "equipment_arrival_items_jd.csv"
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                written = list(reader)

        self.assertIn("arrivalItemKey", reader.fieldnames)
        self.assertIn("projectKey", reader.fieldnames)
        self.assertEqual(written[0]["equipmentType"], "计算柜")

    def test_milestone_refresh_adds_schema_columns_for_existing_csv(self):
        refresh = importlib.import_module("refresh_plan_project_data")
        old_fields = [
            "milestoneKey",
            "projectKey",
            "projectName",
            "scopeType",
            "scopeKey",
            "milestoneType",
            "milestoneName",
            "plannedDate",
            "actualDate",
            "anchorDate",
            "sourceFile",
            "description",
            "directionRole",
            "dependencyMilestoneTypes",
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "Milestone.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=old_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "milestoneKey": "京东::PROJECT::GLOBAL::POWER_ON",
                        "projectKey": "京东",
                        "projectName": "京东",
                        "scopeType": "PROJECT",
                        "scopeKey": "GLOBAL",
                        "milestoneType": "POWER_ON",
                    }
                )
                writer.writerow(
                    {
                        "milestoneKey": "浙江移动::PROJECT::GLOBAL::POWER_ON",
                        "projectKey": "浙江移动",
                        "projectName": "浙江移动",
                        "scopeType": "PROJECT",
                        "scopeKey": "GLOBAL",
                        "milestoneType": "POWER_ON",
                    }
                )

            refresh.update_milestone_csv(
                csv_path,
                "京东",
                {
                    "project": {
                        "ROOM_IMPLEMENTATION_DONE": "2026-01-05",
                        "ARRIVAL": "2026-01-10",
                        "POWER_ON": "2026-01-21",
                        "CLUSTER_DEBUG": "2026-02-01",
                    },
                    "podPowerOn": {"B2DH401-POD01": "2026-01-21"},
                },
            )
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

        self.assertIn("anchorPriority", reader.fieldnames)
        self.assertIn("anchorKind", reader.fieldnames)
        self.assertTrue(rows)
        self.assertTrue(all(row["anchorPriority"] == "0" for row in rows))

    def test_generic_csv_table_reader_returns_non_milestone_objects(self):
        datasource_bindings = importlib.import_module("datasource_bindings")
        data_connector = importlib.import_module("data_connector")
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            csv_path = base / "equipment_arrival_items_jd.csv"
            csv_path.write_text(
                "arrivalItemKey,projectKey,itemId,equipmentType\n"
                "京东::arrival::1,京东,1,计算柜\n"
                "浙江::arrival::1,浙江,1,交换机\n",
                encoding="utf-8-sig",
            )
            bindings_path = base / "datasource-bindings.yaml"
            bindings_path.write_text(
                """
version: 1
datasources:
  - id: plan-equipment-arrival-jd
    type: csv
    path: equipment_arrival_items_jd.csv
    projectId: 京东
    projectKey: 京东
objectTypes:
  EquipmentArrivalItem:
    reader: csv_table
    derived: false
    writable: true
    sources:
      - plan-equipment-arrival-jd
""".lstrip(),
                encoding="utf-8",
            )
            registry = datasource_bindings.load_datasource_bindings(bindings_path)
            original_supported = data_connector.SUPPORTED_OBJECT_TYPES
            original_loader = data_connector.load_datasource_bindings
            original_base_dir = data_connector.BASE_DIR
            try:
                data_connector.SUPPORTED_OBJECT_TYPES = {"EquipmentArrivalItem"}
                data_connector.load_datasource_bindings = lambda: registry
                data_connector.BASE_DIR = base

                rows = data_connector.get_object_data("EquipmentArrivalItem", project_id="京东")
            finally:
                data_connector.SUPPORTED_OBJECT_TYPES = original_supported
                data_connector.load_datasource_bindings = original_loader
                data_connector.BASE_DIR = original_base_dir

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["arrivalItemKey"], "京东::arrival::1")
        self.assertEqual(rows[0]["equipmentType"], "计算柜")

    def test_auxiliary_plan_types_are_backing_data(self):
        dataset_service = importlib.import_module("dataset_service")
        dolt_mirror = importlib.import_module("dolt_mirror")

        expected = {
            "EquipmentRoom",
            "EquipmentArrivalItem",
            "DeliveryBatch",
            "ProjectParticipant",
            "ResourceTeam",
            "ActivityTemplate",
            "ScheduleRisk",
        }

        self.assertTrue(expected.issubset(dataset_service.supported_object_backing_data()))
        self.assertTrue(expected.issubset(set(dolt_mirror.supported_mirror_object_types())))


if __name__ == "__main__":
    unittest.main()
