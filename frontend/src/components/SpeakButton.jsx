import { motion, AnimatePresence } from 'framer-motion';
import { Volume2, Square, Loader2 } from 'lucide-react';

// =============================================================================
// SpeakButton — TTS playback button shown below each assistant message bubble.
//
// Props:
//   text          — message text to synthesize
//   playbackState — 'idle' | 'loading' | 'playing'  (from useVoice)
//   isThisPlaying — true only when THIS specific message is playing
//   onSpeak       — () => void
//   onStop        — () => void
// =============================================================================

function WaveformBars() {
    return (
        <div className="flex items-end gap-[2px] h-3.5" aria-hidden>
            {[8, 14, 10, 14, 8].map((h, i) => (
                <div
                    key={i}
                    className="eq-bar w-[2.5px] rounded-full bg-[#F57224]"
                    style={{ height: h }}
                />
            ))}
        </div>
    );
}

export default function SpeakButton({ text, playbackState, isThisPlaying, onSpeak, onStop }) {
    const isLoading = isThisPlaying && playbackState === 'loading';
    const isPlaying = isThisPlaying && playbackState === 'playing';

    return (
        <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.2 }}
            className="mt-1.5 flex items-center gap-1.5"
        >
            <motion.button
                type="button"
                onClick={isPlaying ? onStop : onSpeak}
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                aria-label={isPlaying ? 'Stop speaking' : 'Speak response aloud'}
                title={isPlaying ? 'Stop' : 'Play response aloud'}
                className={`
                    flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium
                    transition-all duration-200 border
                    ${isPlaying
                        ? 'bg-orange-50 border-[#F57224] text-[#F57224]'
                        : isLoading
                            ? 'bg-gray-50 border-gray-200 text-gray-400 cursor-wait'
                            : 'bg-white border-gray-200 text-gray-500 hover:border-[#F57224] hover:text-[#F57224] hover:bg-orange-50'
                    }
                `}
            >
                <AnimatePresence mode="wait">
                    {isLoading ? (
                        <motion.span
                            key="loading"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                        >
                            <Loader2 size={10} className="animate-spin" />
                        </motion.span>
                    ) : isPlaying ? (
                        <motion.span
                            key="playing"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex items-center gap-1.5"
                        >
                            <WaveformBars />
                            <Square size={8} className="fill-[#F57224] text-[#F57224]" />
                        </motion.span>
                    ) : (
                        <motion.span
                            key="idle"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex items-center gap-1"
                        >
                            <Volume2 size={10} />
                            Speak
                        </motion.span>
                    )}
                </AnimatePresence>
            </motion.button>
        </motion.div>
    );
}
