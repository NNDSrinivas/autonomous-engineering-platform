import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: boolean;
  interactive?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

const paddingMap = {
  none: '',
  sm: 'navi-p-sm',
  md: 'navi-p-md',
  lg: 'navi-p-lg',
};

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  glow = false,
  interactive = false,
  padding = 'md',
  onClick,
}) => {
  const classes = [
    'navi-glass-card',
    glow && 'navi-glass-card--glow',
    interactive && 'navi-glass-card--interactive',
    paddingMap[padding],
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} onClick={onClick} role={onClick ? 'button' : undefined}>
      {children}
    </div>
  );
};

export default GlassCard;
