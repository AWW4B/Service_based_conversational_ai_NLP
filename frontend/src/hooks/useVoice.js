import { useState, useRef, useCallback } from 'react';
import { transcribeAudio, synthesizeSpeech } from '../utils/api';

// =============================================================================
// useVoice — manages microphone recording (ASR) and audio playback (TTS)
//
// micState:     'idle' | 'requesting' | 'recording' | 'transcribing'
// playbackState:'idle' | 'loading'   | 'playing'
// autoPlay:      boolean — when true, each new assistant message is auto-spoken
// =============================================================================

export function useVoice({ onTranscript }) {
    const [micState, setMicState]           = useState('idle');
    const [playbackState, setPlaybackState] = useState('idle');
    const [autoPlay, setAutoPlay]           = useState(false);
    const [error, setError]                 = useState(null);

    const mediaRecorderRef = useRef(null);
    const chunksRef        = useRef([]);
    const audioRef         = useRef(null);

    // -------------------------------------------------------------------------
    // Recording
    // -------------------------------------------------------------------------

    const startRecording = useCallback(async () => {
        setError(null);
        setMicState('requesting');

        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
            setError('Microphone access denied — please allow mic access and try again.');
            setMicState('idle');
            return;
        }

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : '';

        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
        chunksRef.current = [];

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunksRef.current.push(e.data);
        };

        recorder.onstop = async () => {
            stream.getTracks().forEach((t) => t.stop());
            const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
            setMicState('transcribing');
            try {
                const data = await transcribeAudio(blob);
                setMicState('idle');
                if (data?.transcript) {
                    onTranscript(data.transcript);
                } else {
                    setError('No speech detected — please try again.');
                }
            } catch (err) {
                setError('Transcription failed — is the backend running?');
                setMicState('idle');
            }
        };

        recorder.onerror = () => {
            stream.getTracks().forEach((t) => t.stop());
            setError('Recording error — please try again.');
            setMicState('idle');
        };

        mediaRecorderRef.current = recorder;
        recorder.start(250); // collect data every 250ms for reliable blobs
        setMicState('recording');
    }, [onTranscript]);

    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.stop();
        }
    }, []);

    const cancelRecording = useCallback(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.ondataavailable = null;
            mediaRecorderRef.current.onstop = null;
            mediaRecorderRef.current.stop();
        }
        chunksRef.current = [];
        setMicState('idle');
    }, []);

    // -------------------------------------------------------------------------
    // TTS Playback
    // -------------------------------------------------------------------------

    const stopSpeaking = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }
        setPlaybackState('idle');
    }, []);

    const speak = useCallback(async (text) => {
        if (!text?.trim()) return;
        stopSpeaking(); // cancel any existing playback first
        setPlaybackState('loading');

        try {
            const blob = await synthesizeSpeech(text);
            const url  = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audioRef.current = audio;

            audio.onplay  = () => setPlaybackState('playing');
            audio.onended = () => {
                setPlaybackState('idle');
                URL.revokeObjectURL(url);
                if (audioRef.current === audio) audioRef.current = null;
            };
            audio.onerror = () => {
                setPlaybackState('idle');
                URL.revokeObjectURL(url);
                if (audioRef.current === audio) audioRef.current = null;
                setError('Speech playback failed.');
            };
            await audio.play();
        } catch {
            setPlaybackState('idle');
            setError('Speech synthesis failed — is the backend running?');
        }
    }, [stopSpeaking]);

    const toggleAutoPlay = useCallback(() => setAutoPlay((prev) => !prev), []);

    const clearError = useCallback(() => setError(null), []);

    return {
        micState,
        playbackState,
        autoPlay,
        error,
        startRecording,
        stopRecording,
        cancelRecording,
        speak,
        stopSpeaking,
        toggleAutoPlay,
        clearError,
    };
}
