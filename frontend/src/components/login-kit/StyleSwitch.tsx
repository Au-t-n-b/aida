import './style-switch.css';

export type LoginStyle = 'particle' | 'glass';

interface StyleSwitchProps {
  value: LoginStyle;
  onChange: (next: LoginStyle) => void;
}

/** 登录页底部的「粒子 / 玻璃」风格切换段控件。 */
export function StyleSwitch({ value, onChange }: StyleSwitchProps) {
  return (
    <div className="login-style-switch" role="group" aria-label="登录风格">
      <button
        type="button"
        className={`lss-seg${value === 'particle' ? ' lss-active' : ''}`}
        aria-current={value === 'particle'}
        onClick={() => onChange('particle')}
      >
        粒子
      </button>
      <button
        type="button"
        className={`lss-seg${value === 'glass' ? ' lss-active' : ''}`}
        aria-current={value === 'glass'}
        onClick={() => onChange('glass')}
      >
        玻璃
      </button>
    </div>
  );
}
