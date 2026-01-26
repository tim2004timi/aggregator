import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useNavigate } from "react-router-dom";
import { getAiSettings, putAiSettings, reindexAi, getAiStatus } from '@/lib/api';
import { toast } from '@/components/ui/sonner';

const MessageBox = () => {
  const navigate = useNavigate();
  const [systemMessage, setSystemMessage] = useState('');
  const [faqs, setFaqs] = useState('');
  const [rules, setRules] = useState('');
  const [tone, setTone] = useState('');
  const [handoffPhrases, setHandoffPhrases] = useState('');
  const [minScore, setMinScore] = useState(0.2);
  const [sitePages, setSitePages] = useState('');
  const [autoRefreshMinutes, setAutoRefreshMinutes] = useState(0);
  const [status, setStatus] = useState<{ last_indexed?: string; last_error?: string; chunks?: number }>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        const data = await getAiSettings();
        setSystemMessage(data.system_message || '');
        setFaqs(data.faqs || '');
        setRules(data.rules || '');
        setTone(data.tone || '');
        setHandoffPhrases(data.handoff_phrases || '');
        setMinScore(typeof data.min_score === 'number' ? data.min_score : 0.2);
        setSitePages(data.site_pages || '');
        setAutoRefreshMinutes(typeof data.auto_refresh_minutes === 'number' ? data.auto_refresh_minutes : 0);
        const s = await getAiStatus();
        setStatus(s || {});
      } catch (error) {
        console.error('Failed to fetch AI context:', error);
        toast.error('Не удалось загрузить контекст ИИ.');
      } finally {
        setLoading(false);
      }
    };
    fetchContext();
  }, []);

  const handleSubmit = async () => {
    try {
      await putAiSettings({
        system_message: systemMessage,
        faqs,
        rules,
        tone,
        handoff_phrases: handoffPhrases,
        min_score: Number(minScore),
        site_pages: sitePages,
        auto_refresh_minutes: Number(autoRefreshMinutes),
      });
      toast.success('Настройки ИИ успешно обновлены!');
      const s = await getAiStatus();
      setStatus(s || {});
    } catch (error) {
      console.error('Failed to send data:', error);
      toast.error('Не удалось отправить данные.');
    }
  };

  const handleReindex = async () => {
    try {
      const result = await reindexAi();
      if (result.ok) {
        toast.success(`Индекс обновлен (${result.chunks || 0} фрагментов)`);
      } else {
        toast.error(result.error || 'Не удалось обновить индекс');
      }
      const s = await getAiStatus();
      setStatus(s || {});
    } catch (error) {
      console.error('Reindex error:', error);
      toast.error('Не удалось обновить индекс.');
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Добавить контекст для ИИ</h1>
          <Button
            variant="outline"
            onClick={() => navigate("/")}
            className="hover:bg-gray-100"
          >
            Назад
          </Button>
        </div>
        
        <div className="space-y-8">
          {/* AI Context Section */}
          <div className="space-y-4">
            <label className="text-sm font-medium text-gray-700">Контекст ИИ</label>
            {loading ? (
              <div className="text-center text-gray-500">Загрузка контекста...</div>
            ) : (
              <Textarea
                placeholder="Введите контекст для ИИ..."
                className="min-h-[300px] p-4 text-base border-gray-200 focus:border-gray-400 focus:ring-gray-400"
                value={systemMessage}
                onChange={(e) => setSystemMessage(e.target.value)}
              />
            )}
          </div>

          {/* FAQs Section */}
          <div className="space-y-4">
            <label className="text-sm font-medium text-gray-700">Часто задаваемые вопросы</label>
            <Textarea
              placeholder="Введите часто задаваемые вопросы..."
              className="min-h-[200px] p-4 text-base border-gray-200 focus:border-gray-400 focus:ring-gray-400"
              value={faqs}
              onChange={(e) => setFaqs(e.target.value)}
            />
          </div>

          <div className="space-y-4">
            <label className="text-sm font-medium text-gray-700">Правила ответа</label>
            <Textarea
              placeholder="Правила, ограничения, условия передачи менеджеру..."
              className="min-h-[180px] p-4 text-base border-gray-200 focus:border-gray-400 focus:ring-gray-400"
              value={rules}
              onChange={(e) => setRules(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Тон общения</label>
              <Input
                placeholder="дружелюбный, лаконичный"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Минимальная уверенность (0–1)</label>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="space-y-4">
            <label className="text-sm font-medium text-gray-700">Фразы для передачи менеджеру (по одной в строке)</label>
            <Textarea
              placeholder="хочу человека&#10;менеджер&#10;не бот"
              className="min-h-[140px] p-4 text-base border-gray-200 focus:border-gray-400 focus:ring-gray-400"
              value={handoffPhrases}
              onChange={(e) => setHandoffPhrases(e.target.value)}
            />
          </div>

          <div className="space-y-4">
            <label className="text-sm font-medium text-gray-700">Страницы сайта для парсинга (URL, по одной в строке)</label>
            <Textarea
              placeholder="https://site.ru/delivery&#10;https://site.ru/returns"
              className="min-h-[140px] p-4 text-base border-gray-200 focus:border-gray-400 focus:ring-gray-400"
              value={sitePages}
              onChange={(e) => setSitePages(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Автообновление базы (минуты)</label>
              <Input
                type="number"
                min={0}
                step={5}
                value={autoRefreshMinutes}
                onChange={(e) => setAutoRefreshMinutes(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Статус индекса</label>
              <div className="text-sm text-gray-600">
                {status.last_indexed ? `Обновлено: ${status.last_indexed}` : 'Не обновлялось'}
                {typeof status.chunks === 'number' ? ` • Фрагменты: ${status.chunks}` : ''}
                {status.last_error ? ` • Ошибка: ${status.last_error}` : ''}
              </div>
            </div>
          </div>
          
          <div className="flex justify-end">
            <Button
              className="bg-black text-white hover:bg-gray-800"
              onClick={handleSubmit}
              disabled={loading}
            >
              Отправить
            </Button>
            <Button
              className="ml-3"
              variant="outline"
              onClick={handleReindex}
              disabled={loading}
            >
              Обновить индекс
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageBox; 