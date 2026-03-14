import { motion } from 'framer-motion';
import ProductCard from './ProductCard';
import SpeakButton from './SpeakButton';

function extractProducts(content) {
    return [];
}

export default function MessageBubble({ message, isLast, voice }) {
    const isUser      = message.role === 'user';
    const isStreaming  = !!message.streaming;
    const products    = !isUser ? extractProducts(message.content) : [];

    // Determine if this specific bubble's text is the one currently being spoken
    const isThisPlaying = voice && !isUser && !isStreaming &&
        (voice.playbackState === 'playing' || voice.playbackState === 'loading');

    const showSpeakButton = !isUser && !isStreaming && !message.isError && !!message.content && !!voice;

    return (
        <motion.div
            initial={isStreaming ? false : { opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className={`flex gap-2 px-4 ${isUser ? 'justify-end' : 'justify-start'}`}
        >
            {/* Bot avatar */}
            {!isUser && (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#F57224] to-[#ff8c42] flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm mt-1">
                    D
                </div>
            )}

            <div className={`max-w-[80%] ${isUser ? 'order-1' : ''}`}>
                {/* Bubble */}
                <div
                    className={`
                        px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words
                        ${isUser
                            ? 'bg-[#F57224] text-white rounded-2xl rounded-tr-sm shadow-sm'
                            : `bg-white text-gray-800 rounded-2xl rounded-tl-sm shadow-sm border border-gray-100 ${message.isError ? 'border-red-200 bg-red-50' : ''}`
                        }
                        ${isThisPlaying ? 'ring-2 ring-[#F57224]/30' : ''}
                    `}
                >
                    {message.content}
                    {isStreaming && (
                        <span className="inline-block w-1.5 h-4 ml-0.5 bg-[#F57224] rounded-sm animate-pulse align-middle" />
                    )}
                    {message.cancelled && (
                        <span className="block mt-1 text-xs text-orange-400 italic">Generation stopped</span>
                    )}
                </div>

                {/* Product cards (if any) */}
                {products.length > 0 && (
                    <div className="flex gap-3 overflow-x-auto mt-2 pb-2 chat-scroll">
                        {products.map((p, i) => <ProductCard key={i} product={p} />)}
                    </div>
                )}

                {/* Timestamp + latency + speak button row */}
                <div className={`flex items-center gap-2 mt-1 flex-wrap ${isUser ? 'justify-end' : ''}`}>
                    <div className="flex items-center gap-2 text-[10px] text-gray-400">
                        <span>
                            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {!isUser && message.latency_ms && (
                            <span className="text-gray-300">• {(message.latency_ms / 1000).toFixed(1)}s</span>
                        )}
                    </div>

                    {/* TTS speak button */}
                    {showSpeakButton && (
                        <SpeakButton
                            text={message.content}
                            playbackState={voice.playbackState}
                            isThisPlaying={isThisPlaying}
                            onSpeak={() => voice.speak(message.content)}
                            onStop={voice.stopSpeaking}
                        />
                    )}
                </div>
            </div>

            {/* User avatar */}
            {isUser && (
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-white text-xs font-bold shrink-0 mt-1">
                    U
                </div>
            )}
        </motion.div>
    );
}
