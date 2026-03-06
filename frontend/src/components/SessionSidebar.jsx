import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Trash2, Plus, Clock, ChevronLeft } from 'lucide-react';
import { getSessions, deleteSession } from '../utils/api';

export default function SessionSidebar({ currentSessionId, onLoadSession, onNewChat, isOpen, onClose }) {
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchSessions = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getSessions();
            setSessions(data.sessions || []);
        } catch (err) {
            console.error('Failed to fetch sessions:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isOpen) fetchSessions();
    }, [isOpen, fetchSessions]);

    const handleDelete = async (e, sessionId) => {
        e.stopPropagation();
        try {
            await deleteSession(sessionId);
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
        } catch (err) {
            console.error('Failed to delete session:', err);
        }
    };

    const formatTime = (isoStr) => {
        if (!isoStr) return '';
        const date = new Date(isoStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/30 z-[60] backdrop-blur-sm"
                    />

                    {/* Sidebar panel */}
                    <motion.div
                        initial={{ x: -320, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: -320, opacity: 0 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        className="fixed left-0 top-0 bottom-0 w-80 bg-white z-[70] shadow-2xl flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-[#F57224] to-[#ff8c42] text-white">
                            <h2 className="text-base font-bold">Chat History</h2>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => { onNewChat(); onClose(); }}
                                    title="New Chat"
                                    className="p-2 rounded-full hover:bg-white/20 transition-colors"
                                >
                                    <Plus size={18} />
                                </button>
                                <button
                                    onClick={onClose}
                                    title="Close"
                                    className="p-2 rounded-full hover:bg-white/20 transition-colors"
                                >
                                    <ChevronLeft size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Session list */}
                        <div className="flex-1 overflow-y-auto">
                            {loading ? (
                                <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                                    Loading sessions...
                                </div>
                            ) : sessions.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-12 text-gray-400 text-sm gap-2">
                                    <MessageSquare size={32} className="text-gray-300" />
                                    <p>No chat history yet</p>
                                    <p className="text-xs">Start chatting to see your sessions here</p>
                                </div>
                            ) : (
                                <div className="py-2">
                                    {sessions.map((session) => {
                                        const isActive = session.session_id === currentSessionId;
                                        return (
                                            <motion.button
                                                key={session.session_id}
                                                onClick={() => { onLoadSession(session.session_id); onClose(); }}
                                                whileHover={{ x: 4 }}
                                                className={`w-full text-left px-4 py-3 border-b border-gray-50 transition-colors group ${isActive
                                                        ? 'bg-orange-50 border-l-4 border-l-[#F57224]'
                                                        : 'hover:bg-gray-50 border-l-4 border-l-transparent'
                                                    }`}
                                            >
                                                <div className="flex items-start justify-between gap-2">
                                                    <div className="flex-1 min-w-0">
                                                        <p className={`text-sm font-medium truncate ${isActive ? 'text-[#F57224]' : 'text-gray-800'}`}>
                                                            {session.title || 'New Chat'}
                                                        </p>
                                                        <p className="text-xs text-gray-400 truncate mt-0.5">
                                                            {session.preview || 'No messages yet'}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className="flex items-center gap-1 text-[10px] text-gray-400">
                                                                <Clock size={10} />
                                                                {formatTime(session.updated_at)}
                                                            </span>
                                                            <span className="text-[10px] text-gray-300">•</span>
                                                            <span className="text-[10px] text-gray-400">
                                                                {session.turns ?? 0}/{10} turns
                                                            </span>
                                                            <span className="text-[10px] text-gray-300">•</span>
                                                            <span className="text-[10px] text-gray-400">
                                                                {session.message_count} msgs
                                                            </span>
                                                            {session.status === 'ended' && (
                                                                <>
                                                                    <span className="text-[10px] text-gray-300">•</span>
                                                                    <span className="text-[10px] text-orange-400 font-medium">Ended</span>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <button
                                                        onClick={(e) => handleDelete(e, session.session_id)}
                                                        title="Delete chat"
                                                        className="p-1.5 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 text-gray-400 transition-all"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            </motion.button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-4 py-2 border-t border-gray-100 text-center">
                            <p className="text-[10px] text-gray-400">
                                {sessions.length} saved {sessions.length === 1 ? 'session' : 'sessions'}
                            </p>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
