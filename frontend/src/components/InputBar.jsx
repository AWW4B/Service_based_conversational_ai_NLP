import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send, Mic } from 'lucide-react';

export default function InputBar({ onSend, disabled }) {
    const [text, setText] = useState('');
    const inputRef = useRef(null);

    function handleSubmit(e) {
        e.preventDefault();
        if (!text.trim() || disabled) return;
        onSend(text);
        setText('');
        // Keep focus on input after send
        inputRef.current?.focus();
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    }

    return (
        <motion.form
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            onSubmit={handleSubmit}
            className="flex items-center gap-2 px-3 py-3 bg-white border-t border-gray-100"
        >
            {/* Microphone (decorative / future) */}
            <button
                type="button"
                title="Voice input (coming soon)"
                className="p-2 text-gray-400 hover:text-[#F57224] transition-colors rounded-full hover:bg-orange-50"
            >
                <Mic size={18} />
            </button>

            {/* Text input */}
            <input
                ref={inputRef}
                type="text"
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled}
                placeholder={disabled ? 'Session ended — start a new chat' : 'Ask about products on Daraz...'}
                className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-full text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-[#F57224] focus:ring-2 focus:ring-[#F57224]/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            />

            {/* Send */}
            <motion.button
                type="submit"
                disabled={disabled || !text.trim()}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.9 }}
                className="p-2.5 bg-[#F57224] text-white rounded-full shadow-sm hover:bg-[#e0621a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
                <Send size={18} />
            </motion.button>
        </motion.form>
    );
}
