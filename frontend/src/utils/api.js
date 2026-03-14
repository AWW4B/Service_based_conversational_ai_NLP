// In Docker: VITE_API_BASE_URL and VITE_WS_BASE_URL are empty → use relative paths proxied by nginx.
// In local dev: set them to http://localhost:8000 and ws://localhost:8000 in .env.
const _apiEnv = import.meta.env.VITE_API_BASE_URL || '';
const _wsEnv  = import.meta.env.VITE_WS_BASE_URL  || '';

const API_BASE = _apiEnv || '/api';
export const WS_BASE = _wsEnv || (() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws`;
})();

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

// =============================================================================
// VOICE ENDPOINTS (A3 — ASR + TTS)
// These call the backend voice pipeline implemented by the backend team.
// =============================================================================

/**
 * Sends an audio blob to POST /voice/transcribe.
 * Returns { transcript: string } on success.
 */
export async function transcribeAudio(audioBlob) {
    const form = new FormData();
    form.append('audio', audioBlob, 'recording.webm');
    const res = await fetch(`${API_BASE}/voice/transcribe`, {
        method: 'POST',
        body: form,
    });
    if (!res.ok) throw new Error(`Transcribe error: ${res.status}`);
    return res.json();
}

/**
 * Sends text to POST /voice/synthesize.
 * Returns a Blob containing the synthesized audio (mp3/wav).
 */
export async function synthesizeSpeech(text) {
    const res = await fetch(`${API_BASE}/voice/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`Synthesize error: ${res.status}`);
    return res.blob();
}
