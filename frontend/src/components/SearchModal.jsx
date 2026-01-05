import React, { useState, useEffect, useRef } from 'react';
import { Search, X, MessageSquare, User, Building2, Clock, ArrowRight } from 'lucide-react';
import { GlassInput } from './GlassCard';
import { cn } from '../lib/utils';

const getInitials = (name) => {
  const safe = (name || '').trim();
  if (!safe) return '?';
  const parts = safe.split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || '';
  const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || '';
  return (first + last).toUpperCase() || '?';
};

const ContactAvatar = ({ src, name, className }) => {
  const [failed, setFailed] = useState(false);
  const normalizedSrc = typeof src === 'string' && src.includes('api.dicebear.com') ? '' : (src || '');
  const showImage = Boolean(normalizedSrc) && !failed;

  return (
    <div
      className={cn(
        'w-12 h-12 rounded-full overflow-hidden flex items-center justify-center bg-white/10 text-white/80 font-semibold select-none',
        className
      )}
    >
      {showImage ? (
        <img
          src={normalizedSrc}
          alt={name || 'Contato'}
          className="w-full h-full object-cover"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="text-sm">{getInitials(name)}</span>
      )}
    </div>
  );
};

const SearchModal = ({ isOpen, onClose, conversations, onSelectConversation }) => {
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (!isOpen) return null;

  const filteredConversations = conversations.filter(conv => {
    const matchesQuery = 
      conv.contactName.toLowerCase().includes(query.toLowerCase()) ||
      conv.contactPhone.includes(query) ||
      conv.lastMessagePreview.toLowerCase().includes(query.toLowerCase());
    
    if (activeTab === 'all') return matchesQuery;
    return matchesQuery && conv.status === activeTab;
  });

  const tabs = [
    { id: 'all', label: 'Todas', count: conversations.length },
    { id: 'open', label: 'Abertas', count: conversations.filter(c => c.status === 'open').length },
    { id: 'pending', label: 'Pendentes', count: conversations.filter(c => c.status === 'pending').length },
    { id: 'resolved', label: 'Resolvidas', count: conversations.filter(c => c.status === 'resolved').length }
  ];

  const handleSelect = (conv) => {
    onSelectConversation(conv);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-4 animate-in fade-in slide-in-from-top-4 duration-200">
        <div className="backdrop-blur-xl bg-gradient-to-br from-emerald-900/90 to-emerald-950/95 border border-white/20 rounded-2xl shadow-2xl shadow-emerald-500/20 overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-white/10">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Buscar conversas, contatos, mensagens..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-12 pr-12 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
              <button
                onClick={onClose}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg hover:bg-white/10 text-white/40 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mt-4">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                    activeTab === tab.id
                      ? 'bg-emerald-500 text-white'
                      : 'bg-white/10 text-white/70 hover:bg-white/20'
                  )}
                >
                  {tab.label}
                  <span className="ml-1.5 text-xs opacity-70">({tab.count})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Results */}
          <div className="max-h-[400px] overflow-y-auto">
            {query && filteredConversations.length === 0 ? (
              <div className="p-8 text-center text-white/50">
                <Search className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Nenhum resultado encontrado para "{query}"</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {filteredConversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => handleSelect(conv)}
                    className="w-full p-4 flex items-center gap-4 hover:bg-white/5 transition-colors text-left group"
                  >
                    <ContactAvatar src={conv.contactAvatar} name={conv.contactName} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{conv.contactName}</span>
                        <span className={cn(
                          'px-2 py-0.5 rounded-full text-xs',
                          conv.status === 'open' ? 'bg-emerald-500/20 text-emerald-400' :
                          conv.status === 'pending' ? 'bg-amber-500/20 text-amber-400' :
                          'bg-gray-500/20 text-gray-400'
                        )}>
                          {conv.status === 'open' ? 'Aberta' : conv.status === 'pending' ? 'Pendente' : 'Resolvida'}
                        </span>
                      </div>
                      <p className="text-white/50 text-sm truncate">{conv.lastMessagePreview}</p>
                      <p className="text-white/30 text-xs mt-1">{conv.contactPhone}</p>
                    </div>
                    <ArrowRight className="w-5 h-5 text-white/30 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-white/10 bg-white/5">
            <div className="flex items-center justify-between text-xs text-white/40">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10">↑↓</kbd> navegar
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10">Enter</kbd> selecionar
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 rounded bg-white/10">Esc</kbd> fechar
                </span>
              </div>
              <span>{filteredConversations.length} resultados</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SearchModal;
