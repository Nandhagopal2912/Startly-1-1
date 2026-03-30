"use client";

type Props = {
  label?: string;
  sublabel?: string;
};

export function LoadingOverlay({ label = "Loading", sublabel }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/40 backdrop-blur-[2px]"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex flex-col items-center rounded-2xl bg-white px-10 py-8 shadow-xl">
        <div className="relative h-14 w-14">
          <div
            className="absolute inset-0 rounded-full border-2 border-slate-200"
            aria-hidden
          />
          <div
            className="animate-loader-orbit absolute inset-0 rounded-full border-2 border-transparent border-t-blue-600 border-r-blue-500"
            aria-hidden
          />
          <div
            className="animate-loader-pulse absolute inset-3 rounded-full bg-blue-500/20"
            aria-hidden
          />
        </div>
        <p className="mt-5 text-sm font-semibold text-slate-800">{label}</p>
        {sublabel ? <p className="mt-1 max-w-xs text-center text-xs text-slate-500">{sublabel}</p> : null}
      </div>
    </div>
  );
}
