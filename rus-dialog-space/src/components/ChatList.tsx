import React, { useState, useEffect, useCallback } from 'react';
import { Chat, getChats } from '@/lib/api';
import { useWebSocket } from '../contexts/WebSocketContext';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

interface ChatListProps {
  onSelectChat: (chatId: string) => void;
  selectedChatId: string | null;
}

export const ChatList: React.FC<ChatListProps> = ({ onSelectChat, selectedChatId }) => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { lastUpdate } = useWebSocket();
  const [searchQuery, setSearchQuery] = useState('');

  const loadChats = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getChats();
      console.log('Loaded chats with tags:', data.map(chat => ({
        id: chat.id,
        name: chat.name,
        tags: chat.tags
      })));
      setChats(data);
    } catch (error) {
      console.error('Error loading chats:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChats();
  }, [loadChats]);

  // Refresh chats when receiving an update
  useEffect(() => {
    if (lastUpdate) {
      console.log('Received chat update:', lastUpdate);
      loadChats();
    }
  }, [lastUpdate, loadChats]);

  const filteredChats = chats.filter(chat => {
    const matchesSearch = chat.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         chat.lastMessage?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         chat.tags?.some((tag: string) => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesSearch;
  });

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
          <Input
            type="text"
            placeholder="Поиск по чатам и тегам..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {filteredChats.map((chat) => {
          console.log('Rendering chat:', chat.id, 'with tags:', chat.tags);
          return (
            <div
              key={chat.id}
              className={`p-4 border-b cursor-pointer hover:bg-gray-50 ${
                selectedChatId === chat.uuid ? 'bg-blue-50' : ''
              }`}
              onClick={() => onSelectChat(chat.uuid)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="font-medium">
                    {chat.name || `Чат #${chat.id}`}
                    {chat.ai && (
                      <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                        AI
                      </span>
                    )}
                  </div>
                  {chat.tags && chat.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {chat.tags.map((tag: string) => (
                        <span
                          key={tag}
                          className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {chat.lastMessage && (
                    <div className="text-sm text-gray-600 mt-1 truncate">
                      {chat.lastMessage}
                    </div>
                  )}
                </div>
                {chat.waiting && (
                  <div className="ml-2">
                    <div className="animate-pulse h-2 w-2 bg-blue-500 rounded-full"></div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}; 