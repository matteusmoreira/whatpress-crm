import React from 'react';
import { cn } from '../lib/utils';

/**
 * TypingIndicator - Shows animated dots when contact is typing
 */
const TypingIndicator = ({ contactName, className }) => {
    return (
        <div className={cn(
            'flex items-center gap-2 px-4 py-2 bg-white/5 backdrop-blur-sm rounded-xl',
            className
        )}>
            <div className="flex items-center gap-1">
                {/* Animated dots */}
                <span
                    className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                />
                <span
                    className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                />
                <span
                    className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                />
            </div>
            <span className="text-white/60 text-sm">
                {contactName ? `${contactName} está digitando...` : 'Digitando...'}
            </span>
        </div>
    );
};

/**
 * Hook to manage typing indicator state
 * Auto-hides after 5 seconds of inactivity
 */
export const useTypingIndicator = () => {
    const [typingUsers, setTypingUsers] = React.useState({});
    const timeoutsRef = React.useRef({});

    const setTyping = React.useCallback((conversationId, contactName, isTyping) => {
        // Clear existing timeout
        if (timeoutsRef.current[conversationId]) {
            clearTimeout(timeoutsRef.current[conversationId]);
        }

        if (isTyping) {
            // Set typing and auto-clear after 5 seconds
            setTypingUsers(prev => ({
                ...prev,
                [conversationId]: contactName
            }));

            timeoutsRef.current[conversationId] = setTimeout(() => {
                setTypingUsers(prev => {
                    const next = { ...prev };
                    delete next[conversationId];
                    return next;
                });
            }, 5000);
        } else {
            // Clear immediately
            setTypingUsers(prev => {
                const next = { ...prev };
                delete next[conversationId];
                return next;
            });
        }
    }, []);

    const getTypingContact = React.useCallback((conversationId) => {
        return typingUsers[conversationId] || null;
    }, [typingUsers]);

    // Cleanup on unmount
    React.useEffect(() => {
        return () => {
            Object.values(timeoutsRef.current).forEach(clearTimeout);
        };
    }, []);

    return { setTyping, getTypingContact, typingUsers };
};

export default TypingIndicator;
