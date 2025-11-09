import React, { useState, useRef, useEffect } from 'react';
import { X, Plus, Check } from 'lucide-react';
import { addChatTag, removeChatTag } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/sonner';

interface ChatTagsProps {
  chatId: number;
  tags: string[];
  onTagsUpdate: (tags: string[]) => void;
}

export const ChatTags: React.FC<ChatTagsProps> = ({ chatId, tags, onTagsUpdate }) => {
  const [isAdding, setIsAdding] = useState(false);
  const [newTag, setNewTag] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isAdding && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isAdding]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsAdding(false);
        setNewTag('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleAddTag = async () => {
    if (!newTag.trim()) return;
    
    try {
      const result = await addChatTag(chatId, newTag.trim());
      if (result.success) {
        onTagsUpdate(result.tags);
        setNewTag('');
        setIsAdding(false);
        toast.success('Тег добавлен');
      }
    } catch (error) {
      console.error('Failed to add tag:', error);
    }
  };

  const handleRemoveTag = async (tag: string) => {
    try {
      const result = await removeChatTag(chatId, tag);
      if (result.success) {
        onTagsUpdate(result.tags);
        toast.success('Тег удален');
      }
    } catch (error) {
      console.error('Failed to remove tag:', error);
    }
  };

  return (
    <div className="flex items-center gap-2" ref={containerRef}>
      {tags.map((tag) => (
        <div
          key={tag}
          className="flex items-center gap-1 px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-md text-sm text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <span>{tag}</span>
          <button
            onClick={() => handleRemoveTag(tag)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ))}
      
      {isAdding ? (
        <div className="flex items-center gap-1">
          <Input
            ref={inputRef}
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="Новый тег"
            className="h-8 w-28 text-sm border-gray-200 focus:border-gray-300"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleAddTag();
              } else if (e.key === 'Escape') {
                setIsAdding(false);
                setNewTag('');
              }
            }}
          />
          <Button
            size="sm"
            variant="ghost"
            onClick={handleAddTag}
            disabled={!newTag.trim()}
            className="h-8 w-8 p-0 hover:bg-gray-100"
          >
            <Check size={16} />
          </Button>
        </div>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setIsAdding(true)}
          className="h-8 w-8 p-0 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <Plus size={16} />
        </Button>
      )}
    </div>
  );
}; 