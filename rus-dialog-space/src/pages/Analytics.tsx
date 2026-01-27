import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAllAnalytics, getAnalyticsStats, DialogAnalytics } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ArrowLeft, BarChart3, TrendingUp, Users, MessageSquare } from 'lucide-react';

const Analytics = () => {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<DialogAnalytics[]>([]);
  const [stats, setStats] = useState<{
    total_dialogs: number;
    avg_quality_score: number;
    sentiment_distribution: Record<string, number>;
    resolution_distribution: Record<string, number>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAnalytics, setSelectedAnalytics] = useState<DialogAnalytics | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      const [analyticsData, statsData] = await Promise.all([
        getAllAnalytics(),
        getAnalyticsStats(),
      ]);
      setAnalytics(analyticsData);
      setStats(statsData);
      setLoading(false);
    };
    loadData();
  }, []);

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'bg-green-100 text-green-700';
      case 'negative': return 'bg-red-100 text-red-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const getSentimentLabel = (sentiment: string) => {
    switch (sentiment) {
      case 'positive': return 'Позитивное';
      case 'negative': return 'Негативное';
      default: return 'Нейтральное';
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/')}
          >
            <ArrowLeft size={20} />
          </Button>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <BarChart3 className="text-blue-500" />
            Аналитика диалогов
          </h1>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-gray-500">Загрузка...</p>
          </div>
        ) : (
          <div className="space-y-6 max-w-6xl mx-auto">
            {/* Stats Cards */}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg p-4 shadow-sm border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-100 rounded-lg">
                      <MessageSquare className="text-blue-600" size={24} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stats.total_dialogs}</p>
                      <p className="text-sm text-gray-500">Всего диалогов</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4 shadow-sm border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-100 rounded-lg">
                      <TrendingUp className="text-purple-600" size={24} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stats.avg_quality_score?.toFixed(1) || '—'}</p>
                      <p className="text-sm text-gray-500">Ср. качество</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4 shadow-sm border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-green-100 rounded-lg">
                      <Users className="text-green-600" size={24} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stats.sentiment_distribution?.positive || 0}</p>
                      <p className="text-sm text-gray-500">Довольных</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4 shadow-sm border">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-yellow-100 rounded-lg">
                      <BarChart3 className="text-yellow-600" size={24} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stats.resolution_distribution?.resolved || 0}</p>
                      <p className="text-sm text-gray-500">Решено</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Analytics List */}
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="p-4 border-b">
                <h2 className="font-semibold">История анализов</h2>
              </div>
              
              {analytics.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  Нет данных аналитики. Проанализируйте чаты с помощью кнопки 
                  <BarChart3 className="inline mx-1" size={16} /> в заголовке чата.
                </div>
              ) : (
                <div className="divide-y">
                  {analytics.map((item) => (
                    <div
                      key={item.id}
                      className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => setSelectedAnalytics(selectedAnalytics?.id === item.id ? null : item)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">Чат #{item.chat_id}</span>
                            {item.customer_sentiment && (
                              <span className={`px-2 py-0.5 rounded text-xs ${getSentimentColor(item.customer_sentiment)}`}>
                                {getSentimentLabel(item.customer_sentiment)}
                              </span>
                            )}
                            {item.manager_quality_score !== undefined && (
                              <span className="px-2 py-0.5 rounded text-xs bg-purple-100 text-purple-700">
                                Оценка: {item.manager_quality_score}/10
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 line-clamp-2">{item.summary || 'Нет описания'}</p>
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(item.created_at).toLocaleString('ru-RU')}
                          </p>
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {selectedAnalytics?.id === item.id && (
                        <div className="mt-4 pt-4 border-t space-y-3">
                          {item.customer_problem && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Проблема клиента</h4>
                              <p className="text-sm text-gray-600">{item.customer_problem}</p>
                            </div>
                          )}
                          {item.customer_intent && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Намерение</h4>
                              <p className="text-sm text-gray-600">{item.customer_intent}</p>
                            </div>
                          )}
                          {item.manager_quality_notes && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Комментарий по качеству</h4>
                              <p className="text-sm text-gray-600">{item.manager_quality_notes}</p>
                            </div>
                          )}
                          {item.key_topics && item.key_topics.length > 0 && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Ключевые темы</h4>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {item.key_topics.map((topic, i) => (
                                  <span key={i} className="px-2 py-0.5 bg-gray-100 rounded text-xs">{topic}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {item.recommendations && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700">Рекомендации</h4>
                              <p className="text-sm text-gray-600">{item.recommendations}</p>
                            </div>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/?chat=${item.chat_id}`);
                            }}
                          >
                            Открыть чат
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Analytics;

