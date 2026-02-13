import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { register, login } from '@/lib/api';
import { Brain, Lock, Mail, User } from 'lucide-react';

const Register = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error('Пароли не совпадают');
      return;
    }

    if (password.length < 6) {
      toast.error('Пароль должен быть не менее 6 символов');
      return;
    }

    setIsLoading(true);

    try {
      await register(email, password, name);
      toast.success('Аккаунт успешно создан!');
      
      // Auto-login after registration
      try {
        await login(email, password);
        navigate('/', { replace: true });
      } catch {
        // If auto-login fails, redirect to login page
        navigate('/login', { replace: true });
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
            <CardTitle className="text-2xl font-black text-gray-900 tracking-tight">Регистрация</CardTitle>
            <CardDescription className="text-gray-400 text-xs font-bold uppercase tracking-widest">
              Создание аккаунта менеджера
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="bg-white px-8">
          <form onSubmit={handleRegister} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="name" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                Имя (Никнейм)
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                <Input
                  id="name"
                  type="text"
                  placeholder="Иван Менеджер"
                  className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="email" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                <Input
                  id="email"
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
              <label htmlFor="password" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                Пароль
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                <Input
                  id="password"
                  type="password"
                  placeholder="Минимум 6 символов"
                  className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                Подтвердите пароль
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300" size={18} />
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="Повторите пароль"
                  className="pl-10 h-12 bg-gray-50 border-gray-100 focus:border-blue-500 focus:ring-0 rounded-xl text-sm"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
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
        </CardContent>
        <CardFooter className="bg-white pb-10 pt-4 flex flex-col gap-3">
          <Link
            to="/login"
            className="text-sm text-gray-500 hover:text-gray-700 font-medium transition-colors"
          >
            Уже есть аккаунт? Войти
          </Link>
          <p className="text-[10px] text-center w-full text-gray-300 font-bold uppercase tracking-tighter">
            Secure Access • 2026
          </p>
        </CardFooter>
      </Card>
    </div>
  );
};

export default Register;

