import { useMemo } from 'react';
import { ArrowLeft, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import ChatSidebar from '@/components/ChatSidebar';
import ChatView from '@/components/ChatView';
import ChatStats from '@/components/ChatStats';
import { useChat } from '@/contexts/ChatContext';

const AiChats = () => {
  const { selectedChat, selectChat, chats } = useChat();

  const validChatIds = useMemo(() => {
    return chats
      .filter((c) => c.ai)
      .map((c) => c.id)
      .filter((id): id is number => typeof id === 'number' && !isNaN(id));
  }, [chats]);

  const handleChatDeleted = () => {
    selectChat(null);
  };

  return (
    <div className="h-screen flex flex-col">
      {selectedChat && (
        <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => selectChat(null)}
            className="w-full justify-start px-4 py-2 text-gray-700 hover:bg-gray-100"
          >
            <ArrowLeft size={16} className="mr-2" />
            Back to AI Chats
          </Button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <div className={`w-full md:w-1/3 lg:w-3/10 flex flex-col border-r border-gray-300 ${selectedChat ? 'hidden md:flex' : 'flex'}`}>
          <ChatStats />
          <div className="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
              <Bot size={18} className="text-aiHighlight" />
              ИИ чаты
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <ChatSidebar onSelectChat={selectChat} validChatIds={validChatIds} />
          </div>
        </div>

        <div className={`w-full md:w-2/3 lg:w-7/10 flex-1 border-l border-gray-200 ${!selectedChat ? 'hidden md:block' : 'block'} ${selectedChat ? 'mt-12 md:mt-0' : ''}`}>
          <ChatView
            chatId={selectedChat?.id || null}
            onChatDeleted={handleChatDeleted}
          />
        </div>
      </div>
    </div>
  );
};

export default AiChats;

