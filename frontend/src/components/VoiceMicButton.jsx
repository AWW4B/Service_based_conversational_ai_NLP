import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Loader2 } from 'lucide-react';

// =============================================================================
// VoiceMicButton — animated push-to-talk microphone button
//
// States:
//   idle        → mic icon, orange hover glow
//   requesting  → mic icon + spinner ring
//   recording   → red pulsing ring + equalizer bars + "Recording…" tooltip
//   transcribing→ dark button + spinning loader + "Transcribing…" tooltip
// =============================================================================

function EqualizerBars({ color = '#fff' }) {
    return (
        <div className="flex items-end gap-[2px] h-4" aria-hidden>
            {[10, 16, 10, 14, 8].map((h, i) => (
                <div
                    key={i}
                    className="eq-bar w-[3px] rounded-full"
                    style={{ height: h, background: color }}
                />
            ))}
        </div>
    );
}

export default function VoiceMicButton({ micState, onStart, onStop, disabled }) {
    const isIdle         = micState === 'idle';
    const isRequesting   = micState === 'requesting';
    const isRecording    = micState === 'recording';
    const isTranscribing = micState === 'transcribing';
    const busy           = isTranscribing || disabled;

    function handleClick() {
        if (isIdle && !busy)       onStart();
        else if (isRecording)      onStop();
    }

    return (
        <div className="relative flex items-center justify-center">

            {/* — Pulsing red ring (recording only) — */}
            <AnimatePresence>
                {isRecording && (
                    <>
                        <span className="absolute w-10 h-10 rounded-full bg-red-400 mic-pulse-ring pointer-events-none" />
                        <span
                            className="absolute w-10 h-10 rounded-full bg-red-400 mic-pulse-ring pointer-events-none"
                            style={{ animationDelay: '0.55s' }}
                        />
                    </>
                )}
            </AnimatePresence>

            {/* — Main button — */}
            <motion.button
                type="button"
                onClick={handleClick}
                disabled={busy}
                aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
                whileHover={!busy ? { scale: 1.1 } : {}}
                whileTap={!busy ? { scale: 0.88 } : {}}
                title={
                    isIdle         ? 'Click to speak' :
                    isRequesting   ? 'Requesting mic…' :
                    isRecording    ? 'Click to stop recording' :
                    isTranscribing ? 'Transcribing…' : ''
                }
                className={`
                    relative z-10 flex items-center justify-center w-9 h-9 rounded-full
                    transition-all duration-200 shadow-sm
                    ${isRecording    ? 'bg-red-500 text-white shadow-red-200 shadow-md'    :
                      isTranscribing ? 'bg-gray-700 text-white cursor-wait'               :
                      isRequesting   ? 'bg-orange-100 text-[#F57224]'                     :
                                       'bg-orange-50 text-[#F57224] hover:bg-orange-100 hover:shadow-orange-100 hover:shadow-md'}
                    disabled:opacity-40 disabled:cursor-not-allowed
                `}
            >
                <AnimatePresence mode="wait">
                    {isRecording ? (
                        <motion.div
                            key="recording"
                            initial={{ scale: 0.7, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.7, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                        >
                            <EqualizerBars color="#fff" />
                        </motion.div>
                    ) : isTranscribing ? (
                        <motion.div
                            key="transcribing"
                            initial={{ scale: 0.7, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.7, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                        >
                            <Loader2 size={16} className="animate-spin" />
                        </motion.div>
                    ) : (
                        <motion.div
                            key="idle"
                            initial={{ scale: 0.7, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.7, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                        >
                            <Mic size={16} />
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.button>

            {/* — Floating status badge — */}
            <AnimatePresence>
                {(isRecording || isTranscribing) && (
                    <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 6, scale: 0.9 }}
                        transition={{ duration: 0.18 }}
                        className={`
                            absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap
                            px-2.5 py-1 rounded-full text-[10px] font-semibold text-white
                            shadow-lg pointer-events-none z-20
                            ${isRecording ? 'bg-red-500' : 'bg-gray-700'}
                        `}
                    >
                        {isRecording ? (
                            <span className="flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                                Recording
                            </span>
                        ) : 'Transcribing…'}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
