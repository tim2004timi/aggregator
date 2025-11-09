import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useNavigate } from "react-router-dom";
import { getAiContext, putAiContext } from '@/lib/api';
import { toast } from '@/components/ui/sonner';

const MessageBox = () => {
  const navigate = useNavigate();
  const [systemMessage, setSystemMessage] = useState('');
  const [faqs, setFaqs] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        const data = await getAiContext();
        setSystemMessage(data.system_message || '');
        setFaqs(data.faqs || '');
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
      await putAiContext(systemMessage, faqs);
      toast.success('Контекст и FAQ успешно отправлены!');
    } catch (error) {
      console.error('Failed to send data:', error);
      toast.error('Не удалось отправить данные.');
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
          
          <div className="flex justify-end">
            <Button
              className="bg-black text-white hover:bg-gray-800"
              onClick={handleSubmit}
              disabled={loading}
            >
              Отправить
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageBox; 