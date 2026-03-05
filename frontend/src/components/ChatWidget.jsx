import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle } from 'lucide-react';
import ChatWindow from './ChatWindow';
import { useChat } from '../hooks/useChat';

export default function ChatWidget() {
    const [isOpen, setIsOpen] = useState(false);
    const chat = useChat();

    return (
        <>
            {/* ── Floating chat window ───────────────────────────── */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                        className="fixed bottom-24 right-4 z-50 w-[380px] h-[600px] max-h-[80vh]
                       sm:w-[400px] sm:h-[620px]
                       max-[480px]:bottom-0 max-[480px]:right-0 max-[480px]:left-0 max-[480px]:w-full max-[480px]:h-full max-[480px]:rounded-none max-[480px]:max-h-full"
                    >
                        <ChatWindow
                            chat={chat}
                            onMinimize={() => setIsOpen(false)}
                            onClose={() => setIsOpen(false)}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Floating Action Button ─────────────────────────── */}
            <motion.button
                onClick={() => setIsOpen(prev => !prev)}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-[#F57224] hover:bg-[#e0621a] text-white rounded-full shadow-lg flex items-center justify-center transition-colors"
            >
                <AnimatePresence mode="wait">
                    {isOpen ? (
                        <motion.span
                            key="close"
                            initial={{ rotate: -90, opacity: 0 }}
                            animate={{ rotate: 0, opacity: 1 }}
                            exit={{ rotate: 90, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            className="text-xl font-bold"
                        >
                            ✕
                        </motion.span>
                    ) : (
                        <motion.span
                            key="open"
                            initial={{ rotate: 90, opacity: 0 }}
                            animate={{ rotate: 0, opacity: 1 }}
                            exit={{ rotate: -90, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                        >
                            <MessageCircle size={24} />
                        </motion.span>
                    )}
                </AnimatePresence>
            </motion.button>

            {/* ── Badge (unread hint when closed) ─────────────────── */}
            {!isOpen && (
                <motion.div
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 1, type: 'spring' }}
                    className="fixed bottom-[72px] right-5 z-50 bg-white px-3 py-1.5 rounded-full shadow-md text-xs text-gray-700 border border-gray-200 pointer-events-none"
                >
                    💬 Need help shopping?
                </motion.div>
            )}
        </>
    );
}
