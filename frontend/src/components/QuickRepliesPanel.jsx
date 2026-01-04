import React, { useState } from 'react';
import { MessageSquare, Zap, Clock, Tag, User } from 'lucide-react';
import { GlassButton } from './GlassCard';
import { cn } from '../lib/utils';

const DEFAULT_QUICK_REPLIES = [
  {
    id: 'greeting',
    title: 'Saudação',
    content: 'Olá! 👋 Seja bem-vindo(a)! Como posso ajudar você hoje?',
    category: 'greeting',
    icon: '👋'
  },
  {
    id: 'thanks',
    title: 'Agradecimento',
    content: 'Muito obrigado pelo contato! 😊 Estamos sempre à disposição.',
    category: 'closing',
    icon: '🙏'
  },
  {
    id: 'wait',
    title: 'Aguarde',
    content: 'Por favor, aguarde um momento enquanto verifico as informações. ⏳',
    category: 'support',
    icon: '⏳'
  },
  {
    id: 'hours',
    title: 'Horário',
    content: '🕐 Nosso horário de atendimento é de segunda a sexta, das 9h às 18h.',
    category: 'info',
    icon: '🕐'
  },
  {
    id: 'transfer',
    title: 'Transferir',
    content: 'Vou transferir seu atendimento para um especialista. Por favor, aguarde um momento.',
    category: 'support',
    icon: '🔄'
  },
  {
    id: 'resolved',
    title: 'Resolvido',
    content: '✅ Ótimo! Fico feliz em ter ajudado. Caso precise de mais alguma coisa, estou à disposição!',
    category: 'closing',
    icon: '✅'
  },
  {
    id: 'price',
    title: 'Preço',
    content: 'Vou verificar os preços e te passo em instantes! 💰',
    category: 'sales',
    icon: '💰'
  },
  {
    id: 'delivery',
    title: 'Entrega',
    content: '📦 O prazo de entrega é de 3 a 5 dias úteis para sua região.',
    category: 'info',
    icon: '📦'
  }
];

const QuickRepliesPanel = ({ onSelect, onClose }) => {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const categories = [
    { id: 'all', label: 'Todas', icon: <MessageSquare className="w-4 h-4" /> },
    { id: 'greeting', label: 'Saudações', icon: <User className="w-4 h-4" /> },
    { id: 'support', label: 'Suporte', icon: <Zap className="w-4 h-4" /> },
    { id: 'info', label: 'Info', icon: <Clock className="w-4 h-4" /> },
    { id: 'closing', label: 'Fechamento', icon: <Tag className="w-4 h-4" /> }
  ];

  const filteredReplies = DEFAULT_QUICK_REPLIES.filter(reply => {
    const matchesCategory = selectedCategory === 'all' || reply.category === selectedCategory;
    const matchesSearch = reply.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         reply.content.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 backdrop-blur-xl bg-gradient-to-br from-emerald-900/95 to-emerald-950/98 border border-white/20 rounded-2xl shadow-2xl shadow-emerald-500/20 overflow-hidden z-50">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Zap className="w-5 h-5 text-emerald-400" />
            Respostas Rápidas
          </h3>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white transition-colors text-sm"
          >
            ESC para fechar
          </button>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Buscar resposta..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder:text-white/40 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          autoFocus
        />

        {/* Categories */}
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all',
                selectedCategory === cat.id
                  ? 'bg-emerald-500 text-white'
                  : 'bg-white/10 text-white/70 hover:bg-white/20'
              )}
            >
              {cat.icon}
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Replies List */}
      <div className="max-h-64 overflow-y-auto p-2">
        {filteredReplies.length === 0 ? (
          <p className="text-white/50 text-center py-4">Nenhuma resposta encontrada</p>
        ) : (
          <div className="grid grid-cols-1 gap-2">
            {filteredReplies.map(reply => (
              <button
                key={reply.id}
                onClick={() => {
                  onSelect(reply.content);
                  onClose();
                }}
                className="p-3 rounded-xl bg-white/5 hover:bg-white/10 text-left transition-all group"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{reply.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-sm">{reply.title}</p>
                    <p className="text-white/60 text-sm truncate group-hover:text-white/80">
                      {reply.content}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default QuickRepliesPanel;
