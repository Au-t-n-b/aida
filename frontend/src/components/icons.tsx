'use client';

import type { IconProps } from '../types/components';

const iconProps = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export function IconClaw({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <line x1="5" y1="19" x2="10" y2="5" />
      <line x1="9" y1="19" x2="14" y2="5" />
      <line x1="13" y1="19" x2="18" y2="5" />
    </svg>
  );
}

export function IconSurvey({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="2" />
      <path d="M9 12h6M9 16h4" />
    </svg>
  );
}

export function IconGantt({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="3" y="5" width="8" height="3" rx="1" />
      <rect x="8" y="10.5" width="9" height="3" rx="1" />
      <rect x="5" y="16" width="6" height="3" rx="1" />
      <line x1="3" y1="3" x2="3" y2="21" />
    </svg>
  );
}

export function IconTopo({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <circle cx="12" cy="5" r="2" />
      <circle cx="5" cy="17" r="2" />
      <circle cx="19" cy="17" r="2" />
      <circle cx="12" cy="17" r="2" />
      <line x1="12" y1="7" x2="5" y2="15" />
      <line x1="12" y1="7" x2="12" y2="15" />
      <line x1="12" y1="7" x2="19" y2="15" />
    </svg>
  );
}

export function IconDesign({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M2 13.5V19a1 1 0 001 1h4.5" />
      <path d="M22 10.5V5a1 1 0 00-1-1h-4.5" />
      <path d="M13.5 22H19a1 1 0 001-1v-4.5" />
      <path d="M10.5 2H5a1 1 0 00-1 1v4.5" />
      <rect x="8" y="8" width="8" height="8" rx="1" />
    </svg>
  );
}

export function IconInstall({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M12 3v12M8 11l4 4 4-4" />
      <path d="M3 17v2a2 2 0 002 2h14a2 2 0 002-2v-2" />
    </svg>
  );
}

export function IconDeploy({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}

export function IconChat({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

export function IconFile({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
      <polyline points="13 2 13 9 20 9" />
    </svg>
  );
}

export function IconUpload({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polyline points="16 16 12 12 8 16" />
      <line x1="12" y1="12" x2="12" y2="21" />
      <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" />
    </svg>
  );
}

export function IconCheck({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function IconArrow({ size = 16, color = "currentColor", direction = "right" }) {
  const rotate = { right: 0, left: 180, up: -90, down: 90 }[direction] || 0;
  return (
    <svg {...iconProps} width={size} height={size} stroke={color} style={{ transform: `rotate(${rotate}deg)` }}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function IconChevron({
  size = 16,
  color = 'currentColor',
  direction = 'down',
}: IconProps & { direction?: 'down' | 'up' | 'left' | 'right' }) {
  const paths = { down: 'M6 9l6 6 6-6', up: 'M18 15l-6-6-6 6', left: 'M15 18l-6-6 6-6', right: 'M9 18l6-6-6-6' };
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polyline points={paths[direction] ?? paths.down} />
    </svg>
  );
}

export function IconClose({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export function IconPlus({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export function IconSearch({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function IconPlay({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

export function IconPause({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  );
}

export function IconRefresh({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  );
}

export function IconAlert({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function IconShield({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

export function IconBolt({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

export function IconSettings({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );
}

export function IconBell({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </svg>
  );
}

export function IconExternal({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

export function IconDownload({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export function IconEye({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function IconImage({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  );
}

export function IconTable({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
    </svg>
  );
}

export function IconPdf({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M9 13h1.5a1.5 1.5 0 000-3H9v6M14 13h1a2 2 0 010 4h-1v-4" />
    </svg>
  );
}

export function IconCpu({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
    </svg>
  );
}

export function IconUser({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function IconBranch({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <line x1="6" y1="3" x2="6" y2="15" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 01-9 9" />
    </svg>
  );
}

export function IconLayers({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}

export function IconCommand({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M18 3a3 3 0 00-3 3v12a3 3 0 003 3 3 3 0 003-3 3 3 0 00-3-3H6a3 3 0 00-3 3 3 3 0 003 3 3 3 0 003-3V6a3 3 0 00-3-3 3 3 0 00-3 3 3 3 0 003 3h12a3 3 0 003-3 3 3 0 00-3-3z" />
    </svg>
  );
}

export function IconGrid({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

export function IconBox({ size = 16, color = 'currentColor' }: IconProps) {
  return (
    <svg {...iconProps} width={size} height={size} stroke={color}>
      <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

export const ICON_MAP = {
  IconSurvey, IconGantt, IconTopo, IconDesign, IconInstall, IconDeploy,
  IconChat, IconFile, IconUpload, IconCheck, IconArrow, IconChevron,
  IconClose, IconPlus, IconSearch, IconPlay, IconPause, IconRefresh,
  IconAlert, IconShield, IconBolt, IconSettings, IconBell, IconExternal,
  IconDownload, IconEye, IconImage, IconTable, IconPdf, IconCpu,
  IconUser, IconBranch, IconLayers, IconCommand, IconClaw, IconGrid, IconBox,
};
