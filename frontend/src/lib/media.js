const normalizeMessageType = (type) => {
  const raw = String(type || '').trim();
  if (!raw) return 'unknown';

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

const safeLower = (v) => String(v || '').trim().toLowerCase();

const isDataUrl = (url) => typeof url === 'string' && url.startsWith('data:');

const extractMimeFromDataUrl = (dataUrl) => {
  if (!isDataUrl(dataUrl)) return '';
  const semi = dataUrl.indexOf(';');
  const comma = dataUrl.indexOf(',');
  if (semi < 0 || comma < 0 || semi > comma) return '';
  const header = dataUrl.slice(5, semi);
  return safeLower(header);
};

const decodeBase64Head = (base64, byteCount) => {
  const s = String(base64 || '');
  if (!s) return new Uint8Array(0);
  const want = Math.max(0, Math.min(256, Number(byteCount) || 0));
  const takeChars = Math.ceil(want / 3) * 4;
  let chunk = s.slice(0, takeChars);
  while (chunk.length % 4 !== 0) chunk += '=';

  try {
    const bin = atob(chunk);
    const out = new Uint8Array(Math.min(bin.length, want));
    for (let i = 0; i < out.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return new Uint8Array(0);
  }
};

const sniffMimeFromBytes = (bytes) => {
  if (!bytes || bytes.length < 4) return '';
  const b0 = bytes[0];
  const b1 = bytes[1];
  const b2 = bytes[2];

  if (b0 === 0xff && b1 === 0xd8 && b2 === 0xff) return 'image/jpeg';
  if (
    bytes.length >= 8 &&
    b0 === 0x89 &&
    b1 === 0x50 &&
    b2 === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) return 'image/png';
  if (bytes.length >= 6) {
    const g = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5]);
    if (g === 'GIF87a' || g === 'GIF89a') return 'image/gif';
  }
  if (bytes.length >= 4) {
    const s4 = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
    if (s4 === '%PDF') return 'application/pdf';
    if (s4 === 'OggS') return 'audio/ogg';
    if (s4 === 'RIFF' && bytes.length >= 12) {
      const sig = String.fromCharCode(bytes[8], bytes[9], bytes[10], bytes[11]);
      if (sig === 'WEBP') return 'image/webp';
      if (sig === 'WAVE') return 'audio/wav';
    }
  }
  if (bytes.length >= 3) {
    const s3 = String.fromCharCode(bytes[0], bytes[1], bytes[2]);
    if (s3 === 'ID3') return 'audio/mpeg';
  }
  if (bytes.length >= 8) {
    const ftyp = String.fromCharCode(bytes[4], bytes[5], bytes[6], bytes[7]);
    if (ftyp === 'ftyp') return 'video/mp4';
  }
  if (bytes.length >= 4) {
    const s2 = String.fromCharCode(bytes[0], bytes[1]);
    if (s2 === 'PK') return 'application/zip';
  }

  return '';
};

const kindFromMime = (mimeType) => {
  const mt = safeLower(mimeType);
  if (!mt) return 'unknown';
  if (mt === 'image/webp') return 'sticker';
  if (mt.startsWith('image/')) return 'image';
  if (mt.startsWith('audio/') || mt.includes('opus') || mt.includes('ogg')) return 'audio';
  if (mt.startsWith('video/')) return 'video';
  return 'document';
};

const kindFromUrl = (url) => {
  if (typeof url !== 'string' || !url.trim()) return 'unknown';
  if (isDataUrl(url)) return kindFromMime(extractMimeFromDataUrl(url));

  try {
    const u = new URL(url);
    const path = (u.pathname || '').toLowerCase();
    const qpMime = safeLower(u.searchParams.get('mimeType') || u.searchParams.get('mime_type'));
    if (qpMime) return kindFromMime(qpMime);

    if (path.endsWith('.webp')) return 'sticker';
    if (path.endsWith('.jpg') || path.endsWith('.jpeg') || path.endsWith('.png') || path.endsWith('.gif')) return 'image';
    if (path.endsWith('.mp4') || path.endsWith('.3gp') || path.endsWith('.webm')) return 'video';
    if (path.endsWith('.ogg') || path.endsWith('.opus') || path.endsWith('.mp3') || path.endsWith('.wav') || path.endsWith('.webm')) return 'audio';
    if (path.endsWith('.pdf') || path.endsWith('.doc') || path.endsWith('.docx') || path.endsWith('.txt')) return 'document';
    return 'unknown';
  } catch {
    return 'unknown';
  }
};

export const resolveMessageMedia = (message) => {
  const msg = message && typeof message === 'object' ? message : {};
  const type = normalizeMessageType(msg.type);
  const meta = msg.metadata && typeof msg.metadata === 'object' ? msg.metadata : {};

  const metaKind = normalizeMessageType(meta.media_kind ?? meta.mediaKind ?? meta.kind ?? meta.type);
  const metaMime = safeLower(meta.mime_type ?? meta.mimeType ?? meta.mimetype ?? meta.mime);

  const mediaUrl =
    typeof msg.mediaUrl === 'string' ? msg.mediaUrl :
      typeof msg.media_url === 'string' ? msg.media_url :
        typeof msg.url === 'string' ? msg.url :
          '';

  const content = typeof msg.content === 'string' ? msg.content : (msg.content == null ? '' : String(msg.content));

  if (metaKind !== 'unknown' && metaKind !== 'text') {
    return {
      kind: metaKind,
      mimeType: metaMime || '',
      confidence: 'high',
      mediaUrl: mediaUrl || '',
      content
    };
  }

  if (metaMime) {
    return {
      kind: kindFromMime(metaMime),
      mimeType: metaMime,
      confidence: 'medium',
      mediaUrl: mediaUrl || '',
      content
    };
  }

  if (type !== 'unknown' && type !== 'text') {
    return {
      kind: type,
      mimeType: '',
      confidence: 'medium',
      mediaUrl: mediaUrl || '',
      content
    };
  }

  const urlKind = kindFromUrl(mediaUrl || '');
  if (urlKind !== 'unknown') {
    return {
      kind: urlKind,
      mimeType: '',
      confidence: 'low',
      mediaUrl: mediaUrl || '',
      content
    };
  }

  if (isDataUrl(mediaUrl)) {
    const mime = extractMimeFromDataUrl(mediaUrl);
    const head = decodeBase64Head(String(mediaUrl).split(',')[1] || '', 96);
    const sniffed = sniffMimeFromBytes(head);
    const mimeType = sniffed || mime || '';
    const kind = kindFromMime(mimeType);
    return { kind, mimeType, confidence: sniffed ? 'high' : (mime ? 'medium' : 'low'), mediaUrl: mediaUrl || '', content };
  }

  return { kind: 'unknown', mimeType: '', confidence: 'low', mediaUrl: mediaUrl || '', content };
};

export const __testOnly = {
  normalizeMessageType,
  extractMimeFromDataUrl,
  decodeBase64Head,
  sniffMimeFromBytes,
  kindFromMime,
  kindFromUrl
};
