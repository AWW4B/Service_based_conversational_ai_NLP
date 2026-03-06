import { useState, useCallback, useRef, useEffect } from 'react';
import { getWelcome, resetSession, getSession, generateSessionId, WS_BASE } from '../utils/api';

export function useChat() {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(() => generateSessionId());
    const [status, setStatus] = useState('active');
    const [turnsUsed, setTurnsUsed] = useState(0);
    const [turnsMax, setTurnsMax] = useState(10);
    const [latency, setLatency] = useState(null);
    const initialized = useRef(false);
    const wsRef = useRef(null);
    const streamBuf = useRef('');

    // Persistent WebSocket connection
    useEffect(() => {
        const ws = new WebSocket(`${WS_BASE}/ws/chat`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.error) {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: data.error,
                    timestamp: Date.now(),
                    isError: true,
                }]);
                setIsLoading(false);
                return;
            }

            if (!data.done) {
                // Streaming token — append to current assistant bubble
                streamBuf.current += data.token;
                const partial = streamBuf.current;
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant' && last.streaming) {
                        return [...prev.slice(0, -1), { ...last, content: partial }];
                    }
                    // First token — create streaming bubble
                    return [...prev, { role: 'assistant', content: partial, timestamp: Date.now(), streaming: true }];
                });
            } else {
                // Final chunk — finalise the bubble
                const finalContent = data.cancelled ? (streamBuf.current || '[Cancelled]') : (data.full_response || streamBuf.current);
                streamBuf.current = '';

                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant' && last.streaming) {
                        return [...prev.slice(0, -1), {
                            ...last,
                            content: finalContent,
                            streaming: false,
                            cancelled: !!data.cancelled,
                            latency_ms: data.latency_ms,
                        }];
                    }
                    return [...prev, {
                        role: 'assistant',
                        content: finalContent,
                        timestamp: Date.now(),
                        cancelled: !!data.cancelled,
                        latency_ms: data.latency_ms,
                    }];
                });

                if (data.latency_ms) setLatency(data.latency_ms);
                if (data.status) setStatus(data.status);
                if (data.turns_used != null) setTurnsUsed(data.turns_used);
                if (data.turns_max != null) setTurnsMax(data.turns_max);
                setIsLoading(false);
            }
        };

        ws.onclose = () => {
            // Attempt reconnect after brief delay
            setTimeout(() => {
                if (wsRef.current === ws) {
                    const newWs = new WebSocket(`${WS_BASE}/ws/chat`);
                    newWs.onmessage = ws.onmessage;
                    newWs.onclose = ws.onclose;
                    wsRef.current = newWs;
                }
            }, 2000);
        };

        return () => {
            wsRef.current = null;
            ws.close();
        };
    }, []);

    // Fetch welcome message on first mount
    useEffect(() => {
        if (initialized.current) return;
        initialized.current = true;

        (async () => {
            try {
                const data = await getWelcome(sessionId);
                setMessages([{ role: 'assistant', content: data.response, timestamp: Date.now() }]);
                if (data.turns_used != null) setTurnsUsed(data.turns_used);
                if (data.turns_max != null) setTurnsMax(data.turns_max);
            } catch {
                setMessages([{
                    role: 'assistant',
                    content: "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. What are you looking to buy today?",
                    timestamp: Date.now(),
                }]);
            }
        })();
    }, [sessionId]);

    const send = useCallback((text) => {
        if (!text.trim() || isLoading || status === 'ended') return;
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'Connection lost. Please refresh the page.',
                timestamp: Date.now(),
                isError: true,
            }]);
            return;
        }

        const userMsg = { role: 'user', content: text.trim(), timestamp: Date.now() };
        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);
        streamBuf.current = '';

        ws.send(JSON.stringify({ session_id: sessionId, message: text.trim() }));
    }, [sessionId, isLoading, status]);

    const reset = useCallback(async () => {
        try { await resetSession(sessionId); } catch { /* ignore */ }
        const newId = generateSessionId();
        setSessionId(newId);
        setMessages([]);
        setStatus('active');
        setTurnsUsed(0);
        setLatency(null);
        initialized.current = false;

        // Re-fetch welcome for new session
        try {
            const data = await getWelcome(newId);
            setMessages([{ role: 'assistant', content: data.response, timestamp: Date.now() }]);
            if (data.turns_max != null) setTurnsMax(data.turns_max);
        } catch {
            setMessages([{
                role: 'assistant',
                content: "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. What are you looking to buy today?",
                timestamp: Date.now(),
            }]);
        }
        initialized.current = true;
    }, [sessionId]);

    // Load a previous session by ID — restores full history + context
    const loadSession = useCallback(async (targetSessionId) => {
        setIsLoading(true);
        try {
            const data = await getSession(targetSessionId);
            setSessionId(targetSessionId);
            setStatus(data.status || 'active');
            if (data.turns != null) setTurnsUsed(data.turns);
            if (data.turns_max != null) setTurnsMax(data.turns_max);

            // Convert backend history to frontend message format
            const restored = data.history.map((msg, i) => ({
                role: msg.role,
                content: msg.content,
                timestamp: Date.now() - (data.history.length - i) * 1000,
            }));

            setMessages(restored.length > 0 ? restored : [{
                role: 'assistant',
                content: "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. What are you looking to buy today?",
                timestamp: Date.now(),
            }]);

            initialized.current = true;
        } catch (err) {
            console.error('Failed to load session:', err);
        } finally {
            setIsLoading(false);
        }
    }, []);

    return { messages, isLoading, sessionId, status, turnsUsed, turnsMax, latency, send, reset, loadSession };
}
