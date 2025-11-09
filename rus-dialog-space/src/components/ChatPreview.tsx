interface ChatPreviewProps {
  chat: {
    id: number;
    uuid: string;
    waiting: boolean;
    ai: boolean;
    lastMessage?: string;
    lastMessageTime?: string;
    name?: string;
    tags?: string[];
    messager?: string;
  };
  isSelected: boolean;
  onClick: () => void;
}

const VKIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="24" height="24" rx="6" fill="#2787F5"/>
    <path d="M17.5 8.5C17.7 7.9 17.5 7.5 16.7 7.5H15.5C15 7.5 14.8 7.8 14.6 8.2C14.6 8.2 13.7 10.1 13.1 10.9C12.9 11.1 12.8 11.2 12.7 11.2C12.6 11.2 12.5 11.1 12.5 10.8V8.5C12.5 8 12.4 7.5 11.6 7.5H9.1C8.7 7.5 8.5 7.7 8.5 8C8.5 8.5 9.2 8.6 9.3 10.1V12.1C9.2 12.4 9 12.5 8.8 12.5C8.5 12.5 7.7 11.5 7.2 10.3C7 9.8 6.8 9.5 6.3 9.5H5.5C5.1 9.5 5 9.7 5 10C5 10.5 5.5 11.7 6.6 13.2C7.7 14.7 9.1 15.5 10.3 15.5C10.7 15.5 10.9 15.3 10.9 14.9V14.1C10.9 13.7 11 13.6 11.3 13.6C11.5 13.6 12 13.7 12.6 14.3C13.4 15.1 13.7 15.5 14.3 15.5H15.5C15.9 15.5 16 15.3 16 15C16 14.5 15.3 14.4 14.7 13.7C14.5 13.5 14.5 13.4 14.7 13.1C14.7 13.1 17.1 10.2 17.5 8.5Z" fill="white"/>
  </svg>
);

const ChatPreview = ({ chat, isSelected, onClick }: ChatPreviewProps) => {
  console.log('Rendering ChatPreview for chat:', chat.uuid, 'waiting:', chat.waiting);
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
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="12" fill="#229ED9"/>
              <path d="M17.5 7.5L15.5 17.5C15.5 17.5 15.2 18.3 14.3 17.9L10.7 15.2L9.2 16.6C9.2 16.6 9.1 16.7 8.9 16.7L9.1 13.9L15.1 8.7C15.1 8.7 15.2 8.6 15.1 8.6C15.1 8.6 15 8.6 14.9 8.6L8.2 11.2L5.5 10.4C5.5 10.4 5.1 10.2 5.2 9.9C5.2 9.9 5.2 9.8 5.5 9.7L16.5 7.2C16.5 7.2 17.5 7 17.5 7.5Z" fill="white"/>
            </svg>
          ) : chat.messager === 'vk' ? (
            <VKIcon />
          ) : (
            chat.uuid.charAt(0).toUpperCase()
          )}
        </div>
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-medium text-gray-900 truncate">
            {chat.name || `Чат #${chat.uuid}`}
          </h3>
          <span className="text-xs text-gray-500">
            {chat.lastMessageTime && formatTime(chat.lastMessageTime)}
          </span>
        </div>
        
        {chat.tags && chat.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {chat.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
        
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
}; 