import React from 'react';

type ButtonVariant = 'default' | 'primary' | 'secondary' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface GlowButtonProps {
  children: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  type?: 'button' | 'submit' | 'reset';
  title?: string;
}

const variantMap: Record<ButtonVariant, string> = {
  default: '',
  primary: 'navi-glow-btn--primary',
  secondary: 'navi-glow-btn--secondary',
  ghost: 'navi-glow-btn--ghost',
};

const sizeMap: Record<ButtonSize, string> = {
  sm: 'navi-glow-btn--sm',
  md: '',
  lg: 'navi-glow-btn--lg',
  icon: 'navi-glow-btn--icon',
};

export const GlowButton: React.FC<GlowButtonProps> = ({
  children,
  variant = 'default',
  size = 'md',
  disabled = false,
  loading = false,
  className = '',
  onClick,
  type = 'button',
  title,
}) => {
  const classes = [
    'navi-glow-btn',
    variantMap[variant],
    sizeMap[size],
    disabled && 'opacity-50 cursor-not-allowed',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type={type}
      className={classes}
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
    >
      {loading ? (
        <span className="navi-spinner" />
      ) : (
        <span>{children}</span>
      )}
    </button>
  );
};

export default GlowButton;
