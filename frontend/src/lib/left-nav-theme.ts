export type LeftNavTheme = 'light' | 'dark';

const STORAGE_KEY = 'aida:left-nav-theme';

export function readLeftNavTheme(): LeftNavTheme {
  if (typeof window === 'undefined') return 'dark';
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === 'light' ? 'light' : 'dark';
}

export function persistLeftNavTheme(theme: LeftNavTheme) {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, theme);
  }
}
