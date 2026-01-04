import React, { useState, useRef } from 'react';
import { Upload, X, Image, FileText, Film, Mic, Loader2 } from 'lucide-react';
import { GlassButton } from './GlassCard';
import { cn } from '../lib/utils';
import { toast } from './ui/glass-toaster';
import { UploadAPI } from '../lib/api';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const ALLOWED_TYPES = {
  image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
  video: ['video/mp4', 'video/webm', 'video/quicktime'],
  audio: ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm'],
  document: ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
};

const getFileType = (mimeType) => {
  for (const [type, mimes] of Object.entries(ALLOWED_TYPES)) {
    if (mimes.includes(mimeType)) return type;
  }
  return 'document';
};

const getFileIcon = (type) => {
  switch (type) {
    case 'image': return <Image className="w-6 h-6" />;
    case 'video': return <Film className="w-6 h-6" />;
    case 'audio': return <Mic className="w-6 h-6" />;
    default: return <FileText className="w-6 h-6" />;
  }
};

const FileUpload = ({ conversationId, onUpload, onCancel, disabled }) => {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleFileSelect = (selectedFile) => {
    if (!selectedFile) return;

    // Validate file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      toast.error('Arquivo muito grande', { description: 'Máximo permitido: 10MB' });
      return;
    }

    const fileType = getFileType(selectedFile.type);
    setFile({ file: selectedFile, type: fileType, name: selectedFile.name });

    // Generate preview for images
    if (fileType === 'image') {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(selectedFile);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    handleFileSelect(droppedFile);
  };

  const handleUpload = async () => {
    if (!file || !conversationId) {
      toast.error('Erro', { description: 'Selecione uma conversa primeiro' });
      return;
    }

    setUploading(true);
    setUploadProgress(10);
    
    try {
      // Upload file to backend
      setUploadProgress(30);
      const uploadResult = await UploadAPI.uploadFile(file.file, conversationId);
      setUploadProgress(70);
      
      // Send media message
      const messageResult = await UploadAPI.sendMediaMessage(
        conversationId,
        file.type,
        uploadResult.url,
        file.name
      );
      setUploadProgress(100);
      
      toast.success('Arquivo enviado!', { description: file.name });
      
      // Notify parent
      await onUpload?.({
        type: file.type,
        name: file.name,
        url: uploadResult.url,
        message: messageResult
      });
      
      setFile(null);
      setPreview(null);
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Erro ao enviar arquivo', { 
        description: error.response?.data?.detail || error.message 
      });
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleCancel = () => {
    setFile(null);
    setPreview(null);
    onCancel?.();
  };

  if (file) {
    return (
      <div className="p-4 backdrop-blur-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/20 rounded-2xl">
        <div className="flex items-start gap-4">
          {/* Preview */}
          <div className="w-20 h-20 rounded-xl bg-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
            {preview ? (
              <img src={preview} alt="Preview" className="w-full h-full object-cover" />
            ) : (
              <div className="text-white/60">{getFileIcon(file.type)}</div>
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <p className="text-white font-medium truncate">{file.name}</p>
            <p className="text-white/50 text-sm capitalize">{file.type}</p>
            <p className="text-white/40 text-xs">
              {(file.file.size / 1024).toFixed(1)} KB
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              disabled={uploading}
              className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-colors disabled:opacity-50"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {uploading && (
          <div className="mt-3 w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-emerald-500 to-green-400 transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        )}

        {/* Send button */}
        <div className="mt-4 flex justify-end">
          <GlassButton
            onClick={handleUpload}
            disabled={uploading || disabled}
            className="flex items-center gap-2"
          >
            {uploading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Enviando ({uploadProgress}%)...</>
            ) : (
              <><Upload className="w-4 h-4" /> Enviar Arquivo</>
            )}
          </GlassButton>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'p-6 border-2 border-dashed rounded-2xl transition-all cursor-pointer',
        dragOver
          ? 'border-emerald-500 bg-emerald-500/10'
          : 'border-white/20 hover:border-white/40 bg-white/5'
      )}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
        onChange={(e) => handleFileSelect(e.target.files[0])}
        className="hidden"
      />

      <div className="text-center">
        <Upload className="w-10 h-10 text-white/40 mx-auto mb-3" />
        <p className="text-white font-medium mb-1">Arraste um arquivo ou clique para selecionar</p>
        <p className="text-white/50 text-sm">Imagens, vídeos, áudios ou documentos (máx. 10MB)</p>
      </div>
    </div>
  );
};

export default FileUpload;
