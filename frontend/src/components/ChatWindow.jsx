import { useRef, useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import ChatHeader from './ChatHeader';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import QuickActions from './QuickActions';
import InputBar from './InputBar';
import SessionSidebar from './SessionSidebar';
import { useVoice } from '../hooks/useVoice';

export default function ChatWindow({ chat, onMinimize, onClose }) {
    const { messages, isLoading, sessionId, status, turnsMax, send, reset, loadSession } = chat;
    const scrollRef = useRef(null);
    const [sidebarOpen, setSidebarOpen] = useState(false);

    // ── Voice ──────────────────────────────────────────────────────────────────
    const voice = useVoice({ onTranscript: send });

    // Auto-play: speak the latest completed assistant message when autoPlay is on
    const lastAutoSpokenRef = useRef(null);
    useEffect(() => {
        if (!voice.autoPlay) return;
        const last = messages[messages.length - 1];
        if (
            last &&
            last.role === 'assistant' &&
            !last.streaming &&
            !last.isError &&
            last.content &&
            last.timestamp !== lastAutoSpokenRef.current
        ) {
            lastAutoSpokenRef.current = last.timestamp;
            voice.speak(last.content);
        }
    }, [messages, voice.autoPlay]); // eslint-disable-line react-hooks/exhaustive-deps

    // ── Error toast for voice errors ──────────────────────────────────────────
    useEffect(() => {
        if (!voice.error) return;
        const t = setTimeout(voice.clearError, 4000);
        return () => clearTimeout(t);
    }, [voice.error, voice.clearError]);

    // ── Auto-scroll ───────────────────────────────────────────────────────────
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isLoading]);

    const showQuickActions = messages.length === 1 && messages[0]?.role === 'assistant';

    return (
        <div className="flex flex-col h-full bg-[#f5f5f5] rounded-2xl shadow-2xl overflow-hidden border border-gray-200">
            {/* Header */}
            <ChatHeader
                onReset={reset}
                onMinimize={onMinimize}
                onClose={onClose}
                onToggleHistory={() => setSidebarOpen(prev => !prev)}
                autoPlay={voice.autoPlay}
                onToggleAutoPlay={voice.toggleAutoPlay}
            />

            {/* Session history sidebar */}
            <SessionSidebar
                currentSessionId={sessionId}
                onLoadSession={loadSession}
                onNewChat={reset}
                isOpen={sidebarOpen}
                onClose={() => setSidebarOpen(false)}
                turnsMax={turnsMax}
            />

            {/* Voice error toast */}
            <AnimatePresence>
                {voice.error && (
                    <motion.div
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        className="mx-3 mt-2 px-3 py-2 bg-red-50 border border-red-200 rounded-xl text-xs text-red-600 flex items-center gap-2"
                    >
                        <span className="text-base">🎤</span>
                        <span>{voice.error}</span>
                        <button
                            onClick={voice.clearError}
                            className="ml-auto text-red-400 hover:text-red-600 font-bold"
                        >
                            ✕
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Messages area */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto chat-scroll space-y-3 py-4"
            >
                {messages.map((msg, i) => (
                    <MessageBubble
                        key={i}
                        message={msg}
                        isLast={i === messages.length - 1}
                        voice={voice}
                    />
                ))}

                {/* Quick action chips after first bot message */}
                {showQuickActions && (
                    <QuickActions onSelect={send} disabled={isLoading} />
                )}

                {/* Typing indicator */}
                <AnimatePresence>
                    {isLoading && !messages.some(m => m.streaming) && <TypingIndicator />}
                </AnimatePresence>
            </div>

            {/* Session ended banner */}
            {status === 'ended' && (
                <div className="px-4 py-2 bg-orange-50 text-center text-xs text-gray-600 border-t border-orange-100">
                    Session ended.{' '}
                    <button onClick={reset} className="text-[#F57224] font-semibold hover:underline">
                        Start New Chat
                    </button>
                </div>
            )}

            {/* Input bar */}
            <InputBar
                onSend={send}
                disabled={isLoading || status === 'ended'}
                voice={voice}
            />
        </div>
    );
}
