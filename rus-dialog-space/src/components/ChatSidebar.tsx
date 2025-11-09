import React, { useState, useEffect, useMemo } from 'react';
import { Chat, getChats } from '@/lib/api';
import { CircleDot, MessageSquare, Send, Search } from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useChat } from '@/contexts/ChatContext';
import { Input } from '@/components/ui/input';

interface ChatSidebarProps {
  onSelectChat: (chatId: number | null) => void;
  validChatIds?: number[];
}

const ChatSidebar = ({ onSelectChat, validChatIds }: ChatSidebarProps) => {
  const { chats, loading, unreadCount, selectedChat } = useChat();
  const [searchQuery, setSearchQuery] = useState('');

  // Filter chats based on search query
  const filteredChats = chats.filter(chat => {
    const matchesSearch = !searchQuery || 
      chat.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.lastMessage?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const isValidId = validChatIds ? typeof chat.id === 'number' && !isNaN(chat.id) && chat.id !== null && chat.id !== undefined && validChatIds.includes(chat.id) : true;

    return matchesSearch && isValidId;
  });
  
  // Update validChatIds when new chats are added
  useEffect(() => {
    if (validChatIds) {
      const newChatIds = chats
        .filter(chat => typeof chat.id === 'number' && !isNaN(chat.id))
        .map(chat => chat.id);
      
      // If we have new chat IDs that aren't in validChatIds, update the parent
      const hasNewChats = newChatIds.some(id => validChatIds && !validChatIds.includes(id));
      if (hasNewChats) {
        onSelectChat(selectedChat?.id || null); // Pass null if selectedChat is null
      }
    }
  }, [chats, validChatIds, selectedChat, onSelectChat]);

  // Sort chats: waiting (unread) at top by lastMessageTime desc, then read by lastMessageTime desc
  const waitingChats = filteredChats
    .filter(chat => chat.waiting)
    .sort((a, b) => new Date(b.lastMessageTime || 0).getTime() - new Date(a.lastMessageTime || 0).getTime());

  const regularChats = filteredChats
    .filter(chat => !chat.waiting)
    .sort((a, b) => new Date(b.lastMessageTime || 0).getTime() - new Date(a.lastMessageTime || 0).getTime());

  return (
    <div className="h-full flex flex-col bg-white border-r border-gray-200">
      {/* Chat List Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Сообщения</h2>
          <div className="relative w-40">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
            <Input
              type="text"
              placeholder="Поиск по чатам и тегам..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 w-full"
            />
          </div>
        </div>
      </div>
      
      {/* Chat List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">Загрузка чатов...</div>
        ) : (
          <>
            {/* Waiting Response Section */}
            {waitingChats.length > 0 && (
              <div>
                <div className="px-4 py-2 bg-gray-100 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200">
                  Ожидают ответа
                </div>
                
                {waitingChats.map((chat) => (
                  <ChatPreview 
                    key={chat.id}
                    chat={chat} 
                    isSelected={selectedChat?.id === chat.id} 
                    onClick={() => {
                      console.log('Sidebar selecting chat:', chat);
                      onSelectChat(chat.id);
                    }} 
                  />
                ))}
              </div>
            )}
            
            {/* Regular Chats Section */}
            <div>
              {waitingChats.length > 0 && (
                <div className="px-4 py-2 bg-gray-100 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200">
                  Все сообщения
                </div>
              )}
              
              {regularChats.map((chat) => (
                <ChatPreview 
                  key={chat.id}
                  chat={chat} 
                  isSelected={selectedChat?.id === chat.id} 
                  onClick={() => {
                    console.log('Sidebar selecting chat:', chat);
                    onSelectChat(chat.id);
                  }} 
                />
              ))}
            </div>
            
            {filteredChats.length === 0 && (
              <div className="p-4 text-center text-gray-500">Нет доступных чатов</div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

interface ChatPreviewProps {
  chat: Chat;
  isSelected: boolean;
  onClick: () => void;
}

const ChatPreview = React.memo(({ chat, isSelected, onClick }: ChatPreviewProps) => {
  const truncateMessage = (message: string | undefined, maxLength: number = 30) => {
    if (!message) return 'Нет сообщений';
    return message.length > maxLength ? message.substring(0, maxLength) + '...' : message;
  };
  
  // Format timestamp
  const formatTime = (timestamp: string | undefined) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  };
  
  return (
    <div 
      className={`p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors flex items-start ${isSelected ? 'bg-gray-100' : ''}`}
      onClick={onClick}
    >
      <div className="mr-3 flex-shrink-0 mt-1">
        <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center text-gray-600">
          {chat.messager === 'telegram' ? (
            <Send size={20} className="text-blue-500" />
          ) : chat.messager === 'vk' ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <rect width="24" height="24" rx="6" fill="#2787F5"/>
              <path d="M17.5 8.5C17.7 7.9 17.5 7.5 16.7 7.5H15.5C15 7.5 14.8 7.8 14.6 8.2C14.6 8.2 13.7 10.1 13.1 10.9C12.9 11.1 12.8 11.2 12.7 11.2C12.6 11.2 12.5 11.1 12.5 10.8V8.5C12.5 8 12.4 7.5 11.6 7.5H9.1C8.7 7.5 8.5 7.7 8.5 8C8.5 8.5 9.2 8.6 9.3 10.1V12.1C9.2 12.4 9 12.5 8.8 12.5C8.5 12.5 7.7 11.5 7.2 10.3C7 9.8 6.8 9.5 6.3 9.5H5.5C5.1 9.5 5 9.7 5 10C5 10.5 5.5 11.7 6.6 13.2C7.7 14.7 9.1 15.5 10.3 15.5C10.7 15.5 10.9 15.3 10.9 14.9V14.1C10.9 13.7 11 13.6 11.3 13.6C11.5 13.6 12 13.7 12.6 14.3C13.4 15.1 13.7 15.5 14.3 15.5H15.5C15.9 15.5 16 15.3 16 15C16 14.5 15.3 14.4 14.7 13.7C14.5 13.5 14.5 13.4 14.7 13.1C14.7 13.1 17.1 10.2 17.5 8.5Z" fill="white"/>
            </svg>
          ) : (
            <MessageSquare size={20} className="text-gray-500" />
          )}
        </div>
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center">
          <h3 className="text-sm font-medium text-gray-900 truncate">
            {chat.name || `Чат #${chat.uuid}`}
          </h3>
          {chat.tags && chat.tags.length > 0 && (
            <div className="flex gap-1 ml-2 overflow-hidden">
              {chat.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded flex-shrink-0"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          <span className="text-xs text-gray-500 ml-auto flex-shrink-0">
            {chat.lastMessageTime && formatTime(chat.lastMessageTime)}
          </span>
        </div>
        
        <div className="flex items-center justify-between mt-1">
          <p className="text-sm text-gray-500 truncate">
            {truncateMessage(chat.lastMessage)}
          </p>
          
          <div className="flex items-center ml-2">
            {chat.waiting && (
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 mr-1" />
            )}
            
            {chat.ai && (
              <div className="text-xs px-1.5 py-0.5 bg-gray-300 text-aiHighlight rounded-sm">
                ИИ
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default ChatSidebar;
