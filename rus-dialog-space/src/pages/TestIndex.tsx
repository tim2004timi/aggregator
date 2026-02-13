import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { useChat } from '@/contexts/ChatContext';
import { ArrowLeft, User as UserIcon } from 'lucide-react';
import { getCurrentUser, User, Chat } from '@/lib/api';
import TestChatSidebar from '@/components/TestChatSidebar';
import TestChatView from '@/components/TestChatView';

const TestIndex = () => {
  const { selectedChat, selectChat } = useChat();
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(console.error);
  }, []);

  const handleChatDeleted = () => {
    selectChat(null);
  };

  return (
    <div className="h-[100dvh] flex flex-col overflow-hidden bg-gray-100">
      {/* Mobile Back Button */}
      {selectedChat && (
        <div className="md:hidden flex-shrink-0 bg-white border-b border-gray-200">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => selectChat(null)}
            className="w-full justify-start px-4 py-3 text-gray-700 hover:bg-gray-100"
          >
            <ArrowLeft size={16} className="mr-2" />
            Назад к чатам
          </Button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Chat List */}
        <div className={`w-full md:w-[360px] lg:w-[400px] flex-shrink-0 flex flex-col bg-white border-r border-gray-200 ${selectedChat ? 'hidden md:flex' : 'flex'}`}>
          <TestChatSidebar
            onSelectChat={selectChat}
          />
        </div>
        
        {/* Center Panel - Chat View */}
        <div className={`flex-1 flex flex-col bg-white ${!selectedChat ? 'hidden md:flex' : 'flex'} overflow-hidden`}>
          <TestChatView 
            chatId={selectedChat?.id || null}
            onChatDeleted={handleChatDeleted}
          />
        </div>

        {/* Right Panel - Client Data */}
        <div className="hidden lg:flex w-[300px] xl:w-[340px] flex-shrink-0 flex-col bg-white border-l border-gray-200">
          <ClientDataPanel chat={selectedChat} currentUser={currentUser} />
        </div>
      </div>
    </div>
  );
};

interface ClientDataPanelProps {
  chat: Chat | null;
  currentUser: User | null;
}

const ClientDataPanel = ({ chat, currentUser }: ClientDataPanelProps) => {
  if (!chat) {
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-2xl flex items-center justify-center">
            <UserIcon size={28} className="text-gray-300" />
          </div>
          <p className="text-sm text-gray-400 font-medium">Выберите чат для просмотра данных клиента</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-200">
        <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Данные клиента</h3>
      </div>

      {/* Client Info */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {/* Avatar + Name */}
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 flex-shrink-0">
            <UserIcon size={24} />
          </div>
          <div className="min-w-0">
            <p className="text-base font-semibold text-gray-900 truncate">
              {chat.name || 'Не указано'}
            </p>
            <p className="text-xs text-gray-400">
              ID: {chat.uuid}
            </p>
          </div>
        </div>

        {/* Info Fields */}
        <div className="space-y-4">
          <InfoField label="Мессенджер" value={
            chat.messager === 'telegram' ? 'Telegram' :
            chat.messager === 'vk' ? 'ВКонтакте' :
            chat.messager || 'Не указан'
          } />
          <InfoField label="Номер чата" value={`#${chat.id}`} />
          <InfoField label="Статус" value={
            chat.dialog_status === 'assigned' ? 'В работе' :
            chat.dialog_status === 'closed' ? 'Закрыт' :
            'Новый'
          } />
          {chat.assigned_manager_name && (
            <InfoField label="Менеджер" value={chat.assigned_manager_name} />
          )}
          {chat.tags && chat.tags.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Теги</p>
              <div className="flex flex-wrap gap-1.5">
                {chat.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-lg font-medium"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Current Manager Section */}
        {currentUser && (
          <div className="pt-4 border-t border-gray-100">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Вы</p>
            <div className="flex items-center gap-3 bg-gray-50 p-3 rounded-xl">
              <div className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {(currentUser.name || currentUser.email || '?')[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{currentUser.name || currentUser.email}</p>
                <p className="text-xs text-gray-400 truncate">{currentUser.email}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const InfoField = ({ label, value }: { label: string; value: string }) => (
  <div>
    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">{label}</p>
    <p className="text-sm text-gray-900 font-medium">{value}</p>
  </div>
);

export default TestIndex;
