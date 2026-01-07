import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

const THEMES = {
  dark: {
    name: 'Escuro',
    description: 'Tema escuro com alto contraste e foco em leitura',
    preview: 'from-emerald-800 to-teal-900'
  },
  light: {
    name: 'Claro',
    description: 'Tema claro clean e profissional, sem efeitos de vidro',
    preview: 'from-emerald-100 via-green-200 to-emerald-300'
  }
};

export const ThemeProvider = ({ children }) => {
  const normalizeTheme = (value) => {
    if (value === 'black' || value === 'purple') return 'dark';
    if (value === 'dark' || value === 'light') return value;
    return 'light';
  };

  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('whatsapp-crm-theme');
    return normalizeTheme(saved);
  });

  useEffect(() => {
    const nextTheme = normalizeTheme(theme);
    if (nextTheme !== theme) {
      setTheme(nextTheme);
      return;
    }

    localStorage.setItem('whatsapp-crm-theme', nextTheme);
    document.documentElement.classList.remove('light', 'dark', 'black', 'purple');
    document.documentElement.classList.add(nextTheme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
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
