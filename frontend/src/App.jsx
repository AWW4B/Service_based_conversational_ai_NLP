import { useState, useEffect } from 'react';
import ChatWidget from './components/ChatWidget';
import FullPageChat from './components/FullPageChat';
import { healthCheck } from './utils/api';
import { ShoppingBag } from 'lucide-react';

function App() {
  const [mode, setMode] = useState('widget'); // 'widget' | 'fullpage'
  const [backendStatus, setBackendStatus] = useState('checking');

  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));
  }, []);

  if (mode === 'fullpage') {
    return (
      <div className="min-h-screen bg-[#f5f5f5]">
        <div className="absolute top-4 right-4 z-10">
          <button
            onClick={() => setMode('widget')}
            className="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-xs text-gray-600 hover:border-[#F57224] hover:text-[#F57224] transition-all shadow-sm"
          >
            Switch to Widget
          </button>
        </div>
        <FullPageChat />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f5f5f5]">
      {/* ── Landing / Hero ───────────────────────────── */}
      <div className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
        {/* Top bar */}
        <nav className="fixed top-0 left-0 right-0 bg-white/80 backdrop-blur-md border-b border-gray-100 px-6 py-3 flex items-center justify-between z-40">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#F57224] rounded-lg flex items-center justify-center">
              <ShoppingBag size={16} className="text-white" />
            </div>
            <span className="font-bold text-gray-800">Daraz Smart Assistant</span>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-xs ${backendStatus === 'online' ? 'text-green-600' : backendStatus === 'offline' ? 'text-red-500' : 'text-gray-400'}`}>
              <span className={`w-2 h-2 rounded-full ${backendStatus === 'online' ? 'bg-green-500' : backendStatus === 'offline' ? 'bg-red-500' : 'bg-gray-400'}`} />
              {backendStatus === 'online' ? 'API Online' : backendStatus === 'offline' ? 'API Offline' : 'Checking...'}
            </div>
            <button
              onClick={() => setMode('fullpage')}
              className="px-3 py-1.5 bg-[#F57224] text-white rounded-full text-xs font-semibold hover:bg-[#e0621a] transition-colors"
            >
              Open Full Chat
            </button>
          </div>
        </nav>

        {/* Hero */}
        <div className="max-w-lg space-y-6">
          <div className="w-20 h-20 bg-gradient-to-br from-[#F57224] to-[#ff8c42] rounded-2xl flex items-center justify-center mx-auto shadow-lg">
            <ShoppingBag size={36} className="text-white" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-gray-900">
            Daraz <span className="text-[#F57224]">Smart</span> Assistant
          </h1>
          <p className="text-gray-500 text-base sm:text-lg leading-relaxed">
            Your AI-powered shopping companion for Daraz.pk. Ask about any product,
            get personalized recommendations, and find the best deals — all through a simple chat.
          </p>

          <div className="flex flex-wrap justify-center gap-3 text-xs text-gray-400">
            <span className="px-3 py-1 bg-white rounded-full border border-gray-200">🤖 AI Powered</span>
            <span className="px-3 py-1 bg-white rounded-full border border-gray-200">🛍️ Product Recommendations</span>
            <span className="px-3 py-1 bg-white rounded-full border border-gray-200">⚡ Real-time Chat</span>
          </div>

          <p className="text-sm text-gray-400 pt-4">
            Click the <span className="text-[#F57224] font-semibold">chat bubble</span> in the bottom-right corner to start →
          </p>
        </div>
      </div>

      {/* ── Chat Widget (floating) ───────────────────── */}
      <ChatWidget />
    </div>
  );
}

export default App;
