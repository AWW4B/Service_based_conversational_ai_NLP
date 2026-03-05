import { useChat } from '../hooks/useChat';
import ChatWindow from './ChatWindow';

export default function FullPageChat() {
    const chat = useChat();

    return (
        <div className="h-screen w-full max-w-3xl mx-auto p-4 flex flex-col">
            <ChatWindow chat={chat} />
        </div>
    );
}
