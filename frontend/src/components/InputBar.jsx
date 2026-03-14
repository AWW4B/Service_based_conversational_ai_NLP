import { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send } from 'lucide-react';
import VoiceMicButton from './VoiceMicButton';

export default function InputBar({ onSend, disabled, voice }) {
    const [text, setText] = useState('');
    const inputRef = useRef(null);

    function handleSubmit(e) {
        e.preventDefault();
        if (!text.trim() || disabled) return;
        onSend(text);
        setText('');
        inputRef.current?.focus();
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    }

    const isVoiceBusy = voice?.micState === 'recording' || voice?.micState === 'transcribing';

    return (
        <motion.form
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            onSubmit={handleSubmit}
            className="flex items-center gap-2 px-3 py-3 bg-white border-t border-gray-100"
        >
            {/* Microphone — live voice input */}
            {voice && (
                <VoiceMicButton
                    micState={voice.micState}
                    onStart={voice.startRecording}
                    onStop={voice.stopRecording}
                    disabled={disabled}
                />
            )}

            {/* Text input */}
            <input
                ref={inputRef}
                type="text"
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={disabled || isVoiceBusy}
                placeholder={
                    disabled       ? 'Session ended — start a new chat' :
                    isVoiceBusy    ? voice?.micState === 'transcribing' ? 'Transcribing…' : 'Listening…' :
                                     'Ask about products on Daraz…'
                }
                className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-full text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-[#F57224] focus:ring-2 focus:ring-[#F57224]/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            />

            {/* Send */}
            <motion.button
                type="submit"
                disabled={disabled || !text.trim() || isVoiceBusy}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.9 }}
                className="p-2.5 bg-[#F57224] text-white rounded-full shadow-sm hover:bg-[#e0621a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
                <Send size={18} />
            </motion.button>
        </motion.form>
    );
}
