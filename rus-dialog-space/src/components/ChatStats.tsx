import { useEffect, useState } from 'react';
import { getChatStats } from '@/lib/api';
import { MessageSquare, Send, CircleDot, Settings } from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

const ChatStats = () => {
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    ai: 0
  });
  const [loading, setLoading] = useState(true);
  const { lastMessage, lastUpdate } = useWebSocket();
  const navigate = useNavigate();

  const fetchStats = async () => {
    try {
      const statsData = await getChatStats();
      setStats(statsData);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (!lastUpdate) return;
    if (lastUpdate.type === 'stats_update' && typeof lastUpdate.total === 'number') {
      setStats({
        total: lastUpdate.total,
        pending: lastUpdate.pending,
        ai: lastUpdate.ai
      });
      setLoading(false);
    } else {
      fetchStats();
    }
  }, [lastUpdate]);

  return (
    <div className="bg-white border-b border-gray-300 py-3 px-4 flex items-center h-14">
      {loading ? (
        <div className="text-sm text-gray-500">Загрузка статистики...</div>
      ) : (
        <div className="flex space-x-6 w-full">
          <div className="flex items-center">
            <MessageSquare size={18} className="text-gray-500 mr-2" />
            <div>
              <p className="text-xs text-gray-500">Всего чатов</p>
              <p className="text-sm font-medium">{stats.total}</p>
            </div>
          </div>
          
          <div className="flex items-center">
            <CircleDot size={18} className="text-unread mr-2" />
            <div>
              <p className="text-xs text-gray-500">Ожидают ответа</p>
              <p className="text-sm font-medium">{stats.pending}</p>
            </div>
          </div>
          
          <div className="flex items-center">
            <div className="w-4 h-4 bg-aiHighlight/20 rounded-sm flex items-center justify-center text-aiHighlight text-xs font-bold mr-2">
              A
            </div>
            <div>
              <p className="text-xs text-gray-500">ИИ чаты</p>
              <p className="text-sm font-medium">{stats.ai}</p>
            </div>
          </div>
          <div className="ml-auto">
            <Button
              variant="outline"
              size="icon"
              onClick={() => navigate('/message-box')}
              className="w-10 h-10 border-gray-300 hover:bg-gray-100"
            >
              <Settings size={20} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatStats;
