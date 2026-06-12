"""根据 LLD + 公共配置生成 cfg 与 ztp.ini — 对齐 CfgFileCreater（本地模板）。"""

from __future__ import annotations

import os
import time
from pathlib import Path

from data_struct import CfgData


class OfflineCfgFileCreater:
    def __init__(
        self,
        cfg_data_list: list[CfgData],
        common_dict: dict,
        replace_label: dict,
        l1_template: Path,
        l2_template: Path,
        output_root: Path,
    ):
        self.cfgDataList = cfg_data_list
        self.L1_template = l1_template
        self.L2_template = l2_template
        self.replaceLabel = replace_label
        self.common_dict = common_dict
        self.output_root = output_root
        self.outputPath = ""
        self.outputPathL1 = ""
        self.outputPathL2 = ""
        self.ztp_content = ""
        self.ztpTimeSn = ""

    def write_data_to_cfg(self) -> Path:
        self._create_output_dir()
        file_type_num = 1
        software_version_value = self.common_dict.get("{{softwareVersion}}")
        patch_version_value = self.common_dict.get("{{patchVersion}}")
        if software_version_value:
            file_type_num += 1
        if patch_version_value:
            file_type_num += 1

        i = 0
        for cfg_data in self.cfgDataList:
            input_file = self.L2_template
            cfg_file_name = cfg_data.methIP + ".cfg"
            output_file = self.outputPathL2 / cfg_file_name
            replace_dict = {
                self.replaceLabel["deviceName"]: cfg_data.deviceName,
                self.replaceLabel["esn"]: cfg_data.esn,
                self.replaceLabel["location"]: cfg_data.location,
                self.replaceLabel["methIP"]: cfg_data.methIP,
                self.replaceLabel["gateway"]: cfg_data.gateway,
                self.replaceLabel["subMask"]: cfg_data.subMask,
                self.replaceLabel["switchId"]: cfg_data.switchId,
                self.replaceLabel["switchLevel"]: cfg_data.level,
                self.replaceLabel["bgpAs"]: cfg_data.bgpAs,
                self.replaceLabel["loopback0"]: cfg_data.loopback0,
                self.replaceLabel["loopback1"]: cfg_data.loopback1,
            }
            if cfg_data.level == "1":
                input_file = self.L1_template
                output_file = self.outputPathL1 / cfg_file_name
                replace_dict[self.replaceLabel["loopback2"]] = cfg_data.loopback2
                replace_dict[self.replaceLabel["loopback3"]] = cfg_data.loopback3
                replace_dict[self.replaceLabel["loopback4"]] = cfg_data.loopback4
                replace_dict[self.replaceLabel["loopback5"]] = cfg_data.loopback5
                replace_dict[self.replaceLabel["loopback6"]] = cfg_data.loopback6

            full_replace_dict = {**self.common_dict, **replace_dict}
            self._replace_text_in_file(input_file, output_file, full_replace_dict)

            ztp_section = (
                f"[DEVICE_TYPE_{i} DESCRIPTION]\n"
                f"LOCATION=\n"
                f"ESN={cfg_data.esn}\n"
                f"MAC=\n"
                f"*FILETYPENUM={file_type_num}\n"
                f"*FILENAME_1={cfg_file_name}\n"
                f"*TYPE_1=CFG\n"
                f"SHA256_1=\n"
            )
            if file_type_num == 1:
                ztp_section += "\n"
            elif file_type_num == 2:
                if software_version_value is not None:
                    ztp_section += f"*FILENAME_2={software_version_value}.cc\n*TYPE_2=SOFTWARE\n\n"
                else:
                    ztp_section += f"*FILENAME_2={patch_version_value}.PAT\n*TYPE_2=PAT\n\n"
            elif file_type_num == 3:
                ztp_section += f"*FILENAME_2={software_version_value}.cc\n*TYPE_2=SOFTWARE\n"
                ztp_section += f"*FILENAME_3={patch_version_value}.PAT\n*TYPE_3=PAT\n\n"
            i += 1
            self.ztp_content += ztp_section

        ztp_global = (
            f"[GLOBAL CONFIG]\n"
            f"*FILESERVER=sftp://username:password@localhost:port\n"
            f"*TIME_SN={self.ztpTimeSn}\n"
            f"*DEVICE_TYPE_NUM={i}\n\n"
        )
        self.ztp_content = ztp_global + self.ztp_content
        ztp_file = self.outputPath / "ztp.ini"
        ztp_file.write_text(self.ztp_content, encoding="utf-8")
        return self.outputPath

    def _create_output_dir(self) -> None:
        local_time = time.localtime(time.time())
        timestamp = (
            f"{local_time.tm_year}{local_time.tm_mon:02d}{local_time.tm_mday:02d}_"
            f"{local_time.tm_hour:02d}{local_time.tm_min:02d}{local_time.tm_sec:02d}"
        )
        self.ztpTimeSn = (
            f"{local_time.tm_year}{local_time.tm_mon:02d}{local_time.tm_mday:02d}"
            f"{local_time.tm_hour:02d}{local_time.tm_min:02d}{local_time.tm_sec:02d}"
        )
        self.outputPath = self.output_root / timestamp
        self.outputPath.mkdir(parents=True, exist_ok=True)
        self.outputPathL1 = self.outputPath / "L1"
        self.outputPathL2 = self.outputPath / "L2"
        self.outputPathL1.mkdir()
        self.outputPathL2.mkdir()

    def _replace_text_in_file(self, input_file: Path, output_file: Path, replace_dict: dict) -> None:
        lines = input_file.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            begin_match = line.strip().startswith("#### ") and " begin" in line
            if begin_match:
                marker = line.strip()[5:].replace(" begin", "").strip()
                flag_value = replace_dict.get(marker, "是")
                should_comment = flag_value == "否"
                block_lines = []
                i += 1
                while i < n and not lines[i].strip().startswith(f"#### {marker} end"):
                    block_lines.append(lines[i])
                    i += 1
                new_lines.append(line)
                for blk_line in block_lines:
                    replaced_line = blk_line
                    for old_text, new_text in replace_dict.items():
                        if not (isinstance(new_text, str) and new_text in ("是", "否")):
                            replaced_line = replaced_line.replace(old_text, str(new_text))
                    if should_comment and replaced_line.strip():
                        stripped = replaced_line.lstrip()
                        indent = replaced_line[: len(replaced_line) - len(stripped)]
                        if not stripped.startswith("#"):
                            replaced_line = indent + "# " + stripped
                    new_lines.append(replaced_line)
                if i < n:
                    new_lines.append(lines[i])
                i += 1
                continue

            processed = line
            for old_text, new_text in replace_dict.items():
                if not (isinstance(new_text, str) and new_text in ("是", "否")):
                    processed = processed.replace(old_text, str(new_text))
            new_lines.append(processed)
            i += 1

        output_file.write_text("".join(new_lines), encoding="utf-8")
