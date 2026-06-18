/** 本地开发兜底：npm 装不全时避免 Vite 阻断主流程 */
import type { FC, ReactNode, SVGProps } from 'react';

const Icon: FC<SVGProps<SVGSVGElement>> = (props) => (
  <svg width={16} height={16} viewBox="0 0 24 24" aria-hidden {...props}>
    <rect x={4} y={4} width={16} height={16} rx={2} fill="currentColor" opacity={0.2} />
  </svg>
);

const Null: FC<{ children?: ReactNode }> = () => null;

export default Icon;

export const AlertTriangle = Icon;
export const ArrowRight = Icon;
export const Bar = Null;
export const BarChart = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
export const CalendarDays = Icon;
export const CartesianGrid = Null;
export const Cell = Null;
export const ChevronDown = Icon;
export const ChevronRight = Icon;
export const ClipboardList = Icon;
export const Cpu = Icon;
export const FileText = Icon;
export const FileWarning = Icon;
export const Folder = Icon;
export const FolderKanban = Icon;
export const FolderOpen = Icon;
export const Hexagon = Icon;
export const History = Icon;
export const Home = Icon;
export const LabelList = Null;
export const LayoutDashboard = Icon;
export const Legend = Null;
export const Line = Null;
export const LineChart = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
export const LogOut = Icon;
export const Menu = Icon;
export const Moon = Icon;
export const Network = Icon;
export const Pie = Null;
export const PieChart = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
export const ReferenceLine = Null;
export const ResponsiveContainer = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
export const Scatter = Null;
export const ScatterChart = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
export const Search = Icon;
export const Settings = Icon;
export const ShieldAlert = Icon;
export const Sun = Icon;
export const Tooltip = Null;
export const User = Icon;
export const X = Icon;
export const XAxis = Null;
export const YAxis = Null;
export const ZAxis = Null;
