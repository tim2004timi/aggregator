import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import ChatSidebar from '@/components/ChatSidebar';
import ChatView from '@/components/ChatView';
import ChatStats from '@/components/ChatStats';
import { useChat } from '@/contexts/ChatContext';
import { ArrowLeft } from 'lucide-react';

const Index = () => {
  const navigate = useNavigate();
  // Получаем selectChat и selectedChat из контекста
  const { selectedChat, selectChat } = useChat();

  const handleChatDeleted = () => {
    // При удалении чата, сбрасываем selectedChat в контексте
    selectChat(null); //selectChat теперь принимает null для сброса выбранного чата
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Mobile Back Button - Fixed at the top */}
      {selectedChat && (
        <div className="md:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => selectChat(null)}
            className="w-full justify-start px-4 py-2 text-gray-700 hover:bg-gray-100"
          >
            <ArrowLeft size={16} className="mr-2" />
            Back to Chats
          </Button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar - hidden on mobile when chat is selected */}
        <div className={`w-full md:w-1/3 lg:w-3/10 flex flex-col border-r border-gray-300 ${selectedChat ? 'hidden md:flex' : 'flex'}`}>
          <ChatStats />
          <div className="flex-1 overflow-hidden">
            <ChatSidebar
              onSelectChat={selectChat}
            />
          </div>
        </div>
        
        {/* Main Content - full width on mobile when chat is selected */}
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

export default Index;
