import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useNavigate } from "react-router-dom";
import { getAiSettings, putAiSettings, reindexAi } from '@/lib/api';
import { toast } from '@/components/ui/sonner';
import { ArrowLeft, Brain, Database, Sparkles } from 'lucide-react';

const MessageBox = () => {
  const navigate = useNavigate();
  const [systemMessage, setSystemMessage] = useState('');
  const [handoffPhrases, setHandoffPhrases] = useState('');
  const [sitePages, setSitePages] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        const data = await getAiSettings();
        setSystemMessage(data.system_message || '');
        setHandoffPhrases(data.handoff_phrases || '');
        setSitePages(data.site_pages || '');
      } catch (error) {
        console.error('Failed to fetch AI context:', error);
        toast.error('Не удалось загрузить настройки ИИ.');
      } finally {
        setLoading(false);
      }
    };
    fetchContext();
  }, []);

  const handleSubmit = async () => {
    setIsSaving(true);
    try {
      await putAiSettings({
        system_message: systemMessage,
        handoff_phrases: handoffPhrases,
        site_pages: sitePages,
      });
      await reindexAi();
      toast.success('Настройки ИИ сохранены и база знаний обновлена');
    } catch (error) {
      console.error('Failed to send data:', error);
      toast.error('Не удалось сохранить настройки');
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-sm text-gray-500 font-medium">Загрузка настроек...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] bg-gray-50/50 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="h-14 flex items-center px-4 sm:px-6 border-b border-gray-200 bg-white sticky top-0 z-20 shrink-0">
        <div className="flex items-center justify-between w-full max-w-5xl mx-auto gap-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/")}
              className="h-9 w-9 text-gray-500 hover:bg-gray-100 flex-shrink-0"
            >
              <ArrowLeft size={18} />
            </Button>
            <div className="flex items-center gap-2 min-w-0">
              <Brain className="text-blue-600 flex-shrink-0" size={20} />
              <h1 className="text-sm sm:text-base font-bold text-gray-900 truncate">Настройки ИИ</h1>
            </div>
          </div>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={isSaving}
            className="h-8 sm:h-9 px-3 sm:px-6 bg-gray-900 text-white hover:bg-gray-800 text-[10px] sm:text-xs font-bold uppercase tracking-wider"
          >
            {isSaving ? '...' : 'Upd Save'}
          </Button>
        </div>
      </header>

      <main className="flex-1 p-4 sm:p-6 overflow-y-auto scrolling-touch">
        <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6 pb-10">
          
          {/* Left Column: Main Context */}
          <div className="lg:col-span-2 space-y-6">
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2">
                <Sparkles size={16} className="text-blue-500" />
                <h2 className="text-xs font-black text-gray-900 uppercase tracking-widest">Основной контекст</h2>
              </div>
              <div className="p-5">
                <Textarea
                  placeholder="Опишите роль ИИ, его задачи и общую информацию о компании..."
                  className="min-h-[350px] p-4 text-sm leading-relaxed border-gray-100 focus:border-blue-500 focus:ring-0 bg-gray-50/30 rounded-xl resize-none"
                  value={systemMessage}
                  onChange={(e) => setSystemMessage(e.target.value)}
                />
              </div>
            </section>
          </div>

          {/* Right Column: Data Sources */}
          <div className="space-y-6">
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2">
                <Database size={16} className="text-rose-500" />
                <h2 className="text-xs font-black text-gray-900 uppercase tracking-widest">Источники данных</h2>
              </div>
              <div className="p-5 space-y-5">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Фразы для перевода на человека</label>
                  <Textarea
                    placeholder="менеджер&#10;позови человека"
                    className="min-h-[100px] p-3 text-xs bg-gray-50 border-gray-100 focus:border-rose-500 focus:ring-0 rounded-lg resize-none"
                    value={handoffPhrases}
                    onChange={(e) => setHandoffPhrases(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">URL для парсинга</label>
                  <Textarea
                    placeholder="https://site.ru/about"
                    className="min-h-[100px] p-3 text-xs bg-gray-50 border-gray-100 focus:border-rose-500 focus:ring-0 rounded-lg resize-none"
                    value={sitePages}
                    onChange={(e) => setSitePages(e.target.value)}
                  />
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
};

export default MessageBox;
