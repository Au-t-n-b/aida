import { useLocation } from 'react-router-dom';

/** Drop-in for next/navigation usePathname */
export function usePathname(): string {
  return useLocation().pathname;
}

/** pathname + search，用于带 query 的侧栏选中匹配 */
export function useNavPath(): string {
  const { pathname, search } = useLocation();
  return search ? `${pathname}${search}` : pathname;
}
