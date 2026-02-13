import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAllAnalytics, getAnalyticsStats, DialogAnalytics } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { ArrowLeft, BarChart3, ChevronRight, TrendingUp, MessageSquare } from 'lucide-react';

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
  const [selectedId, setSelectedId] = useState<number | null>(null);

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

  const getSentimentBadge = (sentiment: string) => {
    const styles: Record<string, string> = {
      positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      negative: 'bg-red-50 text-red-700 border-red-200',
      neutral: 'bg-gray-50 text-gray-700 border-gray-200',
    };
    const labels: Record<string, string> = {
      positive: 'Позитивный',
      negative: 'Негативный', 
      neutral: 'Нейтральный',
    };
    return (
      <span className={`px-2 py-0.5 text-[10px] font-medium rounded border ${styles[sentiment] || styles.neutral}`}>
        {labels[sentiment] || sentiment}
      </span>
    );
  };

  const selected = analytics.find(a => a.id === selectedId);

  return (
    <div className="h-[100dvh] flex flex-col bg-white overflow-hidden">
      {/* Header */}
      <header className="h-14 flex items-center px-4 border-b border-gray-300 bg-white shrink-0">
        <div className="flex items-center gap-4 w-full">
          <Button
            variant="ghost"
            size="icon"
            onClick={selectedId ? () => setSelectedId(null) : () => navigate('/')}
            className="h-9 w-9 text-gray-500 hover:bg-gray-100"
          >
            <ArrowLeft size={18} />
          </Button>
          <div className="flex items-center gap-2">
            <BarChart3 className="text-gray-500" size={18} />
            <h1 className="text-base font-semibold text-gray-900 truncate">
              {selectedId ? `Анализ #${selectedId}` : 'Аналитика'}
            </h1>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-hidden flex flex-col relative">
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center gap-3 text-gray-500">
              <div className="w-5 h-5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
              <span className="text-sm">Загрузка...</span>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex overflow-hidden">
            {/* Sidebar List */}
            <div className={`${selectedId ? 'hidden md:flex' : 'flex'} w-full md:w-1/3 lg:w-3/10 flex flex-col border-r border-gray-300 bg-white`}>
              {/* Stats Summary in Sidebar */}
              <div className="p-4 border-b border-gray-200 grid grid-cols-1 gap-3 bg-gray-50/50">
                <div className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 shrink-0">
                      <MessageSquare size={20} />
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400 uppercase font-bold leading-none mb-1">Всего диалогов</p>
                      <p className="text-xl font-black text-gray-900 leading-none">{stats?.total_dialogs || 0}</p>
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-xl shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 bg-emerald-50 rounded-lg flex items-center justify-center text-emerald-600 shrink-0">
                      <TrendingUp size={20} />
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400 uppercase font-bold leading-none mb-1">Среднее качество</p>
                      <p className="text-xl font-black text-gray-900 leading-none">
                        {stats?.avg_quality_score != null ? stats.avg_quality_score.toFixed(1) : '—'}
                        <span className="text-sm font-normal text-gray-400 ml-1">/ 10</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto scrolling-touch">
                <div className="px-4 py-2 bg-gray-100 text-[11px] font-medium text-gray-500 uppercase tracking-wider border-b border-gray-200 sticky top-0 z-10">
                  История анализов
                </div>
                
                {analytics.length === 0 ? (
                  <div className="p-8 text-center">
                    <BarChart3 className="text-gray-300 mx-auto mb-2" size={24} />
                    <p className="text-gray-500 text-xs">
                      Нет данных
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {analytics.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => setSelectedId(item.id)}
                        className={`w-full text-left px-4 py-4 hover:bg-gray-50 transition-colors flex items-start gap-3 ${
                          selectedId === item.id ? 'bg-gray-100' : ''
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">Чат #{item.chat_id}</span>
                            <span className="text-[10px] text-gray-400">
                              {new Date(item.created_at).toLocaleDateString('ru-RU', {
                                day: 'numeric',
                                month: 'short'
                              })}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500 truncate mb-2">
                            {item.summary || 'Без описания'}
                          </p>
                          <div className="flex items-center gap-2">
                            {item.customer_sentiment && getSentimentBadge(item.customer_sentiment)}
                            {item.manager_quality_score !== undefined && (
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                item.manager_quality_score >= 7 ? 'bg-emerald-50 text-emerald-700' :
                                item.manager_quality_score >= 4 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'
                              }`}>
                                {item.manager_quality_score}/10
                              </span>
                            )}
                          </div>
                        </div>
                        <ChevronRight 
                          size={16} 
                          className="text-gray-400 mt-1"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Main Content Area */}
            <div className={`${selectedId ? 'flex' : 'hidden md:flex'} flex-1 flex-col bg-gray-50 overflow-y-auto p-4 sm:p-6 scrolling-touch pb-10`}>
              {selected ? (
                <div className="max-w-3xl mx-auto w-full space-y-6">
                  <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 sm:px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between bg-white gap-3">
                      <div>
                        <h3 className="text-base sm:text-lg font-semibold text-gray-900">Анализ чата #{selected.chat_id}</h3>
                        <p className="text-[10px] sm:text-xs text-gray-500">
                          {new Date(selected.created_at).toLocaleString('ru-RU', {
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/?chat=${selected.chat_id}`)}
                        className="text-xs border-gray-300 h-8 self-start sm:self-auto"
                      >
                        Перейти к чату
                      </Button>
                    </div>
                    
                    <div className="p-4 sm:p-6 space-y-6">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="p-3 sm:p-4 bg-gray-50 rounded-lg border border-gray-200">
                          <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-1">Тональность</p>
                          <div className="flex items-center gap-2">
                            {selected.customer_sentiment && getSentimentBadge(selected.customer_sentiment)}
                          </div>
                        </div>
                        <div className="p-3 sm:p-4 bg-gray-50 rounded-lg border border-gray-200">
                          <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-1">Качество</p>
                          <div className="flex items-center gap-2">
                            <span className={`text-lg sm:text-xl font-bold ${
                              selected.manager_quality_score && selected.manager_quality_score >= 7 ? 'text-emerald-600' :
                              selected.manager_quality_score && selected.manager_quality_score >= 4 ? 'text-amber-600' : 'text-red-600'
                            }`}>
                              {selected.manager_quality_score}/10
                            </span>
                          </div>
                        </div>
                      </div>

                      {selected.summary && (
                        <DetailBlock title="Краткое содержание" color="slate">
                          {selected.summary}
                        </DetailBlock>
                      )}
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {selected.customer_problem && (
                          <DetailBlock title="Проблема" color="rose">
                            {selected.customer_problem}
                          </DetailBlock>
                        )}

                        {selected.customer_intent && (
                          <DetailBlock title="Намерение" color="blue">
                            {selected.customer_intent}
                          </DetailBlock>
                        )}
                      </div>

                      {selected.manager_quality_notes && (
                        <DetailBlock title="Комментарий" color="purple">
                          {selected.manager_quality_notes}
                        </DetailBlock>
                      )}

                      {selected.key_topics && selected.key_topics.length > 0 && (
                        <div>
                          <h4 className="text-[10px] font-semibold text-gray-700 uppercase tracking-wider mb-3">Темы</h4>
                          <div className="flex flex-wrap gap-2">
                            {selected.key_topics.map((topic, i) => (
                              <span 
                                key={i} 
                                className="px-2 py-1 bg-white border border-gray-200 text-gray-700 rounded-md text-[10px] sm:text-xs font-medium shadow-sm"
                              >
                                #{topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {selected.recommendations && (
                        <DetailBlock title="Рекомендации" color="emerald">
                          {selected.recommendations}
                        </DetailBlock>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center p-4">
                    <div className="w-14 h-14 sm:w-16 sm:h-16 mx-auto mb-4 bg-white border border-gray-200 rounded-2xl flex items-center justify-center shadow-sm">
                      <BarChart3 className="text-gray-300 w-6 h-6 sm:w-7 sm:h-7" />
                    </div>
                    <p className="text-gray-500 text-xs sm:text-sm">Выберите анализ для просмотра</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

const DetailBlock = ({ 
  title, 
  color, 
  children 
}: { 
  title: string; 
  color: 'slate' | 'rose' | 'blue' | 'purple' | 'emerald'; 
  children: React.ReactNode;
}) => {
  const colors = {
    slate: 'bg-white border-gray-200',
    rose: 'bg-red-50/30 border-red-100',
    blue: 'bg-blue-50/30 border-blue-100',
    purple: 'bg-purple-50/30 border-purple-100',
    emerald: 'bg-emerald-50/30 border-emerald-100',
  };
  const titleColors = {
    slate: 'text-gray-700',
    rose: 'text-red-700',
    blue: 'text-blue-700',
    purple: 'text-purple-700',
    emerald: 'text-emerald-700',
  };
  
  return (
    <div className={`rounded-xl border p-4 shadow-sm ${colors[color]}`}>
      <h4 className={`text-[11px] font-bold uppercase tracking-wider mb-2 ${titleColors[color]}`}>{title}</h4>
      <p className="text-gray-600 text-sm leading-relaxed">{children}</p>
    </div>
  );
};

export default Analytics;
