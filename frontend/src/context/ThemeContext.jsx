import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

const THEMES = {
  dark: {
    name: 'Escuro',
    description: 'Tema elegante com tons de esmeralda e glassmorphism',
    preview: 'from-emerald-800 to-teal-900'
  },
  light: {
    name: 'Claro',
    description: 'Tema luminoso com alta legibilidade e contraste',
    preview: 'from-emerald-100 via-green-200 to-emerald-300'
  },
  black: {
    name: 'Preto (AMOLED)',
    description: 'Preto puro para telas OLED - economia de bateria',
    preview: 'from-zinc-900 to-black'
  },
  purple: {
    name: 'Roxo',
    description: 'Gradiente premium roxo com visual moderno',
    preview: 'from-purple-700 via-violet-800 to-indigo-900'
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
