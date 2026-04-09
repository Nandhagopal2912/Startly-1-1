"use client";

import { motion } from "framer-motion";
import { Loader2, Zap } from "lucide-react";

type Props = {
  label?: string;
  sublabel?: string;
};

export function LoadingOverlay({ label = "Loading", sublabel }: Props) {
  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-white/80 backdrop-blur-xl"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="flex flex-col items-center"
      >
        <div className="relative mb-8">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="h-20 w-20 rounded-[2rem] border-4 border-indigo-100 border-t-indigo-500"
          />
          <div className="absolute inset-0 flex items-center justify-center text-indigo-500">
            <Zap size={24} fill="currentColor" className="animate-pulse" />
          </div>
        </div>
        
        <h3 className="text-xl font-bold text-slate-900 tracking-tight">{label}</h3>
        {sublabel && (
          <p className="mt-2 text-sm text-slate-500 font-medium max-w-[240px] text-center leading-relaxed">
            {sublabel}
          </p>
        )}
        
        <div className="mt-10 flex gap-1">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{ 
                scale: [1, 1.5, 1],
                opacity: [0.3, 1, 0.3]
              }}
              transition={{ 
                duration: 1, 
                repeat: Infinity, 
                delay: i * 0.2 
              }}
              className="h-1.5 w-1.5 rounded-full bg-indigo-500"
            />
          ))}
        </div>
      </motion.div>
    </div>
  );
}
