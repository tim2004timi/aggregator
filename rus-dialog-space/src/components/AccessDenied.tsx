import React from 'react';

export const AccessDenied: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Доступ запрещен</h1>
          <p className="text-gray-600 mb-4">
            Извините, но у вас нет доступа к этому ресурсу.
          </p>
          <p className="text-sm text-gray-500">
            Пожалуйста, обратитесь к администратору для получения доступа.
          </p>
        </div>
      </div>
    </div>
  );
}; 