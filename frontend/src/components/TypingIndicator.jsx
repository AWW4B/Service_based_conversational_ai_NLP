import { motion } from 'framer-motion';

export default function TypingIndicator() {
    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="flex items-start gap-2 px-4 pb-2"
        >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#F57224] to-[#ff8c42] flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm">
                D
            </div>
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                    <div className="flex gap-1">
                        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
                    </div>
                    <span className="text-xs text-gray-400 ml-2">Daraz Assistant is typing...</span>
                </div>
            </div>
        </motion.div>
    );
}
