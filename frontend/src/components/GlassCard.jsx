import React from 'react';
import { cn } from '../lib/utils';
import { useTheme } from '../context/ThemeContext';

export const GlassCard = ({ children, className, hover = true, ...props }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div
      className={cn(
        isDark
          ? 'backdrop-blur-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/20 shadow-2xl shadow-emerald-500/10 rounded-3xl'
          : 'bg-white border border-slate-200 shadow-sm rounded-2xl',
        'p-6',
        hover && (isDark
          ? 'hover:scale-[1.01] transition-all duration-300 hover:shadow-emerald-500/20'
          : 'transition-all duration-200 hover:shadow-md hover:border-slate-300'),
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const GlassInput = React.forwardRef(({ className, ...props }, ref) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <input
      ref={ref}
      className={cn(
        'w-full px-4 py-3 rounded-xl',
        isDark
          ? 'bg-white/10 backdrop-blur-sm border border-white/20 text-foreground placeholder:text-muted-foreground'
          : 'bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400',
        isDark
          ? 'focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50'
          : 'focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500',
        'transition-all duration-200',
        className
      )}
      {...props}
    />
  );
});
GlassInput.displayName = 'GlassInput';

export const GlassButton = ({ children, className, variant = 'primary', loading = false, ...props }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const variants = {
    primary: isDark
      ? 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/30'
      : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm',
    secondary: isDark
      ? 'bg-white/10 hover:bg-white/20 text-foreground border border-white/20'
      : 'bg-white hover:bg-slate-50 text-slate-900 border border-slate-200 shadow-sm',
    danger: isDark
      ? 'bg-red-500/80 hover:bg-red-600/80 text-white'
      : 'bg-red-600 hover:bg-red-700 text-white shadow-sm',
    ghost: isDark
      ? 'bg-transparent hover:bg-white/10 text-foreground'
      : 'bg-transparent hover:bg-slate-100 text-slate-900'
  };

  return (
    <button
      className={cn(
        'px-6 py-3 rounded-xl font-medium',
        'transition-all duration-200 transform',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'active:scale-95',
        variants[variant],
        className
      )}
      disabled={loading}
      {...props}
    >
      {loading ? (
        <span className="flex items-center justify-center gap-2">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Carregando...
        </span>
      ) : children}
    </button>
  );
};

export const GlassBadge = ({ children, variant = 'default', className }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const variants = {
    default: isDark ? 'bg-white/20 text-foreground' : 'bg-slate-100 text-slate-700',
    success: isDark ? 'bg-emerald-500/30 text-emerald-300' : 'bg-emerald-50 text-emerald-700 border border-emerald-100',
    warning: isDark ? 'bg-amber-500/30 text-amber-300' : 'bg-amber-50 text-amber-800 border border-amber-100',
    danger: isDark ? 'bg-red-500/30 text-red-300' : 'bg-red-50 text-red-700 border border-red-100',
    info: isDark ? 'bg-blue-500/30 text-blue-300' : 'bg-blue-50 text-blue-700 border border-blue-100'
  };

  return (
    <span
      className={cn(
        'px-3 py-1 rounded-full text-sm font-medium',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
};
