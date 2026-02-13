import React, { useState, useEffect } from 'react';
import { Chat, getCurrentUser, User } from '@/lib/api';
import { MessageSquare, Send, Search } from 'lucide-react';
import { useChat } from '@/contexts/ChatContext';
import { Input } from '@/components/ui/input';

interface TestChatSidebarProps {
  onSelectChat: (chatId: number | null) => void;
  validChatIds?: number[];
}

const TestChatSidebar = ({ onSelectChat, validChatIds }: TestChatSidebarProps) => {
  const { chats, loading, selectedChat } = useChat();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'my'>('all');
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(console.error);
  }, []);

  // Filter chats based on search query and active tab
  const filteredChats = chats.filter(chat => {
    const matchesSearch = !searchQuery || 
      chat.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.lastMessage?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      chat.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const isValidId = validChatIds ? typeof chat.id === 'number' && !isNaN(chat.id) && validChatIds.includes(chat.id) : true;

    const matchesTab = activeTab === 'all' || (activeTab === 'my' && currentUser && chat.assigned_manager_id === currentUser.id);

    return matchesSearch && isValidId && matchesTab;
  });

  // Sort chats: waiting (unread) at top by lastMessageTime desc, then read by lastMessageTime desc
  const waitingChats = filteredChats
    .filter(chat => chat.waiting)
    .sort((a, b) => new Date(b.lastMessageTime || 0).getTime() - new Date(a.lastMessageTime || 0).getTime());

  const regularChats = filteredChats
    .filter(chat => !chat.waiting)
    .sort((a, b) => new Date(b.lastMessageTime || 0).getTime() - new Date(a.lastMessageTime || 0).getTime());

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header with Tabs */}
      <div className="p-4 border-b border-gray-200 space-y-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('all')}
            className={`flex-1 py-2.5 px-3 text-xs font-bold uppercase tracking-wider rounded-xl transition-all ${
              activeTab === 'all' 
                ? 'bg-[#1F1F1F] text-white shadow-md' 
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            Все сообщения
          </button>
          <button
            onClick={() => setActiveTab('my')}
            className={`flex-1 py-2.5 px-3 text-xs font-bold uppercase tracking-wider rounded-xl transition-all ${
              activeTab === 'my' 
                ? 'bg-[#1F1F1F] text-white shadow-md' 
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            Мои сообщения
          </button>
        </div>

        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
          <Input
            type="text"
            placeholder="Поиск"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 w-full h-11 bg-gray-50 border-gray-200 focus:bg-white transition-colors rounded-xl text-sm"
          />
        </div>
      </div>
      
      {/* Chat List */}
      <div className="flex-1 overflow-y-auto scrolling-touch">
        {loading ? (
          <div className="p-4 text-center text-gray-500">Загрузка чатов...</div>
        ) : (
          <div className="flex flex-col">
            {/* Waiting Response Section */}
            {waitingChats.length > 0 && (
              <div>
                <div className="px-4 py-2 bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                  Ожидают ответа ({waitingChats.length})
                </div>
                {waitingChats.map((chat) => (
                  <TestChatPreview 
                    key={chat.id}
                    chat={chat} 
                    isSelected={selectedChat?.id === chat.id} 
                    onClick={() => onSelectChat(chat.id)} 
                  />
                ))}
              </div>
            )}
            
            {/* Regular Chats Section */}
            <div>
              {waitingChats.length > 0 && regularChats.length > 0 && (
                <div className="px-4 py-2 bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-gray-100">
                  Все сообщения
                </div>
              )}
              {regularChats.map((chat) => (
                <TestChatPreview 
                  key={chat.id}
                  chat={chat} 
                  isSelected={selectedChat?.id === chat.id} 
                  onClick={() => onSelectChat(chat.id)} 
                />
              ))}
            </div>
            
            {filteredChats.length === 0 && (
              <div className="p-8 text-center">
                <p className="text-sm text-gray-400 font-medium">Нет доступных чатов</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

interface TestChatPreviewProps {
  chat: Chat;
  isSelected: boolean;
  onClick: () => void;
}

const TestChatPreview = React.memo(({ chat, isSelected, onClick }: TestChatPreviewProps) => {
  const truncateMessage = (message: string | undefined, maxLength: number = 35) => {
    if (!message) return 'Нет сообщений';
    return message.length > maxLength ? message.substring(0, maxLength) + '...' : message;
  };
  
  const formatTime = (timestamp: string | undefined) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (timestamp: string | undefined) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return formatTime(timestamp);
    }
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  };

  const messengerIcon = () => {
    if (chat.messager === 'telegram') {
      return (
        <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
          <Send size={18} className="text-blue-500" />
        </div>
      );
    }
    if (chat.messager === 'vk') {
      return (
        <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <rect width="24" height="24" rx="6" fill="#2787F5"/>
            <path d="M17.5 8.5C17.7 7.9 17.5 7.5 16.7 7.5H15.5C15 7.5 14.8 7.8 14.6 8.2C14.6 8.2 13.7 10.1 13.1 10.9C12.9 11.1 12.8 11.2 12.7 11.2C12.6 11.2 12.5 11.1 12.5 10.8V8.5C12.5 8 12.4 7.5 11.6 7.5H9.1C8.7 7.5 8.5 7.7 8.5 8C8.5 8.5 9.2 8.6 9.3 10.1V12.1C9.2 12.4 9 12.5 8.8 12.5C8.5 12.5 7.7 11.5 7.2 10.3C7 9.8 6.8 9.5 6.3 9.5H5.5C5.1 9.5 5 9.7 5 10C5 10.5 5.5 11.7 6.6 13.2C7.7 14.7 9.1 15.5 10.3 15.5C10.7 15.5 10.9 15.3 10.9 14.9V14.1C10.9 13.7 11 13.6 11.3 13.6C11.5 13.6 12 13.7 12.6 14.3C13.4 15.1 13.7 15.5 14.3 15.5H15.5C15.9 15.5 16 15.3 16 15C16 14.5 15.3 14.4 14.7 13.7C14.5 13.5 14.5 13.4 14.7 13.1C14.7 13.1 17.1 10.2 17.5 8.5Z" fill="white"/>
          </svg>
        </div>
      );
    }
    return (
      <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
        <MessageSquare size={18} className="text-gray-400" />
      </div>
    );
  };
  
  return (
    <div 
      className={`px-4 py-3 border-b border-gray-100 cursor-pointer transition-colors flex items-center gap-3 ${
        isSelected ? 'bg-gray-50 border-l-2 border-l-gray-900' : 'hover:bg-gray-50'
      }`}
      onClick={onClick}
    >
      {/* Messenger Icon */}
      {messengerIcon()}
      
      {/* Chat Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-0.5">
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {chat.name || `Чат #${chat.uuid}`}
          </h3>
          <span className="text-[10px] text-gray-400 font-medium flex-shrink-0 ml-2">
            Номер чата {chat.id}
          </span>
        </div>
        
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-400 truncate">
            {truncateMessage(chat.lastMessage)}
          </p>
          <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
            <span className="text-[10px] text-gray-300">
              {chat.lastMessageTime && formatDate(chat.lastMessageTime)}
            </span>
            {chat.waiting && (
              <div className="w-2 h-2 rounded-full bg-blue-500" />
            )}
            {chat.ai && (
              <div className="text-[9px] px-1 py-0.5 bg-gray-200 text-gray-500 rounded font-bold">
                ИИ
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default TestChatSidebar;
