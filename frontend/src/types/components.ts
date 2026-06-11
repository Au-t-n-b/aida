import type { CSSProperties, ElementType, ReactNode, SVGProps } from 'react';

export type IconProps = {
  size?: number;
  color?: string;
  style?: CSSProperties;
};

export type SvgIconProps = IconProps & Partial<SVGProps<SVGSVGElement>>;

export type ChildrenProps = { children?: ReactNode };

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export type ButtonProps = ChildrenProps & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  iconRight?: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  style?: CSSProperties;
};

/* tones must stay in sync with BADGE_STYLES in primitives.tsx */
export type BadgeTone = 'default' | 'green' | 'amber' | 'red' | 'blue' | 'violet' | 'accent' | 'purple';
export type BadgeProps = ChildrenProps & {
  tone?: BadgeTone;
  size?: 'xs' | 'sm' | 'md';
  dot?: boolean;
};

/** must stay in sync with PANEL_TONES in primitives.tsx */
export type PanelTone = 'default' | 'raised' | 'accent' | 'amber' | 'blue' | 'red' | 'green';

export type PanelProps = ChildrenProps & {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  padding?: string | number;
  as?: ElementType;
  tone?: PanelTone;
  style?: CSSProperties;
};
