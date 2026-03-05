import { useState, useCallback, useRef, useEffect } from 'react';
import { sendMessage, getWelcome, resetSession, generateSessionId } from '../utils/api';

export function useChat() {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(() => generateSessionId());
    const [status, setStatus] = useState('active');
    const [latency, setLatency] = useState(null);
    const initialized = useRef(false);

    // Fetch welcome message on first mount
    useEffect(() => {
        if (initialized.current) return;
        initialized.current = true;

        (async () => {
            try {
                const data = await getWelcome(sessionId);
                setMessages([{ role: 'assistant', content: data.response, timestamp: Date.now() }]);
            } catch {
                setMessages([{
                    role: 'assistant',
                    content: "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. What are you looking to buy today?",
                    timestamp: Date.now(),
                }]);
            }
        })();
    }, [sessionId]);

    const send = useCallback(async (text) => {
        if (!text.trim() || isLoading || status === 'ended') return;

        const userMsg = { role: 'user', content: text.trim(), timestamp: Date.now() };
        setMessages(prev => [...prev, userMsg]);
        setIsLoading(true);

        try {
            const data = await sendMessage(sessionId, text.trim());
            const botMsg = {
                role: 'assistant',
                content: data.response,
                timestamp: Date.now(),
                latency_ms: data.latency_ms,
            };
            setMessages(prev => [...prev, botMsg]);
            setLatency(data.latency_ms);
            if (data.status) setStatus(data.status);
        } catch (err) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'Sorry, something went wrong. Please try again.',
                timestamp: Date.now(),
                isError: true,
            }]);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, isLoading, status]);

    const reset = useCallback(async () => {
        try { await resetSession(sessionId); } catch { /* ignore */ }
        const newId = generateSessionId();
        setSessionId(newId);
        setMessages([]);
        setStatus('active');
        setLatency(null);
        initialized.current = false;

        // Re-fetch welcome for new session
        try {
            const data = await getWelcome(newId);
            setMessages([{ role: 'assistant', content: data.response, timestamp: Date.now() }]);
        } catch {
            setMessages([{
                role: 'assistant',
                content: "Hi! I'm Daraz Assistant 🛍️, your personal shopping guide for Daraz.pk. What are you looking to buy today?",
                timestamp: Date.now(),
            }]);
        }
        initialized.current = true;
    }, [sessionId]);

    return { messages, isLoading, sessionId, status, latency, send, reset };
}
