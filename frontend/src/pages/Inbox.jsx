import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  Send,
  Paperclip,
  Smile,
  MoreVertical,
  ChevronLeft,
  Check,
  CheckCheck,
  Clock,
  Circle,
  MessageSquare,
  Zap,
  Tag,
  User,
  Users,
  X,
  Link2,
  Image,
  FileText,
  Mic,
  Play,
  Pause,
  Video,
  Wifi,
  WifiOff,
  Reply,
  Trash2,
  Edit2,
  UserCircle,
  Phone,
  Mail,
  PenLine
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { useAuthStore } from '../store/authStore';
import { useRealtime } from '../context/RealtimeContext';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from '../components/ui/glass-toaster';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../components/ui/tooltip';
import FileUpload from '../components/FileUpload';
import QuickRepliesPanel from '../components/QuickRepliesPanel';
import LabelsManager from '../components/LabelsManager';
import TypingIndicator, { useTypingIndicator } from '../components/TypingIndicator';
import { EmojiPicker } from '../components/EmojiPicker';
import { AgentsAPI, LabelsAPI, ConversationsAPI, ContactsAPI, MediaAPI } from '../lib/api';

// Labels are now loaded from the database

const getInitials = (name) => {
  const safe = (name || '').trim();
  if (!safe) return '?';
  const parts = safe.split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || '';
  const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || '';
  return (first + last).toUpperCase() || '?';
};

const URL_REGEX = /https?:\/\/[^\s<>()]+/gi;

const extractUrls = (text) => {
  if (!text) return [];
  const found = text.match(URL_REGEX);
  return Array.isArray(found) ? found : [];
};

const isWhatsappMediaUrl = (url) => {
  try {
    const u = new URL(url);
    const host = u.host.toLowerCase();
    if (!host.includes('whatsapp.net')) return false;
    return true;
  } catch {
    return false;
  }
};

const isApiMediaProxyUrl = (url) => {
  const s = typeof url === 'string' ? url : '';
  if (!s) return false;
  if (s.startsWith('data:')) return false;
  return s.includes('/api/media/proxy') || s.includes('/media/proxy?');
};

const parseProxyParamsFromUrl = (url) => {
  try {
    const u = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    const messageId = u.searchParams.get('message_id') || '';
    const remoteJid = u.searchParams.get('remote_jid') || '';
    const instanceName = u.searchParams.get('instance_name') || '';
    const rawFromMe = u.searchParams.get('from_me');
    const fromMe = rawFromMe === 'true' || rawFromMe === '1';
    if (!messageId || !remoteJid || !instanceName) return null;
    return { messageId, remoteJid, instanceName, fromMe };
  } catch {
    return null;
  }
};

const inferWhatsappMediaKind = (url) => {
  try {
    const u = new URL(url);
    const path = (u.pathname || '').toLowerCase();
    const search = u.searchParams;
    const mime = (search.get('mimeType') || search.get('mime_type') || '').toLowerCase();
    const combined = path + ' ' + mime;
    if (combined.includes('sticker') || combined.includes('webp')) return 'sticker';
    if (
      combined.includes('audio') ||
      combined.includes('ptt') ||
      combined.includes('.ogg') ||
      combined.includes('opus')
    ) return 'audio';
    if (
      combined.includes('video') ||
      combined.includes('.mp4') ||
      combined.includes('.3gp')
    ) return 'video';
    if (
      combined.includes('image') ||
      combined.includes('.jpg') ||
      combined.includes('.jpeg') ||
      combined.includes('.png') ||
      combined.includes('.gif')
    ) return 'image';
    return 'document';
  } catch {
    return 'unknown';
  }
};

const normalizeBareBase64 = (text) => {
  if (!text) return '';
  let s = String(text).trim();
  const commaIndex = s.indexOf(',');
  if (commaIndex >= 0 && s.slice(0, commaIndex).toLowerCase().includes('base64')) {
    s = s.slice(commaIndex + 1).trim();
  }
  s = s.replace(/\s+/g, '');
  if (s.includes('-') || s.includes('_')) {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
  }
  const mod = s.length % 4;
  if (mod === 2) s += '==';
  if (mod === 3) s += '=';
  return s;
};

const isLikelyBareBase64 = (text) => {
  const s = typeof text === 'string' ? text.trim() : '';
  if (!s) return false;
  if (s.startsWith('data:')) return false;
  if (s.includes('http://') || s.includes('https://')) return false;
  if (s.length < 200) return false;
  const compact = s.replace(/\s+/g, '');
  if (!/^[A-Za-z0-9+/_-]+={0,2}$/.test(compact)) return false;
  return true;
};

const resolveMediaMimeType = (renderType, metaMime) => {
  const m = String(metaMime || '').trim().toLowerCase();
  if (m) return m;
  if (renderType === 'sticker') return 'image/webp';
  if (renderType === 'image') return 'image/jpeg';
  if (renderType === 'audio') return 'audio/ogg';
  if (renderType === 'video') return 'video/mp4';
  if (renderType === 'document') return 'application/octet-stream';
  return 'application/octet-stream';
};

const toDataUrlFromBareBase64 = (base64Text, mimeType) => {
  const normalized = normalizeBareBase64(base64Text);
  if (!normalized) return '';
  const mime = String(mimeType || '').trim() || 'application/octet-stream';
  return `data:${mime};base64,${normalized}`;
};

const getWhatsappMediaMeta = (kind) => {
  switch (kind) {
    case 'sticker':
      return { label: '[Figurinha]', Icon: Image };
    case 'audio':
      return { label: '[Áudio]', Icon: Mic };
    case 'video':
      return { label: '[Vídeo]', Icon: Video };
    case 'image':
      return { label: '[Imagem]', Icon: Image };
    default:
      return { label: 'Mídia do WhatsApp', Icon: Image };
  }
};

const shortenUrl = (url) => {
  try {
    const u = new URL(url);
    const host = u.host.replace(/^www\./, '');
    const path = u.pathname.length > 20 ? u.pathname.slice(0, 20) + '…' : u.pathname;
    return host + (path && path !== '/' ? path : '');
  } catch {
    return url.length > 34 ? url.slice(0, 34) + '…' : url;
  }
};

const renderTextWithLinks = (text) => {
  if (!text) return null;
  const parts = text.split(URL_REGEX);
  const urls = extractUrls(text);
  if (urls.length === 0) return text;
  const nodes = [];
  for (let i = 0; i < parts.length; i++) {
    if (parts[i]) nodes.push(<React.Fragment key={`t-${i}`}>{parts[i]}</React.Fragment>);
    const url = urls[i];
    if (url) {
      nodes.push(
        <a
          key={`u-${i}`}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 break-all"
        >
          {shortenUrl(url)}
        </a>
      );
    }
  }
  return nodes;
};

