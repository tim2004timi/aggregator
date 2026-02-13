import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { login, register } from '@/lib/api';
import { Brain, Lock, Mail, User } from 'lucide-react';

const Login = () => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  
  // Login fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  // Register fields
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await login(email, password);
      toast.success('Успешный вход!');
      navigate('/', { replace: true });
    } catch (error: unknown) {
      console.error('Login failed:', error);
      const message = error instanceof Error ? error.message : 'Не удалось войти. Проверьте данные.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();

    if (regPassword !== regConfirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }
    if (regPassword.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }

    setIsLoading(true);
    try {
      await register(regEmail, regPassword, regName);
      toast.success('Аккаунт создан! Входим...');
      
      try {
        await login(regEmail, regPassword);
        navigate('/', { replace: true });
      } catch {
        toast.info('Аккаунт создан. Войдите с вашими данными.');
        setEmail(regEmail);
        setPassword('');
        setMode('login');
      }
    } catch (error: unknown) {
      console.error('Registration failed:', error);
      const message = error instanceof Error ? error.message : 'Не удалось создать аккаунт.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-sm border-none shadow-2xl rounded-3xl overflow-hidden">
        <CardHeader className="space-y-4 text-center pb-6 pt-10 bg-white">
          <div className="mx-auto h-16 w-16 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 shadow-inner">
            <Brain size={32} />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl font-black text-gray-900 tracking-tight">Агрегатор</CardTitle>
            <CardDescription className="text-gray-400 text-xs font-bold uppercase tracking-widest">
              {mode === 'login' ? 'Панель управления' : 'Создание аккаунта менеджера'}
            </CardDescription>
          </div>
        </CardHeader>

        {/* Tabs */}
        <div className="bg-white px-8">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode('login')}
              className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider rounded-xl transition-all ${
                mode === 'login'
                  ? 'bg-[#1F1F1F] text-white shadow-md'
                  : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
              }`}
            >
              Вход
            </button>
            <button
              type="button"
              onClick={() => setMode('register')}
              className={`flex-1 py-2.5 text-xs font-bold uppercase tracking-wider rounded-xl transition-all ${
                mode === 'register'
                  ? 'bg-[#1F1F1F] text-white shadow-md'
                  : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
              }`}
            >
              Регистрация
            </button>
          </div>
        </div>

        <CardContent className="bg-white px-8 pt-6">
          {mode === 'login' ? (
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="login-email" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="login-email"
                    type="email"
                    placeholder="manager@example.com"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="login-password" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Пароль
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="login-password"
                    type="password"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <Button
                type="submit"
                className="w-full h-12 bg-gray-900 text-white hover:bg-gray-800 rounded-xl font-bold text-sm shadow-lg shadow-gray-200 transition-all active:scale-[0.98]"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Вход...</span>
                  </div>
                ) : 'Войти в систему'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="reg-name" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Имя (Никнейм)
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="reg-name"
                    type="text"
                    placeholder="Иван Менеджер"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-email" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="reg-email"
                    type="email"
                    placeholder="manager@example.com"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-password" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Пароль
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="reg-password"
                    type="password"
                    placeholder="Минимум 6 символов"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="reg-confirm" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                  Подтвердите пароль
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                  <Input
                    id="reg-confirm"
                    type="password"
                    placeholder="Повторите пароль"
                    className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                    value={regConfirmPassword}
                    onChange={(e) => setRegConfirmPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <Button
                type="submit"
                className="w-full h-12 bg-gray-900 text-white hover:bg-gray-800 rounded-xl font-bold text-sm shadow-lg shadow-gray-200 transition-all active:scale-[0.98]"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Создание...</span>
                  </div>
                ) : 'Создать аккаунт'}
              </Button>
            </form>
          )}
        </CardContent>
        <CardFooter className="bg-white pb-10 pt-6">
          <p className="text-[10px] text-center w-full text-gray-300 font-bold uppercase tracking-tighter">
            Secure Access • 2026
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default Login;
