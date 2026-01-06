import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

const THEMES = {
  dark: {
    name: 'Escuro',
    description: 'Tema escuro padrão com tons de esmeralda',
    preview: 'from-emerald-900 to-emerald-950'
  },
  light: {
    name: 'Claro',
    description: 'Tema claro com alta legibilidade',
    preview: 'from-slate-100 to-slate-200'
  },
  black: {
    name: 'Preto',
    description: 'Tema AMOLED com preto puro',
    preview: 'from-black to-zinc-900'
  },
  purple: {
    name: 'Roxo',
    description: 'Tema moderno com gradiente roxo',
    preview: 'from-purple-900 to-indigo-950'
  }
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('whatsapp-crm-theme');
    return saved || 'dark';
  });

  useEffect(() => {
    localStorage.setItem('whatsapp-crm-theme', theme);
    // Remove all theme classes
    document.documentElement.classList.remove('light', 'dark', 'black', 'purple');
    // Add current theme class
    document.documentElement.classList.add(theme);
  }, [theme]);

  const toggleTheme = () => {
    const themeKeys = Object.keys(THEMES);
    const currentIndex = themeKeys.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themeKeys.length;
    setTheme(themeKeys[nextIndex]);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
