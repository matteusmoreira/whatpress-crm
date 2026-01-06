import React from 'react';
import { Check, Moon, Sun, Sparkles, Palette } from 'lucide-react';
import { GlassCard } from '../components/GlassCard';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';

const ThemeCard = ({ themeKey, themeData, isSelected, onSelect }) => {
    const { theme } = useTheme();

    return (
        <button
            onClick={() => onSelect(themeKey)}
            className={cn(
                "relative p-6 rounded-2xl text-left transition-all duration-300 group",
                "backdrop-blur-xl border",
                isSelected
                    ? theme === 'dark' || theme === 'black' || theme === 'purple'
                        ? "bg-white/20 border-emerald-500 ring-2 ring-emerald-500/50"
                        : "bg-slate-100 border-emerald-500 ring-2 ring-emerald-500/50"
                    : theme === 'dark' || theme === 'black' || theme === 'purple'
                        ? "bg-white/10 border-white/20 hover:bg-white/15"
                        : "bg-white border-slate-200 hover:bg-slate-50"
            )}
        >
            {/* Preview gradient */}
            <div className={cn(
                "w-full h-24 rounded-xl mb-4 bg-gradient-to-br shadow-lg",
                themeData.preview
            )}>
                <div className="w-full h-full rounded-xl backdrop-blur-sm bg-black/10 flex items-center justify-center">
                    {themeKey === 'dark' && <Moon className="w-8 h-8 text-white/80" />}
                    {themeKey === 'light' && <Sun className="w-8 h-8 text-yellow-500" />}
                    {themeKey === 'black' && <Sparkles className="w-8 h-8 text-white/80" />}
                    {themeKey === 'purple' && <Palette className="w-8 h-8 text-purple-300" />}
                </div>
            </div>

            <h3 className={cn(
                "text-lg font-semibold mb-1",
                theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white' : 'text-slate-800'
            )}>
                {themeData.name}
            </h3>

            <p className={cn(
                "text-sm",
                theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white/60' : 'text-slate-500'
            )}>
                {themeData.description}
            </p>

            {/* Selected indicator */}
            {isSelected && (
                <div className="absolute top-3 right-3 w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center">
                    <Check className="w-4 h-4 text-white" />
                </div>
            )}
        </button>
    );
};

const ThemesPage = () => {
    const { theme, setTheme, themes } = useTheme();

    return (
        <div className="min-h-screen p-6 lg:p-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className={cn(
                    "text-3xl font-bold mb-2",
                    theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white' : 'text-slate-800'
                )}>
                    Temas
                </h1>
                <p className={cn(
                    theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white/60' : 'text-slate-500'
                )}>
                    Personalize a aparência do sistema
                </p>
            </div>

            {/* Theme Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {Object.entries(themes).map(([key, data]) => (
                    <ThemeCard
                        key={key}
                        themeKey={key}
                        themeData={data}
                        isSelected={theme === key}
                        onSelect={setTheme}
                    />
                ))}
            </div>

            {/* Info */}
            <GlassCard className="mt-8 p-6">
                <div className="flex items-start gap-4">
                    <div className={cn(
                        "p-3 rounded-xl",
                        theme === 'dark' || theme === 'black' || theme === 'purple'
                            ? 'bg-emerald-500/20'
                            : 'bg-emerald-100'
                    )}>
                        <Palette className={cn(
                            "w-6 h-6",
                            theme === 'dark' || theme === 'black' || theme === 'purple'
                                ? 'text-emerald-400'
                                : 'text-emerald-600'
                        )} />
                    </div>
                    <div>
                        <h3 className={cn(
                            "font-semibold mb-1",
                            theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white' : 'text-slate-800'
                        )}>
                            Glassmorphism
                        </h3>
                        <p className={cn(
                            "text-sm",
                            theme === 'dark' || theme === 'black' || theme === 'purple' ? 'text-white/60' : 'text-slate-500'
                        )}>
                            Todos os temas utilizam o estilo glassmorphism moderno com transparências e desfoque,
                            mantendo uma aparência premium e elegante em toda a interface.
                        </p>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
};

export default ThemesPage;
