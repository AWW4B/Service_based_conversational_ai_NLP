import { motion } from 'framer-motion';
import { ShoppingBag, RotateCcw, X, Minus } from 'lucide-react';

export default function ChatHeader({ onReset, onMinimize, onClose }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-[#F57224] to-[#ff8c42] text-white rounded-t-2xl shadow-md"
        >
            {/* Left: Logo + Title */}
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
                    <ShoppingBag size={20} />
                </div>
                <div>
                    <h1 className="text-base font-bold leading-tight">Daraz Smart Assistant</h1>
                    <div className="flex items-center gap-1.5 text-xs text-white/80">
                        <span className="relative flex h-2 w-2">
                            <span className="pulse-ring absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
                        </span>
                        Online
                    </div>
                </div>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-1">
                <button
                    onClick={onReset}
                    title="New Chat"
                    className="p-2 rounded-full hover:bg-white/20 transition-colors"
                >
                    <RotateCcw size={16} />
                </button>
                {onMinimize && (
                    <button
                        onClick={onMinimize}
                        title="Minimize"
                        className="p-2 rounded-full hover:bg-white/20 transition-colors"
                    >
                        <Minus size={16} />
                    </button>
                )}
                {onClose && (
                    <button
                        onClick={onClose}
                        title="Close"
                        className="p-2 rounded-full hover:bg-white/20 transition-colors"
                    >
                        <X size={16} />
                    </button>
                )}
            </div>
        </motion.div>
    );
}
