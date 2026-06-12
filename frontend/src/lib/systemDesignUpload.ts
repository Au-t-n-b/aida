/** 系统设计 InputSlot 展示名 → FILE_CONFIG tag（与后端 pipelines/inputs 对齐） */
export const SD_INPUT_LABEL_TO_TAG: Record<string, string> = {
  '项目信息收集表': 'resource',
  '端口连线表': 'Interconnection_Relationship',
  '设备信息表': 'Device_Info',
  '设备位置表': 'Location_Information',
  '测试用例': 'Test_Case',
  '验收用例': 'Test_Case',
};

/** 解析上传 kind：优先 slotTag，其次槽位 label，再次文件名关键词。 */
export function resolveUploadSlotTag(
  slotTag?: string | null,
  slotLabel?: string | null,
  fileName?: string,
): string {
  const tag = (slotTag ?? '').trim();
  if (tag) return tag;
  const label = (slotLabel ?? '').trim();
  if (label && SD_INPUT_LABEL_TO_TAG[label]) return SD_INPUT_LABEL_TO_TAG[label];
  const name = fileName ?? '';
  if (/项目信息收集|资源需求|资源表/.test(name)) return 'resource';
  if (/007|端口连线|端口互联/.test(name)) return 'Interconnection_Relationship';
  if (/001|设备信息/.test(name)) return 'Device_Info';
  if (/004|设备位置/.test(name)) return 'Location_Information';
  if (/验收|测试用例|008/.test(name) && /\.(doc|docx|xlsx|xls)$/i.test(name)) return 'Test_Case';
  return '';
}
