import { Toaster as Sonner, toast } from "sonner"
import { useTheme } from "../../context/ThemeContext"

const GlassToaster = ({ ...props }) => {
  const { theme } = useTheme()
  const isDark = theme === "dark"

  return (
    <Sonner
      theme={isDark ? "dark" : "light"}
      className="toaster group"
      position="top-right"
      toastOptions={{
        classNames: {
          toast:
            isDark
              ? "group toast backdrop-blur-xl bg-gradient-to-br from-white/15 to-white/5 border border-white/20 shadow-2xl shadow-emerald-500/10 rounded-xl text-white"
              : "group toast bg-white border border-slate-200 shadow-lg rounded-xl text-slate-900",
          description: isDark ? "group-[.toast]:text-white/70" : "group-[.toast]:text-slate-600",
          actionButton:
            "group-[.toast]:bg-emerald-500 group-[.toast]:text-white group-[.toast]:rounded-lg",
          cancelButton:
            isDark
              ? "group-[.toast]:bg-white/10 group-[.toast]:text-white/70 group-[.toast]:rounded-lg"
              : "group-[.toast]:bg-slate-100 group-[.toast]:text-slate-700 group-[.toast]:rounded-lg",
          success: isDark ? "!bg-emerald-500/20 !border-emerald-500/30" : "!bg-emerald-50 !border-emerald-200",
          error: isDark ? "!bg-red-500/20 !border-red-500/30" : "!bg-red-50 !border-red-200",
          warning: isDark ? "!bg-amber-500/20 !border-amber-500/30" : "!bg-amber-50 !border-amber-200",
          info: isDark ? "!bg-blue-500/20 !border-blue-500/30" : "!bg-blue-50 !border-blue-200",
        },
      }}
      {...props}
    />
  );
};

export { GlassToaster, toast }
