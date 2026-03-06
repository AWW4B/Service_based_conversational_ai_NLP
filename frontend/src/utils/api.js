const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

export async function sendMessage(sessionId, message) {
    const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!res.ok) throw new Error(`Chat API error: ${res.status}`);
    return res.json();
}

export async function resetSession(sessionId) {
    const res = await fetch(`${API_BASE}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
    });
    if (!res.ok) throw new Error(`Reset API error: ${res.status}`);
    return res.json();
}

export async function getWelcome(sessionId) {
    const res = await fetch(`${API_BASE}/session/welcome/${sessionId}`);
    if (!res.ok) throw new Error(`Welcome API error: ${res.status}`);
    return res.json();
}

export async function healthCheck() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
}

export async function getSessions() {
    const res = await fetch(`${API_BASE}/sessions`);
    if (!res.ok) throw new Error(`Sessions API error: ${res.status}`);
    return res.json();
}

export async function getSession(sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
    if (!res.ok) throw new Error(`Session API error: ${res.status}`);
    return res.json();
}

export async function deleteSession(sessionId) {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Delete session error: ${res.status}`);
    return res.json();
}

export function generateSessionId() {
    return crypto.randomUUID?.() || `sess-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
