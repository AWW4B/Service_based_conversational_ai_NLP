const API_BASE = '';  // Vite proxy handles routing to :8000

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

export function generateSessionId() {
    return crypto.randomUUID?.() || `sess-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