const ContactAvatar = ({ src, name, sizeClassName, className }) => {
  const [failed, setFailed] = useState(false);
  const normalizedSrc = typeof src === 'string' && src.includes('api.dicebear.com') ? '' : (src || '');
  const showImage = Boolean(normalizedSrc) && !failed;

  return (
    <div
      className={cn(
        sizeClassName,
        'rounded-full overflow-hidden flex items-center justify-center bg-white/10 text-white/80 font-semibold select-none',
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

const formatMediaTime = (seconds) => {
  const s = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const mins = Math.floor(s / 60);
  const secs = Math.floor(s % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
};

const INLINE_WAVEFORM_BARS = Array.from({ length: 32 }, (_, i) => {
  const base = 0.3 + 0.7 * Math.abs(Math.sin(i * 0.45));
  return Math.min(1, Math.max(0.25, base));
});

const extractQualityVariants = (meta, fallbackUrl) => {
  if (!meta || typeof meta !== 'object') return [];
  const baseArrays = [];
  if (Array.isArray(meta.qualities)) baseArrays.push(meta.qualities);
  if (Array.isArray(meta.variants)) baseArrays.push(meta.variants);
  if (Array.isArray(meta.qualityVariants)) baseArrays.push(meta.qualityVariants);
  const flat = baseArrays.flat();
  const variants = flat
    .map((v, index) => {
      if (!v || typeof v !== 'object') return null;
      const url = v.url ?? v.mediaUrl ?? v.src ?? v.href ?? null;
      if (!url || typeof url !== 'string') return null;
      const rawLabel = v.label ?? v.quality ?? v.resolution ?? v.name ?? null;
      const label = rawLabel ? String(rawLabel) : `Opção ${index + 1}`;
      return { url, label };
    })
    .filter(Boolean);
  if (fallbackUrl && typeof fallbackUrl === 'string') {
    const hasFallback = variants.some(v => v.url === fallbackUrl);
    if (!hasFallback) variants.unshift({ url: fallbackUrl, label: 'Padrão' });
  }
  const seen = new Set();
  const unique = [];
  for (const v of variants) {
    if (seen.has(v.url)) continue;
    seen.add(v.url);
    unique.push(v);
  }
  return unique;
};

const InlineAudioPlayer = ({ src, title, meta }) => {
  const audioRef = useRef(null);
  const [readySrc, setReadySrc] = useState('');
  const [pendingPlay, setPendingPlay] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(1);
  const [loadError, setLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setReadySrc('');
    setPendingPlay(false);
    setIsPlaying(false);
    setDuration(0);
    setCurrentTime(0);
    setLoadError(false);
    setIsLoading(false);
  }, [src]);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;

    const handleLoadedMetadata = () => {
      setDuration(Number.isFinite(a.duration) ? a.duration : 0);
      setIsLoading(false);
    };
    const handleTimeUpdate = () => setCurrentTime(a.currentTime || 0);
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    const handleError = () => {
      setIsLoading(false);
      setLoadError(true);
      setIsPlaying(false);
    };
    const handleWaiting = () => setIsLoading(true);
    const handleCanPlay = () => setIsLoading(false);

    a.addEventListener('loadedmetadata', handleLoadedMetadata);
    a.addEventListener('timeupdate', handleTimeUpdate);
    a.addEventListener('play', handlePlay);
    a.addEventListener('pause', handlePause);
    a.addEventListener('ended', handleEnded);
    a.addEventListener('error', handleError);
    a.addEventListener('waiting', handleWaiting);
    a.addEventListener('canplay', handleCanPlay);

    a.volume = volume;

    return () => {
      a.removeEventListener('loadedmetadata', handleLoadedMetadata);
      a.removeEventListener('timeupdate', handleTimeUpdate);
      a.removeEventListener('play', handlePlay);
      a.removeEventListener('pause', handlePause);
      a.removeEventListener('ended', handleEnded);
      a.removeEventListener('error', handleError);
      a.removeEventListener('waiting', handleWaiting);
      a.removeEventListener('canplay', handleCanPlay);
    };
  }, [volume]);

  useEffect(() => {
    if (!pendingPlay) return;
    if (!readySrc) return;
    const a = audioRef.current;
    if (!a) return;
    setPendingPlay(false);
    Promise.resolve(a.play()).catch(() => {
      setLoadError(true);
      setIsPlaying(false);
      setIsLoading(false);
    });
  }, [pendingPlay, readySrc]);

  const ensureSrc = () => {
    if (!readySrc) {
      setReadySrc(src);
      setIsLoading(true);
      return false;
    }
    return true;
  };

  const togglePlay = () => {
    if (!src) return;
    const a = audioRef.current;
    if (!a) return;
    if (loadError) return;

    if (!ensureSrc()) {
      setPendingPlay(true);
      return;
    }

    if (a.paused) {
      setIsLoading(true);
      Promise.resolve(a.play()).catch(() => {
        setLoadError(true);
        setIsPlaying(false);
        setIsLoading(false);
      });
    } else {
      a.pause();
    }
  };

  const seekTo = (nextTime) => {
    const a = audioRef.current;
    if (!a) return;
    if (!ensureSrc()) return;
    const t = Math.max(0, Math.min(Number(nextTime) || 0, duration || 0));
    a.currentTime = t;
    setCurrentTime(t);
  };

  const setPlayerVolume = (nextVolume) => {
    const a = audioRef.current;
    const v = Math.max(0, Math.min(Number(nextVolume) || 0, 1));
    setVolume(v);
    if (a) a.volume = v;
  };

  const progressMax = Number.isFinite(duration) && duration > 0 ? duration : 0;
  const progressNow = Number.isFinite(currentTime) && currentTime > 0 ? Math.min(currentTime, progressMax) : 0;
  const progressRatio = progressMax > 0 ? progressNow / progressMax : 0;

  const rawSize = meta ? (meta.file_size ?? meta.fileSize ?? meta.size ?? meta.bytes ?? null) : null;
  const sizeNumber = typeof rawSize === 'number' ? rawSize : rawSize ? Number(rawSize) : 0;
  const sizeDisplay = (() => {
    if (!sizeNumber || Number.isNaN(sizeNumber)) return '';
    const kb = sizeNumber / 1024;
    const mb = kb / 1024;
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${kb.toFixed(1)} KB`;
  })();

  const mimeDisplay = meta ? (meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime ?? '') : '';

  return (
    <div className="w-full min-w-[260px] rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={togglePlay}
          disabled={!src || loadError}
          className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 border',
            loadError ? 'bg-red-500/10 border-red-400/30 text-red-200' : 'bg-emerald-500/15 border-emerald-400/30 text-emerald-200 hover:bg-emerald-500/25'
          )}
          aria-label={isPlaying ? 'Pausar áudio' : 'Reproduzir áudio'}
        >
          {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium truncate">{title || 'Áudio'}</p>
            <p className="text-xs text-white/60 tabular-nums">
              {formatMediaTime(progressNow)} / {formatMediaTime(progressMax)}
            </p>
          </div>

          <div className="mt-2 flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={progressMax || 0}
              step={0.1}
              value={progressNow}
              onChange={(e) => seekTo(e.target.value)}
              disabled={!readySrc || loadError || !progressMax}
              className="flex-1"
              aria-label="Progresso do áudio"
            />
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={volume}
              onChange={(e) => setPlayerVolume(e.target.value)}
              disabled={loadError}
              className="w-24"
              aria-label="Volume do áudio"
            />
          </div>
        </div>
      </div>

      <div className="mt-3 relative h-10 rounded-lg bg-black/40 overflow-hidden">
        <div className="absolute inset-0 flex items-end gap-[2px] px-2">
          {INLINE_WAVEFORM_BARS.map((h, index) => (
            <div
              key={index}
              className="flex-1 bg-white/20 rounded-full"
              style={{ height: `${h * 100}%` }}
            />
          ))}
        </div>
        <div
          className="absolute inset-0 overflow-hidden"
          style={{ width: `${Math.max(0, Math.min(1, progressRatio)) * 100}%` }}
        >
          <div className="absolute inset-0 flex items-end gap-[2px] px-2">
            {INLINE_WAVEFORM_BARS.map((h, index) => (
              <div
                key={index}
                className={cn(
                  'flex-1 rounded-full',
                  loadError ? 'bg-red-400/70' : 'bg-emerald-400/80'
                )}
                style={{ height: `${h * 100}%` }}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between gap-3 text-[11px] text-white/60">
        <span className="truncate">
          {progressMax ? `Duração: ${formatMediaTime(progressMax)}` : 'Duração desconhecida'}
        </span>
        {mimeDisplay && (
          <span className="truncate hidden sm:inline">
            Formato: {String(mimeDisplay)}
          </span>
        )}
        {sizeDisplay && (
          <span className="truncate hidden sm:inline">
            Tamanho: {sizeDisplay}
          </span>
        )}
        {src && (
          <a
            href={readySrc || src}
            download
            target="_blank"
            rel="noreferrer"
            className="text-emerald-200 hover:text-emerald-100 underline-offset-2 hover:underline"
          >
            Baixar áudio
          </a>
        )}
      </div>

      {isLoading && !loadError && (
        <div className="mt-2 flex items-center gap-2 text-xs text-white/60">
          <div className="w-4 h-4 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
          Carregando…
        </div>
      )}

      {loadError && (
        <div className="mt-2 flex items-center justify-between gap-3 text-xs text-red-200">
          <span className="truncate">Não foi possível reproduzir este áudio.</span>
          {src && (
            <a href={src} target="_blank" rel="noreferrer" className="text-white/80 hover:text-white underline">
              Abrir
            </a>
          )}
        </div>
      )}

      <audio ref={audioRef} src={readySrc || undefined} preload="none" />
    </div>
  );
};

// Component to display WhatsApp media (images/videos) inline
const WhatsAppMediaDisplay = ({
  type,
  mediaUrl,
  content,
  direction,
  onImageClick,
  messageId,
  proxyInfo,
  meta
}) => {
  const [loadError, setLoadError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [proxyTried, setProxyTried] = useState(false);
  const [proxiedUrl, setProxiedUrl] = useState('');
  const [videoDuration, setVideoDuration] = useState(0);
  const [qualityUrl, setQualityUrl] = useState('');

  // Check if it's a WhatsApp CDN URL that might be expired
  const isWhatsAppUrl = mediaUrl && (
    mediaUrl.includes('mmg.whatsapp.net') ||
    mediaUrl.includes('whatsapp.net')
  );

  const effectiveUrl = proxiedUrl || mediaUrl;
  const qualityVariants = useMemo(
    () => extractQualityVariants(meta, mediaUrl),
    [meta, mediaUrl]
  );

  const canProxy = Boolean(
    proxyInfo &&
    typeof proxyInfo === 'object' &&
    proxyInfo.messageId &&
    proxyInfo.remoteJid &&
    proxyInfo.instanceName
  );

  const fetchProxy = useCallback(async () => {
    if (proxyTried) return;
    setProxyTried(true);
    if (!canProxy) return;
    try {
      const result = await MediaAPI.proxy({
        messageId: proxyInfo.messageId,
        remoteJid: proxyInfo.remoteJid,
        instanceName: proxyInfo.instanceName,
        fromMe: Boolean(proxyInfo.fromMe)
      });
      const dataUrl = result?.dataUrl;
      if (typeof dataUrl === 'string' && dataUrl.startsWith('data:')) {
        setProxiedUrl(dataUrl);
        setLoadError(false);
        setLoading(false);
      }
    } catch {
      setLoading(false);
      setLoadError(true);
    }
  }, [proxyInfo, canProxy, proxyTried]);

  useEffect(() => {
    setProxyTried(false);
    setProxiedUrl('');
    setLoadError(false);
    setLoading(true);
  }, [mediaUrl, type]);

  useEffect(() => {
    if (!qualityVariants.length) {
      setQualityUrl('');
      return;
    }
    const preferred = qualityVariants.find(v => v.url === mediaUrl) || qualityVariants[0];
    setQualityUrl(preferred.url);
  }, [mediaUrl, qualityVariants]);

  useEffect(() => {
    if (!isWhatsAppUrl) return;
    if (!canProxy) return;
    if (type !== 'audio' && type !== 'video' && type !== 'image' && type !== 'sticker' && type !== 'document') return;
    fetchProxy();
  }, [isWhatsAppUrl, canProxy, type, fetchProxy]);

  useEffect(() => {
    if (isWhatsAppUrl) return;
    if (!canProxy) return;
    if (mediaUrl) return;
    if (type !== 'audio' && type !== 'video' && type !== 'image' && type !== 'sticker' && type !== 'document') return;
    fetchProxy();
  }, [isWhatsAppUrl, canProxy, mediaUrl, type, fetchProxy]);

  if (type === 'document' && (mediaUrl || canProxy)) {
    const title = (content || '').trim() || (meta?.file_name ?? meta?.fileName ?? meta?.name ?? '').trim() || 'Documento';
    const canOpen = Boolean(effectiveUrl);
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => {
            if (!canOpen && canProxy && !proxyTried) {
              fetchProxy();
              return;
            }
            if (!effectiveUrl) return;
            onImageClick?.({ open: true, url: effectiveUrl, title, messageId, kind: 'document', proxyInfo });
          }}
          className={cn(
            'flex items-center gap-3 p-3 rounded-xl border w-full text-left focus:outline-none focus:ring-2 focus:ring-white/30',
            direction === 'outbound'
              ? 'bg-white/10 border-white/20 hover:bg-white/15'
              : 'bg-black/20 border-white/10 hover:bg-black/30'
          )}
          aria-label="Visualizar documento"
        >
          <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
            <FileText className="w-5 h-5 opacity-80" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{title}</p>
            <p className="text-xs opacity-70 truncate">
              {effectiveUrl ? 'Clique para abrir' : loadError ? 'Falha ao carregar' : loading ? 'Carregando…' : 'Clique para carregar'}
            </p>
          </div>
          {effectiveUrl && !isApiMediaProxyUrl(effectiveUrl) && (
            <a
              href={effectiveUrl}
              download
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-emerald-200 hover:text-emerald-100 underline-offset-2 hover:underline text-xs"
            >
              Baixar
            </a>
          )}
        </button>
      </div>
    );
  }

  if ((type === 'image' || type === 'sticker') && (mediaUrl || canProxy)) {
    const label = type === 'sticker' ? 'Figurinha' : 'Imagem';
    const title = type === 'sticker' ? (content || 'Figurinha') : (content || 'Imagem');
    const canOpen = Boolean(effectiveUrl);
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => {
            if (!canOpen && canProxy && !proxyTried) {
              fetchProxy();
              return;
            }
            if (!effectiveUrl) return;
            onImageClick?.({ open: true, url: effectiveUrl, title, messageId, kind: type, proxyInfo });
          }}
          className={cn(
            'flex items-center gap-3 p-3 rounded-xl border w-full text-left focus:outline-none focus:ring-2 focus:ring-white/30',
            direction === 'outbound'
              ? 'bg-white/10 border-white/20 hover:bg-white/15'
              : 'bg-black/20 border-white/10 hover:bg-black/30'
          )}
          aria-label={`Visualizar ${label.toLowerCase()}`}
        >
          <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
            <Image className="w-5 h-5 opacity-80" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{label}</p>
            <p className="text-xs opacity-70 truncate">
              {effectiveUrl ? 'Clique para visualizar' : loadError ? 'Falha ao carregar' : loading ? 'Carregando…' : 'Clique para carregar'}
            </p>
          </div>
        </button>
      </div>
    );
  }

  const videoUrl = qualityUrl || effectiveUrl;

  if (type === 'video' && videoUrl && !loadError) {
    return (
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-xl">
            <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          </div>
        )}
        <video
          key={videoUrl}
          className="w-full max-h-80 rounded-xl bg-black/20"
          controls
          preload="metadata"
          playsInline
          src={videoUrl}
          aria-label="Reprodutor de vídeo"
          onLoadedMetadata={(e) => {
            setLoading(false);
            const el = e.currentTarget;
            const dur = Number.isFinite(el.duration) ? el.duration : 0;
            if (dur > 0) setVideoDuration(dur);
          }}
          onError={() => {
            if (isWhatsAppUrl && canProxy && !proxyTried) {
              fetchProxy();
              return;
            }
            setLoading(false);
            setLoadError(true);
          }}
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-white/70">
          <span className="truncate">
            {videoDuration ? `Duração: ${formatMediaTime(videoDuration)}` : 'Duração desconhecida'}
          </span>
          {(() => {
            const mime =
              meta && (meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime) ?
                (meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime) :
                '';
            if (!mime) return null;
            return (
              <span className="truncate hidden sm:inline">
                Formato: {String(mime)}
              </span>
            );
          })()}
          {(() => {
            const rawSize = meta ? (meta.file_size ?? meta.fileSize ?? meta.size ?? meta.bytes ?? null) : null;
            const sizeNumber = typeof rawSize === 'number' ? rawSize : rawSize ? Number(rawSize) : 0;
            if (!sizeNumber || Number.isNaN(sizeNumber)) return null;
            const kb = sizeNumber / 1024;
            const mb = kb / 1024;
            const formatted = mb >= 1 ? `${mb.toFixed(2)} MB` : `${kb.toFixed(1)} KB`;
            return (
              <span className="truncate hidden sm:inline">
                Tamanho: {formatted}
              </span>
            );
          })()}
          {qualityVariants.length > 1 && (
            <select
              value={qualityUrl || ''}
              onChange={(e) => {
                const next = e.target.value || '';
                setQualityUrl(next);
                setVideoDuration(0);
                setLoading(true);
              }}
              className="h-7 rounded-md bg-black/40 border border-white/15 text-xs px-2 text-white"
            >
              {qualityVariants.map(v => (
                <option key={v.url} value={v.url}>
                  {v.label}
                </option>
              ))}
            </select>
          )}
          <a
            href={videoUrl}
            download
            target="_blank"
            rel="noreferrer"
            className="text-emerald-200 hover:text-emerald-100 underline-offset-2 hover:underline"
          >
            Baixar vídeo
          </a>
        </div>
      </div>
    );
  }

  if (type === 'audio' && effectiveUrl && !loadError) {
    return (
      <InlineAudioPlayer src={effectiveUrl} title={content || 'Áudio'} meta={meta} />
    );
  }

  // Fallback for failed loads or WhatsApp URLs that expired - show clickable placeholder
  if (loadError || (isWhatsAppUrl && !mediaUrl)) {
    const mediaKind =
      type === 'video' ? 'video' :
        type === 'audio' ? 'audio' :
          type === 'sticker' ? 'sticker' :
            'image';
    const IconComponent = mediaKind === 'video' ? Video : mediaKind === 'audio' ? Mic : Image;
    const label = mediaKind === 'video' ? 'Vídeo' : mediaKind === 'audio' ? 'Áudio' : mediaKind === 'sticker' ? 'Figurinha' : 'Imagem';

    return (
      <a
        href={effectiveUrl}
        target="_blank"
        rel="noreferrer"
        className={cn(
          'flex items-center gap-3 p-3 rounded-xl border w-full',
          direction === 'outbound'
            ? 'bg-white/10 border-white/20 hover:bg-white/15'
            : 'bg-black/20 border-white/10 hover:bg-black/30'
        )}
      >
        <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
          <IconComponent className="w-5 h-5 opacity-80" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{label}</p>
          <p className="text-xs opacity-70 truncate">Clique para abrir</p>
        </div>
      </a>
    );
  }

  return null;
};

const Inbox = () => {
  const { user } = useAuthStore();
  const { isConnected: realtimeConnected } = useRealtime();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const {
    conversations,
    selectedConversation,
    messages,
    connections,
    conversationsLoading,
    messagesLoading,
    conversationFilter,
    fetchConversations,
    fetchConnections,
    setSelectedConversation,
    setConversationFilter,
    sendMessage,
    updateConversationStatus,
    deleteConversation,
    purgeAllConversations,
    clearConversationMessages,
    deleteMessage
  } = useAppStore();

  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [newMessage, setNewMessage] = useState('');
  const [selectedConnectionFilter, setSelectedConnectionFilter] = useState('all');
  const [selectedAgentFilter, setSelectedAgentFilter] = useState('all');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(false);
  const [showLabelsMenu, setShowLabelsMenu] = useState(false);
  const [showAssignMenu, setShowAssignMenu] = useState(false);

  const normalizeHexColor = (value) => {
    if (typeof value !== 'string') return null;
    const v = value.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(v)) return v;
    if (/^[0-9a-fA-F]{6}$/.test(v)) return `#${v}`;
    return null;
  };
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showLabelsManager, setShowLabelsManager] = useState(false);
  const [agents, setAgents] = useState([]);
  const [labels, setLabels] = useState([]);
  const [selectedLabelFilter, setSelectedLabelFilter] = useState('all');
  const [replyToMessage, setReplyToMessage] = useState(null);
  const [mediaViewer, setMediaViewer] = useState({ open: false, url: '', title: '', messageId: null, kind: null, proxyInfo: null });
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [editingContactName, setEditingContactName] = useState(false);
  const [contactNameValue, setContactNameValue] = useState('');
  const [contactData, setContactData] = useState(null);
  const [useSignature, setUseSignature] = useState(user?.signatureEnabled ?? true);
  const [showPurgeAllDialog, setShowPurgeAllDialog] = useState(false);
  const [purgingAll, setPurgingAll] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const urlSearchHandledRef = useRef(null);
  const urlSearchInFlightRef = useRef(false);

  const tenantId = user?.tenantId || 'tenant-1';

  // Typing indicator hook
  const { setTyping, getTypingContact } = useTypingIndicator();

  // Load agents for assignment
  const loadAgents = useCallback(async () => {
    try {
      const data = await AgentsAPI.list(tenantId);
      setAgents(data);
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  }, [tenantId]);

  // Load labels from database
  const loadLabels = useCallback(async () => {
    try {
      const data = await LabelsAPI.list(tenantId);
      setLabels(data);
    } catch (error) {
      console.error('Error loading labels:', error);
    }
  }, [tenantId]);

  // Fetch initial data
  useEffect(() => {
    fetchConversations(tenantId);
    fetchConnections(tenantId);
    loadAgents();
    loadLabels();
  }, [tenantId, fetchConversations, fetchConnections, loadAgents, loadLabels]);

  // Handle URL search parameter to initiate conversation
  useEffect(() => {
    const searchParam = searchParams.get('search');
    const contactIdParam = searchParams.get('contactId');
    if (!searchParam || conversationsLoading) return;
    const handledKey = `${searchParam}|${contactIdParam || ''}`;
    if (urlSearchHandledRef.current === handledKey || urlSearchInFlightRef.current) return;
    urlSearchHandledRef.current = handledKey;
    urlSearchInFlightRef.current = true;

    const phone = decodeURIComponent(searchParam).replace(/\D/g, ''); // Simple cleanup
    const newParams = new URLSearchParams(searchParams);
    newParams.delete('search');
    newParams.delete('contactId');
    setSearchParams(newParams);
    if (!phone) {
      urlSearchInFlightRef.current = false;
      return;
    }

    // Check if conversation already exists
    const matches = (conversations || []).filter(c => (String(c?.contactPhone || '')).replace(/\D/g, '') === phone);
    const existing = matches.reduce((best, cur) => {
      if (!best) return cur;
      const bestTs = Date.parse(best?.lastMessageAt || '') || 0;
      const curTs = Date.parse(cur?.lastMessageAt || '') || 0;
      return curTs > bestTs ? cur : best;
    }, null);

    if (existing) {
      setSelectedConversation(existing);
      setSearchQuery(phone);
      urlSearchInFlightRef.current = false;
    } else {
      (async () => {
        try {
          const newConv = await ConversationsAPI.initiate(phone, contactIdParam || null);
          setSelectedConversation(newConv);
          setSearchQuery(phone);
          await fetchConversations(tenantId);
        } catch (error) {
          console.error("Error initiating conversation:", error);
          toast.error("Erro ao iniciar conversa");
        } finally {
          urlSearchInFlightRef.current = false;
        }
      })();
    }
  }, [searchParams, conversations, conversationsLoading, tenantId, fetchConversations, setSelectedConversation, setSearchParams]);

  // Fallback: polling para atualizar conversas/mensagens quando realtime falhar
  useEffect(() => {
    if (!tenantId) return;

    const pollConversations = () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      fetchConversations(tenantId, {}, { silent: true });
    };

    const pollMessages = () => {
      if (!selectedConversation?.id) return;
      if (typeof document !== 'undefined' && document.hidden) return;
      const state = useAppStore.getState();
      const currentMessages = state.messages || [];
      const last = currentMessages[currentMessages.length - 1];
      const lastTs = last?.timestamp;
      if (!lastTs) {
        state.fetchMessages(selectedConversation.id, { silent: true, tail: true, limit: 50 });
        return;
      }
      state.fetchMessages(selectedConversation.id, { silent: true, after: lastTs, append: true, limit: 50 });
    };

    pollConversations();
    pollMessages();

    const conversationsInterval = setInterval(pollConversations, realtimeConnected ? 15000 : 5000);
    const messagesInterval = setInterval(pollMessages, realtimeConnected ? 8000 : 3000);

    return () => {
      clearInterval(conversationsInterval);
      clearInterval(messagesInterval);
    };
  }, [tenantId, selectedConversation?.id, fetchConversations, realtimeConnected]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
    }
  }, [messages]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setShowQuickReplies(false);
        setShowFileUpload(false);
        setShowLabelsMenu(false);
        setShowAssignMenu(false);
        setShowMoreMenu(false);
      }
      if (e.key === '/' && e.ctrlKey) {
        e.preventDefault();
        setShowQuickReplies(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Agent heartbeat - keep online status
  useEffect(() => {
    const sendHeartbeat = async () => {
      try {
        await AgentsAPI.heartbeat();
      } catch (error) {
        console.error('Heartbeat error:', error);
      }
    };

    // Send heartbeat on mount and every 30 seconds
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 30000);

    // Set offline on unmount
    return () => {
      clearInterval(interval);
      AgentsAPI.setOffline().catch(() => { });
    };
  }, []);

  const filteredConversations = (() => {
    const byPhone = new Map();
    for (const conv of conversations || []) {
      const key = String(conv?.contactPhone || '').replace(/\D/g, '') || conv?.id;
      const existing = byPhone.get(key);
      if (!existing) {
        byPhone.set(key, conv);
        continue;
      }
      const existingTs = Date.parse(existing?.lastMessageAt || '') || 0;
      const nextTs = Date.parse(conv?.lastMessageAt || '') || 0;
      if (nextTs > existingTs) byPhone.set(key, conv);
    }

    const unique = Array.from(byPhone.values());
    const q = String(searchQuery || '').toLowerCase();

    return unique.filter(conv => {
      const contactName = String(conv?.contactName || '').toLowerCase();
      const contactPhone = String(conv?.contactPhone || '');
      const matchesSearch = contactName.includes(q) || contactPhone.includes(String(searchQuery || ''));
      const matchesStatus = conversationFilter === 'all' || conv.status === conversationFilter;
      const matchesConnection = selectedConnectionFilter === 'all' || conv.connectionId === selectedConnectionFilter;
      const matchesLabel = selectedLabelFilter === 'all' || (conv.labels || []).includes(selectedLabelFilter);
      const matchesAgent = selectedAgentFilter === 'all' ||
        (selectedAgentFilter === 'mine' && conv.assignedTo === user?.id) ||
        conv.assignedTo === selectedAgentFilter;
      return matchesSearch && matchesStatus && matchesConnection && matchesLabel && matchesAgent;
    });
  })();

  // Helper to get label info by ID
  const getLabelById = (labelId) => labels.find(l => l.id === labelId);

  // Helper to get agent status color
  const getAgentStatusColor = (status) => {
    switch (status) {
      case 'online': return 'bg-emerald-500';
      case 'busy': return 'bg-amber-500';
      default: return 'bg-gray-400';
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!newMessage.trim() || !selectedConversation) return;

    try {
      // Build message with signature if enabled
      let messageToSend = newMessage.trim();

      if (useSignature && user?.name) {
        // Build signature based on user settings
        const parts = [user.name];
        if (user.signatureIncludeTitle && user.jobTitle) {
          parts.push(user.jobTitle);
        }
        if (user.signatureIncludeDepartment && user.department) {
          parts.push(user.department);
        }

        // Format: *Name* (Title / Department)\nMessage
        const signatureLine = parts.length > 1
          ? `*${parts[0]}* (${parts.slice(1).join(' / ')})`
          : `*${parts[0]}*`;

        messageToSend = `${signatureLine}\n${newMessage.trim()}`;
      }

      // TODO: Include replyToMessage.id when sending to support quoted replies
      await sendMessage(selectedConversation.id, messageToSend);
      setNewMessage('');
      setReplyToMessage(null);
      inputRef.current?.focus();
    } catch (error) {
      toast.error('Erro ao enviar mensagem');
    }
  };

  const handleFileUpload = async (fileData) => {
    // FileUpload component now handles the upload via UploadAPI
    // Just close the panel and refresh messages
    setShowFileUpload(false);
    // Messages will be updated via realtime or we can fetch manually
    if (selectedConversation?.id) {
      useAppStore.getState().fetchMessages(selectedConversation.id, { tail: true, limit: 50 });
    }
  };

  const handleQuickReplySelect = (content) => {
    setNewMessage(content);
    inputRef.current?.focus();
  };

  const handleAssign = async (agentId) => {
    try {
      await ConversationsAPI.assign(selectedConversation.id, agentId);
      const agent = agents.find(a => a.id === agentId);
      toast.success('Conversa atribuída', { description: `Para ${agent?.name}` });
      setShowAssignMenu(false);
    } catch (error) {
      toast.error('Erro ao atribuir conversa');
    }
  };

  const handleAddLabel = async (labelId) => {
    try {
      // Check if label already exists on conversation
      const currentLabels = selectedConversation?.labels || [];
      if (currentLabels.includes(labelId)) {
        toast.info('Label já adicionada');
        setShowLabelsMenu(false);
        return;
      }

      await ConversationsAPI.addLabel(selectedConversation.id, labelId);

      // Update local state
      const updatedConv = {
        ...selectedConversation,
        labels: [...currentLabels, labelId]
      };
      setSelectedConversation(updatedConv);

      // Refresh conversations to get updated data
      fetchConversations(tenantId);

      toast.success('Label adicionada');
      setShowLabelsMenu(false);
    } catch (error) {
      toast.error('Erro ao adicionar label');
    }
  };

  // Handle contact editing
  const handleContactNameClick = () => {
    if (!selectedConversation) return;
    setContactNameValue(selectedConversation.contactName || '');
    setEditingContactName(true);
  };

  const handleContactNameSave = async () => {
    if (!selectedConversation || !contactNameValue.trim()) {
      toast.error('Digite um nome válido');
      return;
    }

    try {
      const nextName = contactNameValue.trim();

      await ContactsAPI.update(`conv-${selectedConversation.id}`, { full_name: nextName });

      try {
        const contact = await ContactsAPI.getByPhone(tenantId, selectedConversation.contactPhone);
        if (contact?.id && !String(contact.id).startsWith('conv-')) {
          await ContactsAPI.update(contact.id, { full_name: nextName });
        }
      } catch (e) {
      }

      // Update local state
      const updatedConv = { ...selectedConversation, contactName: nextName };
      setSelectedConversation(updatedConv);

      // Refresh conversations
      fetchConversations(tenantId);

      toast.success('Nome atualizado');
      setEditingContactName(false);
    } catch (error) {
      toast.error('Erro ao atualizar nome');
    }
  };

  const handleViewContact = async () => {
    if (!selectedConversation) return;

    try {
      const contact = await ContactsAPI.getByPhone(tenantId, selectedConversation.contactPhone);
      setContactData(contact);
      setShowContactModal(true);
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao carregar contato');
    }
  };

  const handleEmojiSelect = (emoji) => {
    setNewMessage(prev => prev + emoji);
    setShowEmojiPicker(false);
    inputRef.current?.focus();
  };

  const handlePurgeAllConversations = async () => {
    if (purgingAll) return;
    setPurgingAll(true);
    try {
      const result = await purgeAllConversations(tenantId);
      const deleted = result?.deletedConversations ?? 0;
      toast.success(deleted > 0 ? `Conversas excluídas: ${deleted}` : 'Nenhuma conversa para excluir');
      setShowPurgeAllDialog(false);
    } catch (error) {
      toast.error('Erro ao excluir todas as conversas');
    } finally {
      setPurgingAll(false);
    }
  };

  const handleDeleteConversation = async () => {
    if (!selectedConversation?.id) return;
    const ok = window.confirm('Deseja excluir esta conversa? Isso também remove as mensagens.');
    if (!ok) return;
    try {
      await deleteConversation(selectedConversation.id);
      toast.success('Conversa excluída');
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao excluir conversa');
    }
  };

  const handleClearMessages = async () => {
    if (!selectedConversation?.id) return;
    const ok = window.confirm('Deseja excluir todas as mensagens desta conversa?');
    if (!ok) return;
    try {
      await clearConversationMessages(selectedConversation.id);
      toast.success('Mensagens excluídas');
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao excluir mensagens');
    }
  };

  const handleDeleteMessage = async (messageId) => {
    if (!messageId) return;
    const ok = window.confirm('Deseja excluir esta mensagem?');
    if (!ok) return;
    try {
      await deleteMessage(messageId);
      toast.success('Mensagem excluída');
    } catch (error) {
      toast.error('Erro ao excluir mensagem');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'sent': return <Check className="w-4 h-4 text-white/50" />;
      case 'delivered': return <CheckCheck className="w-4 h-4 text-white/50" />;
      case 'read': return <CheckCheck className="w-4 h-4 text-emerald-400" />;
      case 'failed': return <Clock className="w-4 h-4 text-red-400" />;
      default: return null;
    }
  };

  const getConversationStatusColor = (status) => {
    switch (status) {
      case 'open': return 'bg-emerald-500';
      case 'pending': return 'bg-amber-500';
      case 'resolved': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getMessageTypeIcon = (type) => {
    switch (type) {
      case 'image': return <Image className="w-4 h-4" />;
      case 'video': return <Video className="w-4 h-4" />;
      case 'audio': return <Mic className="w-4 h-4" />;
      case 'document': return <FileText className="w-4 h-4" />;
      case 'sticker': return <Image className="w-4 h-4" />;
      default: return null;
    }
  };

  const normalizeMessageType = (type) => {
    const raw = String(type || '').trim();
    if (!raw) return 'text';

    let t = raw.toLowerCase();
    t = t.replace(/[_-]/g, '');
    if (t.endsWith('message')) t = t.slice(0, -7);

    if (t === 'text' || t === 'chat' || t === 'extendedtext') return 'text';
    if (t === 'image' || t === 'img' || t === 'photo' || t === 'picture' || t === 'imagem') return 'image';
    if (t === 'video' || t === 'gif') return 'video';
    if (t === 'audio' || t === 'ptt' || t === 'voice' || t === 'voicemessage') return 'audio';
    if (t === 'document' || t === 'file' || t === 'documento') return 'document';
    if (t === 'sticker' || t === 'figurinha') return 'sticker';

    return 'unknown';
  };

  const imageViewerItems = useMemo(() => {
    const items = [];
    const list = Array.isArray(messages) ? messages : [];
    for (const msg of list) {
      if (!msg || typeof msg !== 'object') continue;
      const rawContent = typeof msg.content === 'string'
        ? msg.content
        : msg.content == null
          ? ''
          : String(msg.content);
      const rawTrim = rawContent.trim();

      const mediaUrlRaw =
        typeof msg.mediaUrl === 'string' ? msg.mediaUrl :
          typeof msg.media_url === 'string' ? msg.media_url :
            typeof msg.url === 'string' ? msg.url :
              '';
      const mediaUrl = typeof mediaUrlRaw === 'string' && mediaUrlRaw.trim() ? mediaUrlRaw.trim() : '';

      const urls = extractUrls(rawContent);
      const urlFromContent = urls.length ? urls[0] : '';

      const normalizedType = normalizeMessageType(msg.type);

      const meta = (msg && typeof msg === 'object' && msg.metadata && typeof msg.metadata === 'object') ? msg.metadata : null;
      const metaMimeRaw = meta ? (meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime) : null;
      const metaMime = String(metaMimeRaw || '').toLowerCase();
      const kindFromMime = metaMime.includes('webp')
        ? 'sticker'
        : (metaMime.startsWith('image/'))
          ? 'image'
          : null;

      const base64Url = (() => {
        if (mediaUrl) return '';
        if (normalizedType !== 'image' && normalizedType !== 'sticker') return '';
        if (rawTrim.startsWith('data:')) return rawTrim;
        if (!isLikelyBareBase64(rawTrim)) return '';
        const mime = resolveMediaMimeType(normalizedType, metaMime);
        return toDataUrlFromBareBase64(rawTrim, mime);
      })();

      const effectiveUrl = mediaUrl || urlFromContent || base64Url;
      if (!effectiveUrl) continue;

      const kindFromUrl = effectiveUrl ? inferWhatsappMediaKind(effectiveUrl) : 'unknown';
      const kind = (normalizedType && normalizedType !== 'unknown' && normalizedType !== 'text')
        ? normalizedType
        : (kindFromMime || (kindFromUrl !== 'unknown' ? kindFromUrl : null));

      if (kind !== 'image' && kind !== 'sticker') continue;

      const title = kind === 'sticker' ? 'Figurinha' : 'Imagem';
      items.push({
        id: msg.id || null,
        url: effectiveUrl,
        title,
        kind,
        metadata: meta || null
      });
    }
    return items;
  }, [messages, normalizeMessageType]);

  const currentViewerIndex = useMemo(() => {
    if (!mediaViewer?.open) return -1;
    const id = mediaViewer?.messageId;
    const url = mediaViewer?.url;
    if (id) {
      const idx = imageViewerItems.findIndex(i => i.id && i.id === id);
      if (idx >= 0) return idx;
    }
    if (url) {
      const idx = imageViewerItems.findIndex(i => i.url === url);
      if (idx >= 0) return idx;
    }
    return -1;
  }, [mediaViewer, imageViewerItems]);

  const currentViewerItem = useMemo(() => {
    if (currentViewerIndex >= 0) return imageViewerItems[currentViewerIndex];
    if (mediaViewer?.url) {
      return {
        id: mediaViewer?.messageId || null,
        url: mediaViewer.url,
        title: mediaViewer.title || 'Imagem',
        kind: mediaViewer.kind || 'image'
      };
    }
    return null;
  }, [currentViewerIndex, imageViewerItems, mediaViewer]);

  const [viewerZoom, setViewerZoom] = useState(1);
  const [viewerRotation, setViewerRotation] = useState(0);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerLoadError, setViewerLoadError] = useState(false);
  const [viewerResolvedUrl, setViewerResolvedUrl] = useState('');
  const [viewerResolvedMimeType, setViewerResolvedMimeType] = useState('');

  useEffect(() => {
    if (!mediaViewer?.open) return;
    setViewerZoom(1);
    setViewerRotation(0);
  }, [mediaViewer?.open]);

  const currentViewerMessage = useMemo(() => {
    const list = Array.isArray(messages) ? messages : [];
    const id = currentViewerItem?.id || mediaViewer?.messageId;
    if (!id) return null;
    return list.find(m => m && typeof m === 'object' && m.id === id) || null;
  }, [messages, currentViewerItem, mediaViewer]);

  useEffect(() => {
    if (!mediaViewer?.open) return;
    setViewerLoading(true);
    setViewerLoadError(false);
    setViewerResolvedUrl(currentViewerItem?.url || '');
    setViewerResolvedMimeType('');
  }, [mediaViewer?.open, currentViewerItem?.url]);

  useEffect(() => {
    const run = async () => {
      if (!mediaViewer?.open) return;
      const url = currentViewerItem?.url || '';
      if (!url) return;
      if (typeof url !== 'string') return;
      if (url.startsWith('data:')) {
        setViewerResolvedUrl(url);
        setViewerLoading(false);
        return;
      }
      const shouldProxy = isWhatsappMediaUrl(url) || isApiMediaProxyUrl(url);
      if (!shouldProxy) {
        setViewerResolvedUrl(url);
        setViewerLoading(false);
        return;
      }
      const proxyInfo = (() => {
        const pi = mediaViewer?.proxyInfo;
        const canUse =
          pi &&
          typeof pi === 'object' &&
          pi.messageId &&
          pi.remoteJid &&
          pi.instanceName;
        if (canUse) {
          return {
            messageId: pi.messageId,
            remoteJid: pi.remoteJid,
            instanceName: pi.instanceName,
            fromMe: Boolean(pi.fromMe)
          };
        }
        return parseProxyParamsFromUrl(url);
      })();
      if (!proxyInfo) {
        setViewerResolvedUrl(url);
        setViewerLoading(false);
        return;
      }
      try {
        const result = await MediaAPI.proxy({
          messageId: proxyInfo.messageId,
          remoteJid: proxyInfo.remoteJid,
          instanceName: proxyInfo.instanceName,
          fromMe: Boolean(proxyInfo.fromMe)
        });
        const dataUrl = result?.dataUrl;
        const mimetype = result?.mimetype;
        if (typeof mimetype === 'string') setViewerResolvedMimeType(mimetype);
        if (typeof dataUrl === 'string' && dataUrl.startsWith('data:')) {
          setViewerResolvedUrl(dataUrl);
          setViewerLoading(false);
          return;
        }
        setViewerResolvedUrl(url);
        setViewerLoading(false);
      } catch {
        setViewerLoading(false);
        setViewerLoadError(true);
        toast.error('Não foi possível abrir esta mídia');
      }
    };
    run();
  }, [mediaViewer?.open, currentViewerItem?.url, mediaViewer?.proxyInfo]);

  const getMessageTypeBadgeInfo = (type) => {
    switch (type) {
      case 'image':
        return { label: 'Imagem', badgeClass: 'bg-sky-500/10 border-sky-400 text-sky-200', dotClass: 'bg-sky-400' };
      case 'video':
        return { label: 'Vídeo', badgeClass: 'bg-purple-500/10 border-purple-400 text-purple-200', dotClass: 'bg-purple-400' };
      case 'audio':
        return { label: 'Áudio', badgeClass: 'bg-amber-500/10 border-amber-400 text-amber-200', dotClass: 'bg-amber-400' };
      case 'document':
        return { label: 'Documento', badgeClass: 'bg-slate-500/10 border-slate-300 text-slate-200', dotClass: 'bg-slate-300' };
      case 'sticker':
        return { label: 'Figurinha', badgeClass: 'bg-pink-500/10 border-pink-400 text-pink-200', dotClass: 'bg-pink-400' };
      default:
        return null;
    }
  };

  const getMessageOriginInfo = (msg) => {
    const rawOrigin = msg.origin || (msg.direction === 'inbound' ? 'customer' : 'agent');
    const origin = String(rawOrigin || '').toLowerCase();
    if (origin === 'system') {
      return {
        label: 'Sistema',
        badgeClass: 'bg-purple-500/10 border-purple-400 text-purple-200',
        dotClass: 'bg-purple-400',
        tooltip: 'Mensagem automática enviada pelo sistema'
      };
    }
    if (origin === 'customer') {
      return {
        label: 'Cliente',
        badgeClass: 'bg-emerald-500/10 border-emerald-400 text-emerald-200',
        dotClass: 'bg-emerald-400',
        tooltip: 'Mensagem enviada pelo cliente'
      };
    }
    return {
      label: 'Agente',
      badgeClass: 'bg-sky-500/10 border-sky-400 text-sky-200',
      dotClass: 'bg-sky-400',
      tooltip: 'Mensagem enviada por um agente humano'
    };
  };

  const formatTime = (timestamp) => {
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ptBR });
    } catch {
      return '';
    }
  };

  return (
    <div className="h-full min-h-0 flex flex-col lg:flex-row">
      {/* Conversations List */}
      <div
        className={cn(
          'w-full lg:w-96 min-h-0 border-r border-white/10 bg-black/20 flex flex-col',
          selectedConversation ? 'hidden lg:flex' : 'flex'
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-white">Conversas</h1>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowPurgeAllDialog(true)}
                disabled={purgingAll || conversationsLoading || (conversations || []).length === 0}
                className={cn(
                  'p-2 rounded-lg transition-colors',
                  'hover:bg-red-500/20 text-white/60 hover:text-red-200',
                  (purgingAll || conversationsLoading || (conversations || []).length === 0) && 'opacity-40 cursor-not-allowed hover:bg-transparent'
                )}
                title="Excluir todas as conversas"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <GlassBadge
                variant={realtimeConnected ? 'success' : 'danger'}
                className="flex items-center gap-1.5 px-2 py-1 text-xs"
              >
                {realtimeConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {realtimeConnected ? 'Ao vivo' : 'Offline'}
              </GlassBadge>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <GlassInput
              type="text"
              placeholder="Buscar conversas..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 py-2 text-sm"
            />
          </div>

          <select
            value={conversationFilter}
            onChange={(e) => setConversationFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas</option>
            <option value="open" className="bg-emerald-900">Abertas</option>
            <option value="pending" className="bg-emerald-900">Pendentes</option>
            <option value="resolved" className="bg-emerald-900">Resolvidas</option>
          </select>
        </div>

        {/* Connection filter */}
        <div className="p-3 border-b border-white/10 flex gap-2">
          <select
            value={selectedConnectionFilter}
            onChange={(e) => setSelectedConnectionFilter(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas conexões</option>
            {connections.map(conn => (
              <option key={conn.id} value={conn.id} className="bg-emerald-900">
                {conn.phoneNumber}
              </option>
            ))}
          </select>
          <select
            value={selectedLabelFilter}
            onChange={(e) => setSelectedLabelFilter(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas labels</option>
            {labels.map(label => (
              <option key={label.id} value={label.id} className="bg-emerald-900">
                {label.name}
              </option>
            ))}
          </select>
        </div>

        {/* Agent filter */}
        <div className="p-3 border-b border-white/10">
          <select
            value={selectedAgentFilter}
            onChange={(e) => setSelectedAgentFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todos os agentes</option>
            <option value="mine" className="bg-emerald-900">Minhas conversas</option>
            <option value="" className="bg-emerald-900">Não atribuídas</option>
            {agents.map(agent => (
              <option key={agent.id} value={agent.id} className="bg-emerald-900">
                {agent.name} {agent.status === 'online' ? '🟢' : '⚫'}
              </option>
            ))}
          </select>
        </div>

        {/* Conversations */}
        <div className="flex-1 overflow-y-auto">
          {conversationsLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-white/50">
              <MessageSquare className="w-12 h-12 mb-3" />
              <p>Nenhuma conversa encontrada</p>
            </div>
          ) : (
            filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => setSelectedConversation(conv)}
                className={cn(
                  'p-4 border-b border-white/5 cursor-pointer transition-all',
                  'hover:bg-white/5',
                  selectedConversation?.id === conv.id && 'bg-emerald-500/20 border-l-4 border-l-emerald-500'
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="relative">
                    <ContactAvatar
                      src={conv.contactAvatar}
                      name={conv.contactName}
                      sizeClassName="w-12 h-12"
                    />
                    <div className={cn(
                      'absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full border-2',
                      isDark ? 'border-emerald-900' : 'border-slate-200',
                      getConversationStatusColor(conv.status)
                    )} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-white font-medium truncate">{conv.contactName}</span>
                      <span className="text-white/40 text-xs">{formatTime(conv.lastMessageAt)}</span>
                    </div>
                    <p className="text-white/50 text-sm truncate">{conv.lastMessagePreview}</p>
                    <div className="flex items-center gap-1 mt-1">
                      <span className="text-white/30 text-xs">{conv.contactPhone}</span>
                      {/* Labels badges */}
                      {(conv.labels || []).slice(0, 2).map(labelId => {
                        const label = getLabelById(labelId);
                        if (!label) return null;
                        return (
                          <span
                            key={labelId}
                            className={cn(
                              'text-xs px-1.5 py-0.5 rounded-full font-medium',
                              isDark ? 'text-white/90' : 'text-slate-700 border border-slate-200'
                            )}
                            style={(() => {
                              const hex = normalizeHexColor(label.color);
                              if (!hex) return undefined;
                              return {
                                backgroundColor: `${hex}${isDark ? '40' : '1A'}`,
                                borderColor: !isDark ? `${hex}33` : undefined
                              };
                            })()}
                          >
                            {label.name}
                          </span>
                        );
                      })}
                      {(conv.labels || []).length > 2 && (
                        <span className="text-xs text-white/40">+{conv.labels.length - 2}</span>
                      )}
                    </div>
                  </div>
                  {conv.unreadCount > 0 && (
                    <span className="bg-emerald-500 text-white text-xs font-bold px-2 py-1 rounded-full min-w-[24px] text-center animate-pulse">
                      {conv.unreadCount}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <TooltipProvider>
        {/* Chat Area */}
        <div
          className={cn(
            'flex-1 min-h-0 bg-gradient-to-br from-emerald-950/50 to-teal-950/50',
            selectedConversation ? 'flex flex-col' : 'hidden lg:flex lg:flex-col'
          )}
        >
          {selectedConversation ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b border-white/10 backdrop-blur-sm bg-black/20">
                <div className="flex items-start sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setSelectedConversation(null)}
                      className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition-colors"
                      title="Voltar"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <ContactAvatar
                      src={selectedConversation.contactAvatar}
                      name={selectedConversation.contactName}
                      sizeClassName="w-10 h-10"
                    />
                    <div>
                      {editingContactName ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={contactNameValue}
                            onChange={(e) => setContactNameValue(e.target.value)}
                            className="px-2 py-1 bg-white/10 border border-white/20 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleContactNameSave();
                              if (e.key === 'Escape') setEditingContactName(false);
                            }}
                          />
                          <button
                            onClick={handleContactNameSave}
                            className="p-1 bg-emerald-500 rounded text-white hover:bg-emerald-600"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingContactName(false)}
                            className="p-1 bg-white/10 rounded text-white/60 hover:bg-white/20"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <h2 className="text-white font-medium">{selectedConversation.contactName}</h2>
                      )}
                      <button
                        onClick={handleContactNameClick}
                        className="text-white/50 text-sm hover:text-emerald-400 hover:underline transition-colors flex items-center gap-1"
                        title="Clique para editar nome do contato"
                      >
                        {selectedConversation.contactPhone}
                        <Edit2 className="w-3 h-3 opacity-0 group-hover:opacity-100" />
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap justify-end">
                    {/* Status select */}
                    <select
                      value={selectedConversation.status}
                      onChange={(e) => updateConversationStatus(selectedConversation.id, e.target.value)}
                      className="px-3 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none"
                    >
                      <option value="open" className="bg-emerald-900">Aberta</option>
                      <option value="pending" className="bg-emerald-900">Pendente</option>
                      <option value="resolved" className="bg-emerald-900">Resolvida</option>
                    </select>

                    {/* Assign button */}
                    <div className="relative">
                      <button
                        onClick={() => setShowAssignMenu(!showAssignMenu)}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                        title="Atribuir"
                      >
                        <Users className="w-5 h-5" />
                      </button>
                      {showAssignMenu && (
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <p className="text-white/50 text-xs px-2 mb-2">Atribuir para:</p>
                            {/* Sort agents: online first */}
                            {[...agents]
                              .sort((a, b) => (a.status === 'online' ? -1 : 1) - (b.status === 'online' ? -1 : 1))
                              .map(agent => (
                                <button
                                  key={agent.id}
                                  onClick={() => handleAssign(agent.id)}
                                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                                >
                                  <div className="relative">
                                    <img src={agent.avatar} alt={agent.name} className="w-6 h-6 rounded-full" />
                                    <span
                                      className={cn(
                                        'absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border',
                                        isDark ? 'border-emerald-900' : 'border-slate-200',
                                        getAgentStatusColor(agent.status)
                                      )}
                                    />
                                  </div>
                                  <span className="flex-1 text-left">{agent.name}</span>
                                  <span className="text-xs text-white/40 capitalize">{agent.status || 'offline'}</span>
                                </button>
                              ))}
                            {/* Unassign option */}
                            {selectedConversation?.assignedTo && (
                              <button
                                onClick={async () => {
                                  try {
                                    await ConversationsAPI.unassign(selectedConversation.id);
                                    toast.success('Conversa desatribuída');
                                    setShowAssignMenu(false);
                                  } catch (error) {
                                    toast.error('Erro ao desatribuir');
                                  }
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-500/20 text-red-400 text-sm mt-2 border-t border-white/10 pt-2"
                              >
                                <X className="w-4 h-4" />
                                Remover atribuição
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Labels button */}
                    <div className="relative">
                      <button
                        onClick={() => setShowLabelsMenu(!showLabelsMenu)}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                        title="Labels"
                      >
                        <Tag className="w-5 h-5" />
                      </button>
                      {showLabelsMenu && (
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <p className="text-white/50 text-xs px-2 mb-2">Adicionar label:</p>
                            {labels.map(label => (
                              <button
                                key={label.id}
                                onClick={() => handleAddLabel(label.id)}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                              >
                                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: label.color }} />
                                {label.name}
                              </button>
                            ))}
                            <div className="border-t border-white/10 mt-2 pt-2">
                              <button
                                onClick={() => {
                                  setShowLabelsMenu(false);
                                  setShowLabelsManager(true);
                                }}
                                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/70 hover:text-white text-sm"
                              >
                                <Tag className="w-4 h-4" />
                                Gerenciar Labels
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="relative">
                      <button
                        onClick={() => {
                          setShowMoreMenu(!showMoreMenu);
                          setShowAssignMenu(false);
                          setShowLabelsMenu(false);
                        }}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                        title="Mais opções"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      {showMoreMenu && (
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <button
                              onClick={handleViewContact}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <UserCircle className="w-4 h-4" />
                              Ver contato
                            </button>
                            <button
                              onClick={handleClearMessages}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <Trash2 className="w-4 h-4" />
                              Excluir mensagens
                            </button>
                            <button
                              onClick={handleDeleteConversation}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-500/20 text-red-400 text-sm mt-1"
                            >
                              <Trash2 className="w-4 h-4" />
                              Excluir conversa
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
                {messagesLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <>
                    {messages.map((msg) => (
                      <div key={msg.id}>
                        {(() => {
                          const rawContent = typeof msg.content === 'string'
                            ? msg.content
                            : msg.content == null
                              ? ''
                              : String(msg.content);
                          const rawTrim = rawContent.trim();
                          const normalizedType = normalizeMessageType(msg.type);
                          const fallback =
                            normalizedType === 'audio' ? '[Áudio]' :
                              normalizedType === 'image' ? '[Imagem]' :
                                normalizedType === 'video' ? '[Vídeo]' :
                                  normalizedType === 'document' ? '[Documento]' :
                                    normalizedType === 'sticker' ? '[Figurinha]' :
                                      '[Mensagem]';
                          const mediaUrlRaw =
                            typeof msg.mediaUrl === 'string' ? msg.mediaUrl :
                              typeof msg.media_url === 'string' ? msg.media_url :
                                typeof msg.url === 'string' ? msg.url :
                                  '';
                          const mediaUrl = typeof mediaUrlRaw === 'string' && mediaUrlRaw.trim() ? mediaUrlRaw.trim() : '';
                          const isMediaType = ['image', 'video', 'audio', 'document', 'sticker'].includes(normalizedType);
                          const canInlineMedia = Boolean(mediaUrl) && isMediaType;

                          // Check if the content contains a WhatsApp media URL (for image/video types)
                          const contentUrls = extractUrls(rawContent);
                          const contentWhatsappUrl = contentUrls.find(u => isWhatsappMediaUrl(u)) || '';
                          const hasWhatsappMediaInContent = Boolean(contentWhatsappUrl);

                          const effectiveMediaUrlCandidate = mediaUrl || (isMediaType && contentWhatsappUrl ? contentWhatsappUrl : '');
                          const inferredKindFromUrl = effectiveMediaUrlCandidate ? inferWhatsappMediaKind(effectiveMediaUrlCandidate) : 'unknown';

                          const meta = (msg && typeof msg === 'object' && msg.metadata && typeof msg.metadata === 'object') ? msg.metadata : null;
                          const proxyInfo = (() => {
                            if (!msg?.id) return null;
                            if (!meta) return null;
                            const remoteJid = meta.remote_jid ?? meta.remoteJid ?? meta.remotejid ?? null;
                            const instanceName = meta.instance_name ?? meta.instanceName ?? meta.instancename ?? null;
                            const rawFromMe = meta.from_me ?? meta.fromMe ?? meta.fromme ?? null;
                            const fromMe = (() => {
                              if (typeof rawFromMe === 'boolean') return rawFromMe;
                              if (typeof rawFromMe === 'number') return Boolean(rawFromMe);
                              if (typeof rawFromMe === 'string') {
                                const v = rawFromMe.trim().toLowerCase();
                                if (['true', '1', 'yes', 'y', 'sim'].includes(v)) return true;
                                if (['false', '0', 'no', 'n', 'nao', 'não', ''].includes(v)) return false;
                              }
                              return false;
                            })();
                            if (!remoteJid || !instanceName) return null;
                            return {
                              messageId: msg.id,
                              remoteJid,
                              instanceName,
                              fromMe
                            };
                          })();
                          const metaKindRaw = meta ? (meta.media_kind ?? meta.mediaKind ?? meta.kind ?? meta.type) : null;
                          const metaKind = normalizeMessageType(metaKindRaw);
                          const metaMimeRaw = meta ? (meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime) : null;
                          const metaMime = String(metaMimeRaw || '').toLowerCase();
                          const kindFromMime = metaMime.includes('webp')
                            ? 'sticker'
                            : (metaMime.startsWith('audio/') || metaMime.includes('opus') || metaMime.includes('ogg'))
                              ? 'audio'
                              : metaMime.startsWith('video/')
                                ? 'video'
                                : metaMime.startsWith('image/')
                                  ? 'image'
                                  : null;
                          // PRIORITY ORDER FOR MEDIA TYPE DETECTION:
                          // 1. normalizedType (from msg.type - saved by backend, most reliable)
                          // 2. metaKind (from metadata.media_kind - also from backend)
                          // 3. kindFromMime (inferred from mime_type)
                          // 4. inferredKindFromUrl (inferred from URL - least reliable fallback)
                          const renderType = (normalizedType && normalizedType !== 'unknown' && normalizedType !== 'text')
                            ? normalizedType
                            : (metaKind && metaKind !== 'unknown' && metaKind !== 'text')
                              ? metaKind
                              : (kindFromMime && kindFromMime !== 'unknown')
                                ? kindFromMime
                                : (inferredKindFromUrl !== 'unknown')
                                  ? inferredKindFromUrl
                                  : normalizedType;

                          const base64MediaUrl = (() => {
                            if (!isMediaType) return '';
                            if (!rawTrim) return '';
                            if (rawTrim.startsWith('data:')) return rawTrim;
                            if (!isLikelyBareBase64(rawTrim)) return '';
                            const mime = resolveMediaMimeType(renderType, metaMime);
                            return toDataUrlFromBareBase64(rawTrim, mime);
                          })();

                          const effectiveMediaUrl = effectiveMediaUrlCandidate || base64MediaUrl;

                          const hasContent = rawTrim.length > 0 && !base64MediaUrl;
                          const displayContent = hasContent ? rawContent : fallback;

                          const urls = extractUrls(displayContent);
                          const hasOnlyUrl = normalizedType === 'text' && urls.length === 1 && displayContent.trim() === urls[0];
                          const primaryUrl = hasOnlyUrl ? urls[0] : '';
                          const isWhatsappMedia = primaryUrl ? isWhatsappMediaUrl(primaryUrl) : false;

                          const mediaRenderableKind = ['image', 'video', 'audio', 'document', 'sticker'].includes(renderType);
                          const shouldRenderMedia = mediaRenderableKind && (Boolean(effectiveMediaUrl) || Boolean(proxyInfo));

                          const mediaKind = isWhatsappMedia ? inferWhatsappMediaKind(primaryUrl) :
                            (hasWhatsappMediaInContent ? inferWhatsappMediaKind(contentWhatsappUrl) : 'unknown');
                          const whatsappMeta = isWhatsappMedia ? getWhatsappMediaMeta(mediaKind) : null;
                          const originInfo = getMessageOriginInfo(msg);
                          // Use renderType for badge - it already has correct priority logic
                          const typeForBadge = ['image', 'video', 'audio', 'document', 'sticker'].includes(renderType)
                            ? renderType
                            : (hasOnlyUrl && isWhatsappMedia
                              ? (mediaKind === 'sticker' ? 'sticker' : mediaKind === 'audio' ? 'audio' : mediaKind === 'video' ? 'video' : 'image')
                              : null);
                          const typeBadgeInfo = typeForBadge ? getMessageTypeBadgeInfo(typeForBadge) : null;

                          return (
                            <div
                              className={cn(
                                'flex group',
                                msg.direction === 'outbound' ? 'justify-end' : 'justify-start'
                              )}
                            >
                              {msg.direction === 'outbound' && (
                                <div className="self-center mr-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                                  <button
                                    onClick={() => handleDeleteMessage(msg.id)}
                                    className="p-1.5 rounded-full hover:bg-red-500/20 text-white/40 hover:text-red-400 transition-all"
                                    title="Excluir"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                  <button
                                    onClick={() => { setReplyToMessage(msg); inputRef.current?.focus(); }}
                                    className="p-1.5 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition-all"
                                    title="Responder"
                                  >
                                    <Reply className="w-4 h-4" />
                                  </button>
                                </div>
                              )}

                              <div
                                className={cn(
                                  'max-w-[70%] rounded-2xl px-4 py-3',
                                  msg.direction === 'outbound'
                                    ? 'bg-emerald-500 text-white rounded-br-md'
                                    : 'bg-white/10 backdrop-blur-sm text-white rounded-bl-md'
                                )}
                              >
                                {typeBadgeInfo && (
                                  <div className="flex items-center gap-2 mb-2">
                                    <div
                                      className={cn(
                                        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] uppercase tracking-wide',
                                        typeBadgeInfo.badgeClass
                                      )}
                                    >
                                      <span className={cn('w-1.5 h-1.5 rounded-full', typeBadgeInfo.dotClass)} />
                                      {getMessageTypeIcon(typeForBadge)}
                                      <span>{typeBadgeInfo.label}</span>
                                    </div>
                                  </div>
                                )}
                                {shouldRenderMedia && (renderType === 'image' || renderType === 'video' || renderType === 'audio' || renderType === 'sticker' || renderType === 'document') && (
                                  <WhatsAppMediaDisplay
                                    type={renderType}
                                    mediaUrl={effectiveMediaUrl}
                                    content={displayContent}
                                    direction={msg.direction}
                                    onImageClick={setMediaViewer}
                                    messageId={msg.id}
                                    proxyInfo={proxyInfo}
                                    meta={meta}
                                  />
                                )}
                                {/* WhatsApp media URL in text message - render inline */}
                                {normalizedType === 'text' && hasOnlyUrl && isWhatsappMedia && (
                                  <WhatsAppMediaDisplay
                                    type={mediaKind === 'video' ? 'video' : mediaKind === 'audio' ? 'audio' : 'image'}
                                    mediaUrl={primaryUrl}
                                    content={whatsappMeta?.label || 'Mídia do WhatsApp'}
                                    direction={msg.direction}
                                    onImageClick={setMediaViewer}
                                    messageId={msg.id}
                                    proxyInfo={proxyInfo}
                                    meta={meta}
                                  />
                                )}
                                {normalizedType === 'text' && hasOnlyUrl && !isWhatsappMedia && (
                                  <a
                                    href={primaryUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className={cn(
                                      'flex items-center gap-3 p-3 rounded-xl border w-full',
                                      msg.direction === 'outbound'
                                        ? 'bg-white/10 border-white/20 hover:bg-white/15'
                                        : 'bg-black/20 border-white/10 hover:bg-black/30'
                                    )}
                                  >
                                    <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
                                      <Link2 className="w-5 h-5 opacity-80" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium truncate">{shortenUrl(primaryUrl)}</p>
                                      <p className="text-xs opacity-70 truncate">{primaryUrl}</p>
                                    </div>
                                  </a>
                                )}
                                {(!shouldRenderMedia && !(normalizedType === 'text' && hasOnlyUrl)) && (
                                  <p className={cn('whitespace-pre-wrap', !hasContent && 'italic text-white/70')}>
                                    {renderTextWithLinks(displayContent)}
                                  </p>
                                )}
                                {shouldRenderMedia && hasContent && renderType !== 'document' && (
                                  <p className="whitespace-pre-wrap mt-2">
                                    {renderTextWithLinks(rawContent)}
                                  </p>
                                )}
                                <div
                                  className={cn(
                                    'flex items-center justify-between gap-2 mt-1',
                                    msg.direction === 'outbound' ? 'text-white/70' : 'text-white/40'
                                  )}
                                >
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <div
                                        className={cn(
                                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] uppercase tracking-wide',
                                          originInfo.badgeClass
                                        )}
                                      >
                                        <span
                                          className={cn(
                                            'w-1.5 h-1.5 rounded-full',
                                            originInfo.dotClass
                                          )}
                                        />
                                        <span>{originInfo.label}</span>
                                      </div>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" sideOffset={6}>
                                      {originInfo.tooltip}
                                    </TooltipContent>
                                  </Tooltip>
                                  <div className="flex items-center gap-1">
                                    <span className="text-xs">
                                      {new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    {msg.direction === 'outbound' && getStatusIcon(msg.status)}
                                  </div>
                                </div>
                              </div>

                              {msg.direction === 'inbound' && (
                                <div className="self-center ml-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                                  <button
                                    onClick={() => handleDeleteMessage(msg.id)}
                                    className="p-1.5 rounded-full hover:bg-red-500/20 text-white/40 hover:text-red-400 transition-all"
                                    title="Excluir"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                  <button
                                    onClick={() => { setReplyToMessage(msg); inputRef.current?.focus(); }}
                                    className="p-1.5 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition-all"
                                    title="Responder"
                                  >
                                    <Reply className="w-4 h-4" />
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* File Upload Panel */}
              {showFileUpload && (
                <div className="p-4 border-t border-white/10">
                  <FileUpload
                    conversationId={selectedConversation?.id}
                    onUpload={handleFileUpload}
                    onCancel={() => setShowFileUpload(false)}
                  />
                </div>
              )}

              {/* Typing Indicator */}
              {selectedConversation && getTypingContact(selectedConversation.id) && (
                <div className="px-4 pb-2">
                  <TypingIndicator
                    contactName={getTypingContact(selectedConversation.id)}
                  />
                </div>
              )}

              {/* Reply Preview */}
              {replyToMessage && (
                <div className="px-4 pt-2 border-t border-white/10">
                  <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg border-l-2 border-emerald-500">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Reply className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400 text-xs font-medium">
                          Respondendo a {replyToMessage.direction === 'inbound' ? selectedConversation?.contactName : 'você'}
                        </span>
                      </div>
                      <p className="text-white/60 text-sm truncate">
                        {(typeof replyToMessage.content === 'string' && replyToMessage.content.trim().length > 0)
                          ? replyToMessage.content
                          : '[Mensagem]'}
                      </p>
                    </div>
                    <button
                      onClick={() => setReplyToMessage(null)}
                      className="p-1 hover:bg-white/10 rounded text-white/40 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="p-4 border-t border-white/10 backdrop-blur-sm bg-black/20 relative">
                {/* Quick Replies Panel */}
                {showQuickReplies && (
                  <QuickRepliesPanel
                    onSelect={handleQuickReplySelect}
                    onClose={() => setShowQuickReplies(false)}
                  />
                )}


                <form onSubmit={handleSendMessage} className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowFileUpload(!showFileUpload)}
                      className={cn(
                        'p-2 rounded-lg transition-colors',
                        showFileUpload
                          ? 'bg-emerald-500 text-white'
                          : 'hover:bg-white/10 text-white/60 hover:text-white'
                      )}
                    >
                      <Paperclip className="w-5 h-5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowQuickReplies(!showQuickReplies)}
                      className={cn(
                        'p-2 rounded-lg transition-colors',
                        showQuickReplies
                          ? 'bg-emerald-500 text-white'
                          : 'hover:bg-white/10 text-white/60 hover:text-white'
                      )}
                      title="Respostas rápidas (Ctrl+/)"
                    >
                      <Zap className="w-5 h-5" />
                    </button>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={() => setUseSignature(!useSignature)}
                          className={cn(
                            'p-2 rounded-lg transition-colors',
                            useSignature
                              ? 'bg-emerald-500 text-white'
                              : 'hover:bg-white/10 text-white/60 hover:text-white'
                          )}
                          title={useSignature ? 'Assinatura ativada' : 'Assinatura desativada'}
                        >
                          <PenLine className="w-5 h-5" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {useSignature ? 'Desativar assinatura' : 'Ativar assinatura'}
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <div className="flex items-center gap-2 flex-1">
                    <div className="flex-1 relative">
                      <GlassInput
                        ref={inputRef}
                        type="text"
                        placeholder="Digite sua mensagem..."
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        className="pr-12"
                      />
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <button
                          type="button"
                          onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                          className={cn(
                            "text-white/40 hover:text-white/60 transition-colors",
                            showEmojiPicker && "text-emerald-400"
                          )}
                        >
                          <Smile className="w-5 h-5" />
                        </button>
                        {showEmojiPicker && (
                          <EmojiPicker
                            onSelect={handleEmojiSelect}
                            onClose={() => setShowEmojiPicker(false)}
                            position="top"
                          />
                        )}
                      </div>
                    </div>
                    <GlassButton type="submit" className="px-4 py-3" disabled={!newMessage.trim()}>
                      <Send className="w-5 h-5" />
                    </GlassButton>
                  </div>
                </form>

                {/* Typing hint */}
                <p className="text-white/30 text-xs mt-2 text-center">
                  Ctrl+/ para respostas rápidas • Enter para enviar
                </p>
              </div>
            </>
          ) : (
            /* Empty State */
            <div className="flex-1 flex flex-col items-center justify-center text-white/50">
              <div className="w-24 h-24 rounded-full bg-white/10 flex items-center justify-center mb-4">
                <MessageSquare className="w-12 h-12" />
              </div>
              <h3 className="text-xl font-medium text-white mb-2">Nenhuma conversa selecionada</h3>
              <p>Selecione uma conversa para começar a conversar</p>
            </div>
          )}
        </div>
      </TooltipProvider>

      <Dialog open={mediaViewer.open} onOpenChange={(open) => setMediaViewer(prev => ({ ...prev, open }))}>
        <DialogContent className="max-w-5xl bg-black/80 border border-white/10 p-0">
          <DialogTitle className="sr-only">
            {currentViewerItem?.title || mediaViewer.title || 'Mídia'}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Visualizador de mídia
          </DialogDescription>
          <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/10">
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {currentViewerItem?.title || mediaViewer.title || 'Mídia'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (currentViewerIndex > 0) {
                    const prev = imageViewerItems[currentViewerIndex - 1];
                    setMediaViewer({ open: true, url: prev.url, title: prev.title, messageId: prev.id || null, kind: prev.kind || null, proxyInfo: mediaViewer?.proxyInfo || null });
                  }
                }}
                disabled={currentViewerIndex <= 0}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 disabled:opacity-40 disabled:hover:bg-white/10 text-white text-sm"
                aria-label="Mídia anterior"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => {
                  if (currentViewerIndex >= 0 && currentViewerIndex < imageViewerItems.length - 1) {
                    const next = imageViewerItems[currentViewerIndex + 1];
                    setMediaViewer({ open: true, url: next.url, title: next.title, messageId: next.id || null, kind: next.kind || null, proxyInfo: mediaViewer?.proxyInfo || null });
                  }
                }}
                disabled={currentViewerIndex < 0 || currentViewerIndex >= imageViewerItems.length - 1}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 disabled:opacity-40 disabled:hover:bg-white/10 text-white text-sm"
                aria-label="Próxima mídia"
              >
                <ChevronLeft className="w-4 h-4 rotate-180" />
              </button>

              <div className="w-px h-6 bg-white/10 mx-1" />

              <button
                type="button"
                onClick={() => setViewerZoom(z => Math.max(0.5, Math.round((z - 0.25) * 100) / 100))}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm"
                aria-label="Diminuir zoom"
              >
                –
              </button>
              <button
                type="button"
                onClick={() => setViewerZoom(1)}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm tabular-nums"
                aria-label="Resetar zoom"
              >
                {Math.round(viewerZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={() => setViewerZoom(z => Math.min(4, Math.round((z + 0.25) * 100) / 100))}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm"
                aria-label="Aumentar zoom"
              >
                +
              </button>

              <div className="w-px h-6 bg-white/10 mx-1" />

              <button
                type="button"
                onClick={() => setViewerRotation(r => (r - 90) % 360)}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm"
                aria-label="Rotacionar à esquerda"
              >
                90°
              </button>
              <button
                type="button"
                onClick={() => setViewerRotation(r => (r + 90) % 360)}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm"
                aria-label="Rotacionar à direita"
              >
                90°
              </button>

              <div className="w-px h-6 bg-white/10 mx-1" />

              {currentViewerItem?.url && (
                <a
                  href={viewerResolvedUrl || currentViewerItem.url}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/30 text-emerald-100 text-sm"
                >
                  Baixar
                </a>
              )}
              <button
                type="button"
                onClick={() => setMediaViewer(prev => ({ ...prev, open: false }))}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/15 text-white"
                aria-label="Fechar visualizador"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="relative h-[80vh] overflow-auto">
            {viewerLoading && !viewerLoadError && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-white/20 border-t-white/70 rounded-full animate-spin" />
              </div>
            )}

            {viewerLoadError && (
              <div className="h-full flex items-center justify-center p-6 text-white/70">
                <div className="max-w-md text-center">
                  <p className="text-sm">Não foi possível carregar esta mídia.</p>
                  {(viewerResolvedUrl || currentViewerItem?.url) && (
                    <a href={viewerResolvedUrl || currentViewerItem.url} target="_blank" rel="noreferrer" className="text-white underline mt-2 inline-block">
                      Abrir em nova aba
                    </a>
                  )}
                </div>
              </div>
            )}

            {!viewerLoadError && (viewerResolvedUrl || currentViewerItem?.url) && (() => {
              const kind = currentViewerItem?.kind || mediaViewer?.kind || 'image';
              const url = viewerResolvedUrl || currentViewerItem?.url || '';
              const lc = String(url || '').toLowerCase();
              const isPdf =
                viewerResolvedMimeType === 'application/pdf' ||
                lc.startsWith('data:application/pdf') ||
                lc.includes('.pdf');

              if (kind === 'document') {
                if (isPdf) {
                  return (
                    <div className="min-h-full p-0">
                      <iframe
                        title={currentViewerItem?.title || 'Documento'}
                        src={url}
                        className="w-full h-[80vh] rounded-b-lg"
                        sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
                        onLoad={() => setViewerLoading(false)}
                      />
                    </div>
                  );
                }

                setTimeout(() => setViewerLoading(false), 0);
                return (
                  <div className="min-h-full flex items-center justify-center p-6">
                    <div className="w-full max-w-md rounded-xl border border-white/10 bg-white/5 p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
                          <FileText className="w-5 h-5 opacity-80" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate">{currentViewerItem?.title || 'Documento'}</p>
                          <p className="text-xs text-white/60 truncate">{shortenUrl(url)}</p>
                        </div>
                      </div>
                      <div className="mt-4 flex items-center justify-end gap-2">
                        <a
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-white text-sm"
                        >
                          Abrir
                        </a>
                        <a
                          href={url}
                          download
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-400/30 text-emerald-100 text-sm"
                        >
                          Baixar
                        </a>
                      </div>
                    </div>
                  </div>
                );
              }

              return (
                <div className="min-h-full flex flex-col items-center justify-center p-4 gap-2">
                  <div className="flex-1 flex items-center justify-center w-full">
                    <img
                      src={url}
                      alt={currentViewerItem?.title || 'Imagem'}
                      className="max-w-full h-auto object-contain rounded-lg"
                      style={{ transform: `scale(${viewerZoom}) rotate(${viewerRotation}deg)`, transformOrigin: 'center' }}
                      referrerPolicy="no-referrer"
                      onLoad={() => setViewerLoading(false)}
                      onError={() => {
                        setViewerLoading(false);
                        setViewerLoadError(true);
                      }}
                    />
                  </div>
                  <div className="w-full max-w-2xl text-xs text-white/70 flex flex-wrap items-center justify-between gap-2">
                    <span className="truncate">
                      {viewerResolvedMimeType || currentViewerItem?.metadata?.mime_type || currentViewerItem?.metadata?.mimeType || 'Formato desconhecido'}
                    </span>
                    {(() => {
                      const meta = currentViewerMessage && typeof currentViewerMessage.metadata === 'object' ? currentViewerMessage.metadata : currentViewerItem?.metadata;
                      const rawSize = meta ? (meta.file_size ?? meta.fileSize ?? meta.size ?? meta.bytes ?? null) : null;
                      const sizeNumber = typeof rawSize === 'number' ? rawSize : rawSize ? Number(rawSize) : 0;
                      if (!sizeNumber || Number.isNaN(sizeNumber)) return null;
                      const kb = sizeNumber / 1024;
                      const mb = kb / 1024;
                      const formatted = mb >= 1 ? `${mb.toFixed(2)} MB` : `${kb.toFixed(1)} KB`;
                      return <span className="truncate">Tamanho: {formatted}</span>;
                    })()}
                  </div>
                </div>
              );
            })()}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={showPurgeAllDialog} onOpenChange={(open) => !purgingAll && setShowPurgeAllDialog(open)}>
        <DialogContent className="max-w-md bg-black/70 border border-white/10">
          <DialogTitle className="sr-only">Excluir todas as conversas</DialogTitle>
          <DialogDescription className="sr-only">
            Confirmação para excluir todas as conversas do tenant
          </DialogDescription>
          <div className="p-6">
            <h2 className="text-lg font-bold text-white mb-2">Excluir todas as conversas</h2>
            <p className="text-white/70 text-sm">
              Isso vai remover todas as conversas e mensagens deste tenant. Essa ação não pode ser desfeita.
            </p>
            <div className="mt-5 flex items-center justify-end gap-3">
              <GlassButton
                variant="secondary"
                onClick={() => setShowPurgeAllDialog(false)}
                disabled={purgingAll}
                className="px-4 py-2"
              >
                Cancelar
              </GlassButton>
              <GlassButton
                variant="danger"
                onClick={handlePurgeAllConversations}
                loading={purgingAll}
                className="px-4 py-2"
              >
                Excluir tudo
              </GlassButton>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Contact View Modal */}
      <Dialog open={showContactModal} onOpenChange={setShowContactModal}>
        <DialogContent className="max-w-md bg-white/10 backdrop-blur-xl border border-white/20">
          <DialogTitle className="sr-only">Informações do contato</DialogTitle>
          <DialogDescription className="sr-only">
            Detalhes do contato selecionado
          </DialogDescription>
          <div className="p-6">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Users className="w-5 h-5 text-emerald-400" />
              Informações do Contato
            </h2>

            {contactData ? (
              <div className="space-y-4">
                {/* Avatar and Name */}
                <div className="flex items-center gap-4">
                  <ContactAvatar
                    src={null}
                    name={contactData.fullName}
                    sizeClassName="w-16 h-16"
                  />
                  <div>
                    <h3 className="text-lg font-semibold text-white">{contactData.fullName}</h3>
                    <p className="text-white/60 text-sm">{contactData.phone}</p>
                  </div>
                </div>

                {/* Contact Details */}
                <div className="space-y-3 mt-6">
                  {/* Phone */}
                  <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <Phone className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <p className="text-white/50 text-xs">Telefone</p>
                      <p className="text-white">{contactData.phone}</p>
                    </div>
                  </div>

                  {/* Email */}
                  {contactData.email && (
                    <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <Mail className="w-4 h-4 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-white/50 text-xs">Email</p>
                        <p className="text-white">{contactData.email}</p>
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {contactData.tags && contactData.tags.length > 0 && (
                    <div className="p-3 bg-white/5 rounded-lg">
                      <p className="text-white/50 text-xs mb-2">Tags</p>
                      <div className="flex flex-wrap gap-2">
                        {contactData.tags.map((tag, idx) => (
                          <GlassBadge key={idx} variant="success" className="px-2 py-1 text-xs">
                            {tag}
                          </GlassBadge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Custom Fields */}
                  {contactData.customFields && Object.keys(contactData.customFields).length > 0 && (
                    <div className="p-3 bg-white/5 rounded-lg">
                      <p className="text-white/50 text-xs mb-2">Campos Personalizados</p>
                      <div className="space-y-2">
                        {Object.entries(contactData.customFields).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-white/60 text-sm capitalize">{key.replace(/_/g, ' ')}</span>
                            <span className="text-white text-sm">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source */}
                  {contactData.source && (
                    <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                        <FileText className="w-4 h-4 text-purple-400" />
                      </div>
                      <div>
                        <p className="text-white/50 text-xs">Origem</p>
                        <p className="text-white capitalize">{contactData.source}</p>
                      </div>
                    </div>
                  )}

                  {/* Created At */}
                  {contactData.createdAt && (
                    <div className="text-center text-white/40 text-xs mt-4">
                      Criado em {new Date(contactData.createdAt).toLocaleDateString('pt-BR')}
                    </div>
                  )}
                </div>

                {/* Close Button */}
                <div className="mt-6 flex justify-end">
                  <GlassButton onClick={() => setShowContactModal(false)}>
                    Fechar
                  </GlassButton>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center p-8">
                <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Labels Manager Modal */}
      <LabelsManager
        isOpen={showLabelsManager}
        onClose={() => setShowLabelsManager(false)}
        onLabelsChange={loadLabels}
      />
    </div>
  );
};

export default Inbox;
