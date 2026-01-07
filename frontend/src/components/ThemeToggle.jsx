import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';

const ThemeToggle = ({ className }) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={cn(
        'relative p-2 rounded-xl transition-all duration-200',
        theme === 'dark'
          ? 'bg-white/10 hover:bg-white/20'
          : 'bg-white border border-slate-200 hover:bg-slate-50 shadow-sm',
        className
      )}
      title={theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
    >
      <div className="relative w-5 h-5">
        <Sun 
          className={cn(
            'absolute inset-0 w-5 h-5 transition-all duration-300',
            theme === 'dark' 
              ? 'opacity-0 rotate-90 scale-0' 
              : 'opacity-100 rotate-0 scale-100 text-amber-500'
          )}
        />
        <Moon 
          className={cn(
            'absolute inset-0 w-5 h-5 transition-all duration-300',
            theme === 'dark' 
              ? 'opacity-100 rotate-0 scale-100 text-blue-300' 
              : 'opacity-0 -rotate-90 scale-0'
          )}
        />
      </div>
    </button>
  );
};

export default ThemeToggle;
