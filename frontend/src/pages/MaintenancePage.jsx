import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Bold, Italic, Underline, Link as LinkIcon, List, Save, Upload, Trash2, Power, PowerOff } from 'lucide-react';
import { GlassBadge, GlassButton, GlassCard } from '../components/GlassCard';
import { MaintenanceAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const getMaintenanceKey = (m) => {
  if (!m || !m.enabled) return null;
  const k = String(m.updatedAt || '').trim();
  return k || 'enabled';
};

const MaintenancePage = () => {
  const editorRef = useRef(null);
  const fileInputRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const [maintenance, setMaintenance] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [messageHtml, setMessageHtml] = useState('');
  const [attachments, setAttachments] = useState([]);

  const maintenanceKey = useMemo(() => getMaintenanceKey(maintenance), [maintenance]);

  const syncEditorFromState = useCallback((html) => {
    const el = editorRef.current;
    if (!el) return;
    const next = String(html || '');
    if (el.innerHTML !== next) el.innerHTML = next;
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await MaintenanceAPI.get();
      setMaintenance(data);
      setEnabled(!!data?.enabled);
      setMessageHtml(String(data?.messageHtml || ''));
      setAttachments(Array.isArray(data?.attachments) ? data.attachments : []);
      syncEditorFromState(data?.messageHtml || '');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erro ao carregar manutenção');
    } finally {
      setLoading(false);
    }
  }, [syncEditorFromState]);

  useEffect(() => {
    load();
  }, [load]);

  const exec = (command, value = null) => {
    const el = editorRef.current;
    if (!el) return;
    el.focus();
    document.execCommand(command, false, value);
    setMessageHtml(el.innerHTML);
  };

  const handlePromptLink = () => {
    const url = window.prompt('Cole a URL:');
    if (!url) return;
    exec('createLink', url);
  };

  const handleToggle = async () => {
    const next = !enabled;
    setEnabled(next);
    try {
      const data = await MaintenanceAPI.update({ enabled: next });
      setMaintenance(data);
      toast.success(next ? 'Modo manutenção ativado' : 'Modo manutenção desativado');
    } catch (e) {
      setEnabled(!next);
      toast.error(e?.response?.data?.detail || 'Erro ao atualizar manutenção');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const data = await MaintenanceAPI.update({
        enabled,
        messageHtml,
        attachments
      });
      setMaintenance(data);
      setEnabled(!!data?.enabled);
      setMessageHtml(String(data?.messageHtml || ''));
      setAttachments(Array.isArray(data?.attachments) ? data.attachments : []);
      syncEditorFromState(data?.messageHtml || '');
      toast.success('Configuração de manutenção salva');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erro ao salvar manutenção');
    } finally {
      setSaving(false);
    }
  };

  const handlePickFile = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const uploaded = await MaintenanceAPI.uploadAttachment(file);
      const next = [...attachments, uploaded].filter(Boolean);
      setAttachments(next);
      const data = await MaintenanceAPI.update({ attachments: next });
      setMaintenance(data);
      setAttachments(Array.isArray(data?.attachments) ? data.attachments : next);
      toast.success('Anexo enviado');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erro ao enviar anexo');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = async (url) => {
    const next = attachments.filter(a => a?.url !== url);
    setAttachments(next);
    try {
      const data = await MaintenanceAPI.update({ attachments: next });
      setMaintenance(data);
      setAttachments(Array.isArray(data?.attachments) ? data.attachments : next);
      toast.success('Anexo removido');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Erro ao remover anexo');
    }
  };

  return (
    <div className="min-h-screen p-6 lg:p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-2">
          <AlertTriangle className="w-8 h-8 text-amber-400" />
          Modo Manutenção
        </h1>
        <p className="text-white/60">Ative um aviso global exibido no login</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="lg:col-span-1" hover={false}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Status</h2>
              <p className="text-white/60 text-sm mt-1">Controla o aviso para todos os usuários</p>
            </div>
            <GlassBadge variant={enabled ? 'warning' : 'success'}>
              {enabled ? 'Ativo' : 'Desativado'}
            </GlassBadge>
          </div>

          <div className="mt-6 flex gap-3">
            <GlassButton
              onClick={handleToggle}
              variant={enabled ? 'danger' : 'primary'}
              className="flex items-center gap-2"
              disabled={loading || saving}
            >
              {enabled ? <PowerOff className="w-4 h-4" /> : <Power className="w-4 h-4" />}
              {enabled ? 'Desativar' : 'Ativar'}
            </GlassButton>
            <GlassButton
              onClick={handleSave}
              variant="secondary"
              className="flex items-center gap-2"
              disabled={loading || saving}
              loading={saving}
            >
              <Save className="w-4 h-4" />
              Salvar
            </GlassButton>
          </div>

          <div className="mt-6 text-white/60 text-sm space-y-1">
            <div>Atualizado em: {maintenance?.updatedAt ? String(maintenance.updatedAt) : '—'}</div>
            <div>Chave: {maintenanceKey || '—'}</div>
          </div>
        </GlassCard>

        <GlassCard className="lg:col-span-2" hover={false}>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Mensagem</h2>
              <p className="text-white/60 text-sm mt-1">Editor rico com HTML simples</p>
            </div>
            <div className="flex items-center gap-2">
              <GlassButton type="button" variant="secondary" className="px-3 py-2" onClick={() => exec('bold')}>
                <Bold className="w-4 h-4" />
              </GlassButton>
              <GlassButton type="button" variant="secondary" className="px-3 py-2" onClick={() => exec('italic')}>
                <Italic className="w-4 h-4" />
              </GlassButton>
              <GlassButton type="button" variant="secondary" className="px-3 py-2" onClick={() => exec('underline')}>
                <Underline className="w-4 h-4" />
              </GlassButton>
              <GlassButton type="button" variant="secondary" className="px-3 py-2" onClick={handlePromptLink}>
                <LinkIcon className="w-4 h-4" />
              </GlassButton>
              <GlassButton type="button" variant="secondary" className="px-3 py-2" onClick={() => exec('insertUnorderedList')}>
                <List className="w-4 h-4" />
              </GlassButton>
            </div>
          </div>

          <div
            ref={editorRef}
            contentEditable
            suppressContentEditableWarning
            onInput={(e) => setMessageHtml(e.currentTarget.innerHTML)}
            className={cn(
              "min-h-[220px] w-full rounded-2xl px-4 py-3 outline-none transition-all",
              "bg-white/10 border border-white/20 text-white",
              "focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50"
            )}
          />

          <div className="mt-6 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-white font-semibold">Anexos</h3>
              <p className="text-white/60 text-sm">Opcional: links exibidos no aviso</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files?.[0] || null)}
              />
              <GlassButton
                type="button"
                variant="secondary"
                onClick={handlePickFile}
                className="flex items-center gap-2"
                disabled={uploading}
                loading={uploading}
              >
                <Upload className="w-4 h-4" />
                Enviar anexo
              </GlassButton>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {attachments.length === 0 ? (
              <div className="text-white/50 text-sm">Nenhum anexo</div>
            ) : (
              attachments.map((a) => (
                <div
                  key={a.url}
                  className="flex items-center justify-between gap-3 px-4 py-3 rounded-2xl bg-white/5 border border-white/10"
                >
                  <div className="min-w-0">
                    <div className="text-white font-medium truncate">{a.name || a.url}</div>
                    <div className="text-white/50 text-xs truncate">{a.type || 'arquivo'} {typeof a.size === 'number' ? `• ${a.size} bytes` : ''}</div>
                    <a href={a.url} target="_blank" rel="noreferrer" className="text-emerald-300 text-xs underline break-all">
                      {a.url}
                    </a>
                  </div>
                  <GlassButton
                    type="button"
                    variant="ghost"
                    className="px-3 py-2"
                    onClick={() => handleRemoveAttachment(a.url)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </GlassButton>
                </div>
              ))
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

export default MaintenancePage;

