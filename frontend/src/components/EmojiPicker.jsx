import React, { useState } from 'react';
import { cn } from '../lib/utils';

const QUICK_REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏'];

export const EmojiPicker = ({ onSelect, onClose, position = 'top' }) => {
    const ALL_EMOJIS = [
        '👍', '❤️', '😂', '😮', '😢', '🙏', '🔥', '👏',
        '🎉', '💯', '✅', '❌', '👀', '💪', '🤔', '😍'
    ];

    return (
        <div className={cn(
            'absolute right-0 z-[1000] pointer-events-auto touch-manipulation backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl p-2 max-w-[calc(100vw-1rem)]',
            position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'
        )}>
            <div className="grid grid-cols-6 sm:grid-cols-8 gap-1">
                {ALL_EMOJIS.map(emoji => (
                    <button
                        key={emoji}
                        onClick={() => { onSelect(emoji); onClose(); }}
                        className="p-2 hover:bg-white/10 rounded-lg text-xl transition-colors"
                    >
                        {emoji}
                    </button>
                ))}
            </div>
        </div>
    );
};

export const MessageReactions = ({ reactions = [], onAddReaction, messageId }) => {
    const [showPicker, setShowPicker] = useState(false);

    if (!reactions || reactions.length === 0) {
        return (
            <div className="relative inline-block">
                <button
                    onClick={() => setShowPicker(!showPicker)}
                    className="opacity-0 group-hover:opacity-100 text-xs text-white/40 hover:text-white px-1.5 py-0.5 rounded hover:bg-white/10 transition-all"
                >
                    +
                </button>
                {showPicker && (
                    <EmojiPicker
                        onSelect={(emoji) => onAddReaction(messageId, emoji)}
                        onClose={() => setShowPicker(false)}
                        position="top"
                    />
                )}
            </div>
        );
    }

    // Group reactions by emoji
    const grouped = reactions.reduce((acc, r) => {
        acc[r.emoji] = (acc[r.emoji] || 0) + 1;
        return acc;
    }, {});

    return (
        <div className="flex items-center gap-1 mt-1 flex-wrap relative">
            {Object.entries(grouped).map(([emoji, count]) => (
                <button
                    key={emoji}
                    onClick={() => onAddReaction(messageId, emoji)}
                    className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-white/10 hover:bg-white/20 text-xs transition-colors"
                >
                    <span>{emoji}</span>
                    {count > 1 && <span className="text-white/60">{count}</span>}
                </button>
            ))}
            <div className="relative">
                <button
                    onClick={() => setShowPicker(!showPicker)}
                    className="opacity-0 group-hover:opacity-100 text-xs text-white/40 hover:text-white px-1.5 py-0.5 rounded-full hover:bg-white/10 transition-all"
                >
                    +
                </button>
                {showPicker && (
                    <EmojiPicker
                        onSelect={(emoji) => onAddReaction(messageId, emoji)}
                        onClose={() => setShowPicker(false)}
                        position="top"
                    />
                )}
            </div>
        </div>
    );
};

// Quick reaction bar that appears on hover
export const QuickReactionBar = ({ onReact, messageId }) => {
    return (
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex items-center gap-0.5 p-1 rounded-full backdrop-blur-xl bg-emerald-800/90 border border-white/20 shadow-lg opacity-0 group-hover:opacity-100 transition-all">
            {QUICK_REACTIONS.map(emoji => (
                <button
                    key={emoji}
                    onClick={() => onReact(messageId, emoji)}
                    className="p-1.5 hover:bg-white/20 rounded-full text-sm transition-colors"
                    title={emoji}
                >
                    {emoji}
                </button>
            ))}
        </div>
    );
};

export default EmojiPicker;
