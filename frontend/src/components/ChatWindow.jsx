import { useRef, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import ChatHeader from './ChatHeader';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import QuickActions from './QuickActions';
import InputBar from './InputBar';

export default function ChatWindow({ chat, onMinimize, onClose }) {
    const { messages, isLoading, status, send, reset } = chat;
    const scrollRef = useRef(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isLoading]);

    const showQuickActions = messages.length === 1 && messages[0]?.role === 'assistant';

    return (
        <div className="flex flex-col h-full bg-[#f5f5f5] rounded-2xl shadow-2xl overflow-hidden border border-gray-200">
            {/* Header */}
            <ChatHeader onReset={reset} onMinimize={onMinimize} onClose={onClose} />

            {/* Messages area */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto chat-scroll space-y-3 py-4"
            >
                {messages.map((msg, i) => (
                    <MessageBubble key={i} message={msg} isLast={i === messages.length - 1} />
                ))}

                {/* Quick action chips after first bot message */}
                {showQuickActions && (
                    <QuickActions onSelect={send} disabled={isLoading} />
                )}

                {/* Typing indicator */}
                <AnimatePresence>
                    {isLoading && <TypingIndicator />}
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
            <InputBar onSend={send} disabled={isLoading || status === 'ended'} />
        </div>
    );
}
