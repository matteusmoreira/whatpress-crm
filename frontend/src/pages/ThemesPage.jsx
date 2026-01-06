import React from 'react';
import { Check, Moon, Sun, Sparkles, Palette } from 'lucide-react';
import { GlassCard } from '../components/GlassCard';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';

const ThemeCard = ({ themeKey, themeData, isSelected, onSelect }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark' || theme === 'black' || theme === 'purple';

    return (
        <button
            onClick={() => onSelect(themeKey)}
            className={cn(
                "relative p-6 rounded-2xl text-left transition-all duration-300 group overflow-hidden",
                "backdrop-blur-xl border-2",
                isSelected
                    ? isDark
                        ? "bg-white/20 border-emerald-400 ring-2 ring-emerald-400/50 shadow-lg shadow-emerald-500/20"
                        : "bg-white border-emerald-500 ring-2 ring-emerald-500/50 shadow-lg shadow-emerald-500/30"
                    : isDark
                        ? "bg-white/10 border-white/20 hover:bg-white/15 hover:border-white/30"
                        : "bg-white/90 border-slate-200 hover:bg-white hover:border-slate-300 shadow-sm hover:shadow-md"
            )}
        >
            {/* Preview gradient - mais alto e com mais detalhes */}
            <div className={cn(
                "w-full h-28 rounded-xl mb-4 bg-gradient-to-br shadow-lg overflow-hidden",
                themeData.preview,
                themeKey === 'light' && 'border border-slate-200'
            )}>
                <div className="w-full h-full backdrop-blur-sm bg-black/5 flex items-center justify-center">
                    {themeKey === 'dark' && <Moon className="w-10 h-10 text-white drop-shadow-lg" />}
                    {themeKey === 'light' && <Sun className="w-10 h-10 text-amber-500 drop-shadow-lg" />}
                    {themeKey === 'black' && <Sparkles className="w-10 h-10 text-white drop-shadow-lg" />}
                    {themeKey === 'purple' && <Palette className="w-10 h-10 text-purple-200 drop-shadow-lg" />}
                </div>
            </div>

            <h3 className={cn(
                "text-lg font-bold mb-1",
                isDark ? 'text-white' : 'text-slate-800'
            )}>
                {themeData.name}
            </h3>

            <p className={cn(
                "text-sm leading-relaxed",
                isDark ? 'text-white/60' : 'text-slate-500'
            )}>
                {themeData.description}
            </p>

            {/* Selected indicator - mais visível */}
            {isSelected && (
                <div className="absolute top-3 right-3 w-7 h-7 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg shadow-emerald-500/50">
                    <Check className="w-4 h-4 text-white" strokeWidth={3} />
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
