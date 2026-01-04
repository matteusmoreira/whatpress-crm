import { Toaster as Sonner, toast } from "sonner"

const GlassToaster = ({ ...props }) => {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      position="top-right"
      toastOptions={{
        classNames: {
          toast:
            "group toast backdrop-blur-xl bg-gradient-to-br from-white/15 to-white/5 border border-white/20 shadow-2xl shadow-emerald-500/10 rounded-xl text-white",
          description: "group-[.toast]:text-white/70",
          actionButton:
            "group-[.toast]:bg-emerald-500 group-[.toast]:text-white group-[.toast]:rounded-lg",
          cancelButton:
            "group-[.toast]:bg-white/10 group-[.toast]:text-white/70 group-[.toast]:rounded-lg",
          success: "!bg-emerald-500/20 !border-emerald-500/30",
          error: "!bg-red-500/20 !border-red-500/30",
          warning: "!bg-amber-500/20 !border-amber-500/30",
          info: "!bg-blue-500/20 !border-blue-500/30",
        },
      }}
      {...props}
    />
  );
};

export { GlassToaster, toast }
