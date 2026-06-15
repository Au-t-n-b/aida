import './style-switch.css';

export type LoginStyle = 'gateway' | 'glass';

interface StyleSwitchProps {
  value: LoginStyle;
  onChange: (next: LoginStyle) => void;
}

/** 登录页底部的风格切换段控件。 */
export function StyleSwitch({ value, onChange }: StyleSwitchProps) {
  return (
    <div className="login-style-switch" role="group" aria-label="登录风格">
      <button
        type="button"
        className={`lss-seg${value === 'gateway' ? ' lss-active' : ''}`}
        aria-current={value === 'gateway'}
        onClick={() => onChange('gateway')}
      >
        浅色
      </button>
      <button
        type="button"
        className={`lss-seg${value === 'glass' ? ' lss-active' : ''}`}
        aria-current={value === 'glass'}
        onClick={() => onChange('glass')}
      >
        深色
      </button>
    </div>
  );
}
