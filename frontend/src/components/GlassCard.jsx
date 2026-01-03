import React from 'react';
import { cn } from '../lib/utils';

export const GlassCard = ({ children, className, hover = true, ...props }) => {
  return (
    <div
      className={cn(
        'backdrop-blur-xl bg-gradient-to-br from-white/10 to-white/5',
        'border border-white/20 shadow-2xl shadow-emerald-500/10',
        'rounded-3xl p-6',
        hover && 'hover:scale-[1.01] transition-all duration-300 hover:shadow-emerald-500/20',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const GlassInput = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        'w-full px-4 py-3 rounded-xl',
        'bg-white/10 backdrop-blur-sm border border-white/20',
        'text-white placeholder:text-white/50',
        'focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50',
        'transition-all duration-200',
        className
      )}
      {...props}
    />
  );
});
GlassInput.displayName = 'GlassInput';

export const GlassButton = ({ children, className, variant = 'primary', loading = false, ...props }) => {
  const variants = {
    primary: 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/30',
    secondary: 'bg-white/10 hover:bg-white/20 text-white border border-white/20',
    danger: 'bg-red-500/80 hover:bg-red-600/80 text-white',
    ghost: 'bg-transparent hover:bg-white/10 text-white'
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
  const variants = {
    default: 'bg-white/20 text-white',
    success: 'bg-emerald-500/30 text-emerald-300',
    warning: 'bg-amber-500/30 text-amber-300',
    danger: 'bg-red-500/30 text-red-300',
    info: 'bg-blue-500/30 text-blue-300'
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
