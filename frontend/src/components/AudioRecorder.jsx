import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Play, Pause, Send, Trash2, X } from 'lucide-react';
import { cn } from '../lib/utils';

const AudioRecorder = ({ onSend, onCancel }) => {
    const [isRecording, setIsRecording] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [audioUrl, setAudioUrl] = useState(null);
    const [audioBlob, setAudioBlob] = useState(null);
    const [duration, setDuration] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);

    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const timerRef = useRef(null);
    const audioRef = useRef(null);

    useEffect(() => {
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
            if (audioUrl) URL.revokeObjectURL(audioUrl);
        };
    }, [audioUrl]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    audioChunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                const url = URL.createObjectURL(blob);
                setAudioBlob(blob);
                setAudioUrl(url);

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start(100); // Collect data every 100ms
            setIsRecording(true);
            setDuration(0);

            timerRef.current = setInterval(() => {
                setDuration(d => d + 1);
            }, 1000);

        } catch (error) {
            console.error('Error starting recording:', error);
            alert('Não foi possível acessar o microfone. Verifique as permissões.');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
        }
    };

    const handlePlayPause = () => {
        if (!audioRef.current) return;

        if (isPlaying) {
            audioRef.current.pause();
        } else {
            audioRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    const handleAudioEnded = () => {
        setIsPlaying(false);
    };

    const handleSend = async () => {
        if (audioBlob) {
            await onSend(audioBlob, duration);
        }
    };

    const handleDiscard = () => {
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
        setAudioBlob(null);
        setDuration(0);
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <div className="p-4 bg-emerald-900/90 backdrop-blur-xl border border-white/20 rounded-xl">
            {!audioUrl ? (
                // Recording Mode
                <div className="flex items-center gap-4">
                    <button
                        onClick={isRecording ? stopRecording : startRecording}
                        className={cn(
                            'p-4 rounded-full transition-colors',
                            isRecording
                                ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                                : 'bg-emerald-500 hover:bg-emerald-600'
                        )}
                    >
                        {isRecording ? (
                            <Square className="w-6 h-6 text-white" />
                        ) : (
                            <Mic className="w-6 h-6 text-white" />
                        )}
                    </button>

                    <div className="flex-1">
                        {isRecording ? (
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                                <span className="text-white font-mono">{formatTime(duration)}</span>
                                <span className="text-white/50 text-sm">Gravando...</span>
                            </div>
                        ) : (
                            <span className="text-white/50">Clique para gravar</span>
                        )}
                    </div>

                    <button
                        onClick={onCancel}
                        className="p-2 text-white/40 hover:text-white hover:bg-white/10 rounded-lg"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
            ) : (
                // Playback Mode
                <div className="flex items-center gap-4">
                    <button
                        onClick={handlePlayPause}
                        className="p-3 rounded-full bg-emerald-500 hover:bg-emerald-600 transition-colors"
                    >
                        {isPlaying ? (
                            <Pause className="w-5 h-5 text-white" />
                        ) : (
                            <Play className="w-5 h-5 text-white" />
                        )}
                    </button>

                    <div className="flex-1">
                        <div className="flex items-center gap-2">
                            <div className="flex-1 h-1 bg-white/20 rounded-full overflow-hidden">
                                <div className="h-full bg-emerald-500 rounded-full" style={{ width: '100%' }} />
                            </div>
                            <span className="text-white/60 text-sm font-mono">{formatTime(duration)}</span>
                        </div>
                    </div>

                    <audio
                        ref={audioRef}
                        src={audioUrl}
                        onEnded={handleAudioEnded}
                        className="hidden"
                    />

                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleDiscard}
                            className="p-2 text-white/40 hover:text-red-400 hover:bg-red-500/20 rounded-lg"
                            title="Descartar"
                        >
                            <Trash2 className="w-5 h-5" />
                        </button>
                        <button
                            onClick={handleSend}
                            className="p-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg"
                            title="Enviar"
                        >
                            <Send className="w-5 h-5 text-white" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

// Simple Audio Player for received messages
export const AudioPlayer = ({ src, duration }) => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [progress, setProgress] = useState(0);
    const audioRef = useRef(null);

    const handlePlayPause = () => {
        if (!audioRef.current) return;

        if (isPlaying) {
            audioRef.current.pause();
        } else {
            audioRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    const handleTimeUpdate = () => {
        if (audioRef.current) {
            const progress = (audioRef.current.currentTime / audioRef.current.duration) * 100;
            setProgress(progress);
        }
    };

    const handleEnded = () => {
        setIsPlaying(false);
        setProgress(0);
    };

    const formatTime = (seconds) => {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <div className="flex items-center gap-3 p-2 bg-black/20 rounded-lg min-w-[200px]">
            <button
                onClick={handlePlayPause}
                className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
            >
                {isPlaying ? (
                    <Pause className="w-4 h-4 text-white" />
                ) : (
                    <Play className="w-4 h-4 text-white" />
                )}
            </button>

            <div className="flex-1">
                <div className="h-1 bg-white/20 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-white/60 rounded-full transition-all"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            <span className="text-white/60 text-xs font-mono">
                {formatTime(duration)}
            </span>

            <audio
                ref={audioRef}
                src={src}
                onTimeUpdate={handleTimeUpdate}
                onEnded={handleEnded}
                className="hidden"
            />
        </div>
    );
};

export default AudioRecorder;
