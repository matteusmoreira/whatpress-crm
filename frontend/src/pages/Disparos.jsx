import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Megaphone, Plus, X, Check, Send, Pause, Play, Ban, BarChart3, Users, Clock } from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { BulkCampaignsAPI, ContactsAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const KANBAN_UNASSIGNED_COLUMN_ID = '__unassigned__';
const KANBAN_CUSTOM_FIELD_KEY = 'kanban_column';

const PERIOD_UNITS = [
  { value: 'minute', label: 'Minuto' },
  { value: 'hour', label: 'Hora' },
  { value: 'day', label: 'Dia' },
  { value: 'week', label: 'Semana' },
  { value: 'month', label: 'Mês' }
];

const STATUS_STYLES = {
  draft: { label: 'Rascunho', color: 'bg-white/10 text-white/70' },
  scheduled: { label: 'Agendado', color: 'bg-blue-500/20 text-blue-300 border border-blue-500/30' },
  running: { label: 'Enviando', color: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' },
  paused: { label: 'Pausado', color: 'bg-amber-500/20 text-amber-300 border border-amber-500/30' },
  completed: { label: 'Concluído', color: 'bg-purple-500/20 text-purple-300 border border-purple-500/30' },
  cancelled: { label: 'Cancelado', color: 'bg-red-500/20 text-red-300 border border-red-500/30' },
  failed: { label: 'Falhou', color: 'bg-red-500/20 text-red-300 border border-red-500/30' }
};

const CampaignForm = ({
  isOpen,
  onClose,
  onSaved,
  tenantId,
  editingCampaign
}) => {
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [templateBody, setTemplateBody] = useState('');
  const [delaySeconds, setDelaySeconds] = useState(0);
  const [maxMessagesPerPeriod, setMaxMessagesPerPeriod] = useState('');
  const [periodUnit, setPeriodUnit] = useState('hour');

  const [contactSearch, setContactSearch] = useState('');
  const [contacts, setContacts] = useState([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());

  const [kanbanColumns, setKanbanColumns] = useState([]);
  const [selectedKanbanColumnId, setSelectedKanbanColumnId] = useState('');
  const [addingKanbanColumn, setAddingKanbanColumn] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    if (editingCampaign) {
      setName(editingCampaign.name || '');
      setTemplateBody(editingCampaign.template_body || '');
      setDelaySeconds(Number(editingCampaign.delay_seconds || 0));
      setMaxMessagesPerPeriod(
        editingCampaign.max_messages_per_period === null || editingCampaign.max_messages_per_period === undefined
          ? ''
          : String(editingCampaign.max_messages_per_period)
      );
      setPeriodUnit(editingCampaign.period_unit || 'hour');
      const payload = editingCampaign.selection_payload || {};
      const ids = payload.contact_ids || payload.contactIds || [];
      setSelectedIds(new Set((Array.isArray(ids) ? ids : []).map((x) => String(x))));
    } else {
      setName('');
      setTemplateBody('');
      setDelaySeconds(0);
      setMaxMessagesPerPeriod('');
      setPeriodUnit('hour');
      setSelectedIds(new Set());
    }
  }, [editingCampaign, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    if (!tenantId) {
      setKanbanColumns([]);
      setSelectedKanbanColumnId('');
      return;
    }
    try {
      const key = `contacts-kanban:${tenantId}`;
      const raw = window?.localStorage?.getItem(key);
      const parsed = raw ? JSON.parse(raw) : null;
      const storedColumns = Array.isArray(parsed?.columns) ? parsed.columns : [];
      const normalized = storedColumns
        .filter((c) => c && c.id && c.title)
        .map((c) => ({
          id: String(c.id),
          title: String(c.title),
          color: String(c.color || 'slate')
        }));
      const boardCols = [
        { id: KANBAN_UNASSIGNED_COLUMN_ID, title: 'Sem Coluna', color: 'slate' },
        ...normalized
      ];
      setKanbanColumns(boardCols);
      if (boardCols.length > 0) setSelectedKanbanColumnId((prev) => prev || boardCols[0].id);
    } catch {
      setKanbanColumns([{ id: KANBAN_UNASSIGNED_COLUMN_ID, title: 'Sem Coluna', color: 'slate' }]);
      setSelectedKanbanColumnId(KANBAN_UNASSIGNED_COLUMN_ID);
    }
  }, [isOpen, tenantId]);

  const loadContacts = useCallback(async () => {
    try {
      if (!tenantId) return;
      setLoadingContacts(true);
      const data = await ContactsAPI.list(tenantId, contactSearch, 50, 0);
      const list = Array.isArray(data) ? data : (data?.contacts || []);
      setContacts(Array.isArray(list) ? list : []);
    } catch (e) {
      toast.error('Erro ao carregar contatos');
    } finally {
      setLoadingContacts(false);
    }
  }, [contactSearch, tenantId]);

  const loadAllContacts = useCallback(async () => {
    if (!tenantId) return [];
    const pageLimit = 200;
    let pageOffset = 0;
    let totalCount = Infinity;
    const all = [];

    while (all.length < totalCount) {
      const data = await ContactsAPI.list(tenantId, '', pageLimit, pageOffset);
      const batch = Array.isArray(data?.contacts) ? data.contacts : (Array.isArray(data) ? data : []);
      const reportedTotal = typeof data?.total === 'number' ? data.total : null;
      if (typeof reportedTotal === 'number') totalCount = reportedTotal;

      all.push(...batch);
      if (batch.length === 0) break;
      pageOffset += pageLimit;
      if (pageOffset > 20000) break;
    }

    return all;
  }, [tenantId]);

  const addContactsFromKanbanColumn = useCallback(async () => {
    if (!tenantId) return;
    const colId = String(selectedKanbanColumnId || '').trim();
    if (!colId) return;

    setAddingKanbanColumn(true);
    try {
      const all = await loadAllContacts();
      const matched = all.filter((c) => {
        const cf = c?.customFields || c?.custom_fields || {};
        const current = String(cf?.[KANBAN_CUSTOM_FIELD_KEY] || '').trim() || KANBAN_UNASSIGNED_COLUMN_ID;
        return current === colId;
      });
      const ids = matched.map((c) => String(c?.id || '').trim()).filter(Boolean);
      if (ids.length === 0) {
        toast.error('Nenhum contato nessa coluna');
        return;
      }
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const id of ids) next.add(id);
        return next;
      });
      toast.success(`${ids.length} contato(s) adicionados`);
    } catch (e) {
      toast.error('Erro ao carregar contatos do Kanban');
    } finally {
      setAddingKanbanColumn(false);
    }
  }, [loadAllContacts, selectedKanbanColumnId, tenantId]);

  useEffect(() => {
    if (!isOpen) return;
    const t = setTimeout(() => loadContacts(), 250);
    return () => clearTimeout(t);
  }, [isOpen, loadContacts]);

  const toggleContact = (contactId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(contactId)) next.delete(contactId);
      else next.add(contactId);
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!tenantId) return;
    const trimmedName = name.trim();
    const trimmedBody = templateBody.trim();
    if (!trimmedName) {
      toast.error('Informe um nome para a campanha');
      return;
    }
    if (!trimmedBody) {
      toast.error('Informe o texto da mensagem');
      return;
    }
    if (selectedIds.size === 0) {
      toast.error('Selecione pelo menos 1 contato');
      return;
    }

    setSaving(true);
    try {
      const campaignPayload = {
        name: trimmedName,
        templateBody: trimmedBody,
        delaySeconds: Number(delaySeconds) || 0,
        maxMessagesPerPeriod: maxMessagesPerPeriod === '' ? null : Math.max(0, Number(maxMessagesPerPeriod) || 0),
        periodUnit: periodUnit || 'hour'
      };

      let saved = null;
      if (editingCampaign?.id) {
        saved = await BulkCampaignsAPI.update(editingCampaign.id, campaignPayload);
      } else {
        saved = await BulkCampaignsAPI.create(tenantId, campaignPayload);
      }

      await BulkCampaignsAPI.setRecipients(tenantId, saved.id, Array.from(selectedIds));
      toast.success(editingCampaign ? 'Campanha atualizada' : 'Campanha criada');
      onSaved?.();
      onClose?.();
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || null;
      toast.error('Erro ao salvar campanha', msg ? { description: String(msg) } : undefined);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const selectedCount = selectedIds.size;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-3xl bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Megaphone className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">
              {editingCampaign ? 'Editar Disparo' : 'Novo Disparo'}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4 max-h-[75vh] overflow-y-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div>
                <label className="text-white/70 text-sm mb-2 block">Nome</label>
                <GlassInput value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: Promoção Janeiro" />
              </div>

              <div>
                <label className="text-white/70 text-sm mb-2 block">Mensagem (template)</label>
                <textarea
                  value={templateBody}
                  onChange={(e) => setTemplateBody(e.target.value)}
                  placeholder="Ex: Olá {nome}, temos uma oferta para você!"
                  className={cn(
                    "w-full min-h-[130px] p-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white placeholder-white/40",
                    "focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                  )}
                />
                <div className="text-xs text-white/40 mt-2">
                  Variáveis: {'{nome}'} {'{telefone}'} {'{email}'}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-white/70 text-sm mb-2 block">Delay (seg)</label>
                  <GlassInput
                    type="number"
                    min="0"
                    value={delaySeconds}
                    onChange={(e) => setDelaySeconds(e.target.value)}
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="text-white/70 text-sm mb-2 block">Limite</label>
                  <GlassInput
                    type="number"
                    min="0"
                    value={maxMessagesPerPeriod}
                    onChange={(e) => setMaxMessagesPerPeriod(e.target.value)}
                    placeholder="0 = sem limite"
                  />
                </div>
                <div>
                  <label className="text-white/70 text-sm mb-2 block">Período</label>
                  <select
                    value={periodUnit}
                    onChange={(e) => setPeriodUnit(e.target.value)}
                    className="h-11 w-full px-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                  >
                    {PERIOD_UNITS.map((u) => (
                      <option key={u.value} value={u.value} className="bg-emerald-900">
                        {u.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-white/70 text-sm">Destinatários</div>
                <GlassBadge className="bg-white/10 text-white/80 border border-white/10">
                  {selectedCount} selecionado{selectedCount === 1 ? '' : 's'}
                </GlassBadge>
              </div>

              <div className="relative">
                <Users className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <GlassInput
                  value={contactSearch}
                  onChange={(e) => setContactSearch(e.target.value)}
                  placeholder="Buscar contatos..."
                  className="pl-11"
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-2">
                <select
                  value={selectedKanbanColumnId}
                  onChange={(e) => setSelectedKanbanColumnId(e.target.value)}
                  className="h-11 w-full px-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                  disabled={addingKanbanColumn || kanbanColumns.length === 0}
                >
                  {kanbanColumns.length === 0 ? (
                    <option value="" className="bg-emerald-900">Kanban não configurado</option>
                  ) : (
                    kanbanColumns.map((c) => (
                      <option key={c.id} value={c.id} className="bg-emerald-900">
                        {c.title}
                      </option>
                    ))
                  )}
                </select>
                <GlassButton
                  type="button"
                  onClick={addContactsFromKanbanColumn}
                  disabled={addingKanbanColumn || kanbanColumns.length === 0 || !selectedKanbanColumnId}
                  className="min-w-[190px]"
                >
                  {addingKanbanColumn ? 'Adicionando...' : 'Adicionar da coluna'}
                </GlassButton>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/5 overflow-hidden">
                {loadingContacts ? (
                  <div className="flex items-center justify-center py-10">
                    <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : contacts.length === 0 ? (
                  <div className="text-center py-10 text-white/40">
                    Nenhum contato encontrado
                  </div>
                ) : (
                  <div className="max-h-[320px] overflow-y-auto">
                    {contacts.map((c) => {
                      const id = String(c.id);
                      const checked = selectedIds.has(id);
                      const displayName = c.name || c.full_name || c.fullName || c.phone || '';
                      const phone = c.phone || '';
                      return (
                        <button
                          key={id}
                          type="button"
                          onClick={() => toggleContact(id)}
                          className={cn(
                            "w-full flex items-center justify-between px-4 py-3 text-left border-b border-white/5 hover:bg-white/5 transition-colors",
                            checked && "bg-emerald-500/10"
                          )}
                        >
                          <div className="min-w-0">
                            <div className="text-white font-medium truncate">{displayName}</div>
                            <div className="text-white/40 text-xs truncate">{phone}</div>
                          </div>
                          <div className={cn(
                            "w-6 h-6 rounded-lg border flex items-center justify-center",
                            checked ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "border-white/15 text-white/30"
                          )}>
                            {checked ? <Check className="w-4 h-4" /> : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="h-11 px-5 rounded-xl bg-white/5 hover:bg-white/10 text-white/70 transition-colors"
            >
              Cancelar
            </button>
            <GlassButton type="submit" disabled={saving} className="min-w-[160px]">
              <Send className="w-4 h-4 mr-2" />
              {saving ? 'Salvando...' : editingCampaign ? 'Atualizar' : 'Criar'}
            </GlassButton>
          </div>
        </form>
      </div>
    </div>
  );
};

const StatsModal = ({ isOpen, onClose, stats }) => {
  if (!isOpen) return null;
  const totals = stats?.totals || {};
  const campaign = stats?.campaign || {};
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">
              Progresso
            </h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="text-white font-semibold">{campaign.name || 'Campanha'}</div>
          <div className="grid grid-cols-2 gap-3">
            <GlassCard className="p-4">
              <div className="text-white/50 text-sm">Agendados</div>
              <div className="text-2xl font-bold text-white">{totals.scheduled || 0}</div>
            </GlassCard>
            <GlassCard className="p-4">
              <div className="text-white/50 text-sm">Enviando</div>
              <div className="text-2xl font-bold text-white">{totals.sending || 0}</div>
            </GlassCard>
            <GlassCard className="p-4">
              <div className="text-white/50 text-sm">Enviados</div>
              <div className="text-2xl font-bold text-white">{totals.sent || 0}</div>
            </GlassCard>
            <GlassCard className="p-4">
              <div className="text-white/50 text-sm">Falharam</div>
              <div className="text-2xl font-bold text-white">{totals.failed || 0}</div>
            </GlassCard>
          </div>

          <div className="flex justify-end">
            <GlassButton onClick={onClose}>Fechar</GlassButton>
          </div>
        </div>
      </div>
    </div>
  );
};

const Disparos = () => {
  const { user } = useAuthStore();
  const { selectedTenant, tenants, fetchTenants } = useAppStore();

  const [loading, setLoading] = useState(true);
  const [campaigns, setCampaigns] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState(null);

  const [statsOpen, setStatsOpen] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [stats, setStats] = useState(null);

  const isSuperAdmin = user?.role === 'superadmin';
  const tenantId = isSuperAdmin
    ? (selectedTenant?.id || tenants?.[0]?.id || null)
    : (user?.tenantId || null);

  useEffect(() => {
    if (!isSuperAdmin) return;
    fetchTenants?.();
  }, [fetchTenants, isSuperAdmin]);

  const loadCampaigns = useCallback(async () => {
    try {
      if (!tenantId) return;
      setLoading(true);
      const data = await BulkCampaignsAPI.list(tenantId);
      setCampaigns(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error('Erro ao carregar disparos');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const openCreate = () => {
    setEditingCampaign(null);
    setShowForm(true);
  };

  const openEdit = (campaign) => {
    setEditingCampaign(campaign);
    setShowForm(true);
  };

  const scheduleNow = async (campaign) => {
    if (!tenantId) return;
    if (!window.confirm('Agendar envio agora?')) return;
    try {
      await BulkCampaignsAPI.schedule(tenantId, campaign.id, {
        startAt: new Date().toISOString(),
        recurrence: campaign.recurrence || 'none',
        delaySeconds: campaign.delay_seconds || 0,
        maxMessagesPerPeriod: campaign.max_messages_per_period,
        periodUnit: campaign.period_unit
      });
      toast.success('Disparo agendado');
      loadCampaigns();
    } catch (e) {
      toast.error('Erro ao agendar disparo');
    }
  };

  const pause = async (campaign) => {
    if (!tenantId) return;
    try {
      await BulkCampaignsAPI.pause(tenantId, campaign.id);
      toast.success('Disparo pausado');
      loadCampaigns();
    } catch (e) {
      toast.error('Erro ao pausar');
    }
  };

  const resume = async (campaign) => {
    if (!tenantId) return;
    try {
      await BulkCampaignsAPI.resume(tenantId, campaign.id);
      toast.success('Disparo retomado');
      loadCampaigns();
    } catch (e) {
      toast.error('Erro ao retomar');
    }
  };

  const cancel = async (campaign) => {
    if (!tenantId) return;
    if (!window.confirm('Cancelar esta campanha?')) return;
    try {
      await BulkCampaignsAPI.cancel(tenantId, campaign.id);
      toast.success('Disparo cancelado');
      loadCampaigns();
    } catch (e) {
      toast.error('Erro ao cancelar');
    }
  };

  const remove = async (campaign) => {
    if (!window.confirm('Excluir esta campanha?')) return;
    try {
      await BulkCampaignsAPI.delete(campaign.id);
      toast.success('Campanha excluída');
      loadCampaigns();
    } catch (e) {
      toast.error('Erro ao excluir');
    }
  };

  const openStats = async (campaign) => {
    if (!tenantId) return;
    setStatsOpen(true);
    setStatsLoading(true);
    setStats(null);
    try {
      const data = await BulkCampaignsAPI.stats(tenantId, campaign.id);
      setStats(data);
    } catch (e) {
      toast.error('Erro ao carregar progresso');
      setStatsOpen(false);
    } finally {
      setStatsLoading(false);
    }
  };

  const emptyState = useMemo(() => {
    if (loading) return null;
    if (campaigns.length > 0) return null;
    return (
      <GlassCard className="p-12 text-center">
        <Megaphone className="w-16 h-16 text-white/20 mx-auto mb-4" />
        <h3 className="text-xl font-medium text-white mb-2">Nenhum disparo criado</h3>
        <p className="text-white/50 mb-6">
          Crie campanhas para enviar mensagens em massa para seus contatos.
        </p>
        <GlassButton onClick={openCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Criar primeiro disparo
        </GlassButton>
      </GlassCard>
    );
  }, [campaigns.length, loading]);

  return (
    <div className="p-4 sm:p-5 lg:p-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between mb-6 pl-16 lg:pl-0">
        <div>
          <h1 className="wa-page-title flex items-center gap-2">
            <Megaphone className="w-8 h-8 text-emerald-400" />
            Disparos
          </h1>
          <p className="wa-page-subtitle">Envie mensagens em massa com agendamento e controle</p>
        </div>
        <GlassButton onClick={openCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Novo Disparo
        </GlassButton>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : emptyState ? (
        emptyState
      ) : (
        <div className="space-y-4">
          {campaigns.map((c) => {
            const statusKey = String(c.status || 'draft').toLowerCase();
            const st = STATUS_STYLES[statusKey] || STATUS_STYLES.draft;
            const isSchedulable = ['draft', 'paused', 'completed', 'cancelled', 'failed'].includes(statusKey);
            const isRunning = statusKey === 'running' || statusKey === 'scheduled';
            return (
              <GlassCard key={c.id} className="p-5">
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-3">
                      <div className="text-white font-semibold text-lg truncate">{c.name}</div>
                      <GlassBadge className={cn("px-3 py-1 rounded-full text-xs", st.color)}>
                        {st.label}
                      </GlassBadge>
                    </div>
                    <div className="text-white/50 text-sm mt-2 whitespace-pre-wrap break-words">
                      {(c.template_body || '').slice(0, 220)}{(c.template_body || '').length > 220 ? '...' : ''}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 mt-4 text-white/50 text-sm">
                      <div className="inline-flex items-center gap-2">
                        <Clock className="w-4 h-4 text-emerald-400" />
                        <span>Delay: {Number(c.delay_seconds || 0)}s</span>
                      </div>
                      <div className="inline-flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-emerald-400" />
                        <span>
                          Limite: {c.max_messages_per_period ? `${c.max_messages_per_period}/${c.period_unit || 'hora'}` : 'sem limite'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 justify-end">
                    <GlassButton
                      variant="secondary"
                      onClick={() => openStats(c)}
                      className="h-10"
                    >
                      <BarChart3 className="w-4 h-4 mr-2" />
                      Progresso
                    </GlassButton>
                    <GlassButton variant="secondary" onClick={() => openEdit(c)} className="h-10">
                      Editar
                    </GlassButton>
                    {isSchedulable ? (
                      <GlassButton onClick={() => scheduleNow(c)} className="h-10">
                        <Send className="w-4 h-4 mr-2" />
                        Agendar agora
                      </GlassButton>
                    ) : null}
                    {statusKey === 'paused' ? (
                      <GlassButton variant="secondary" onClick={() => resume(c)} className="h-10">
                        <Play className="w-4 h-4 mr-2" />
                        Retomar
                      </GlassButton>
                    ) : null}
                    {isRunning ? (
                      <GlassButton variant="secondary" onClick={() => pause(c)} className="h-10">
                        <Pause className="w-4 h-4 mr-2" />
                        Pausar
                      </GlassButton>
                    ) : null}
                    {statusKey !== 'cancelled' ? (
                      <GlassButton variant="secondary" onClick={() => cancel(c)} className="h-10">
                        <Ban className="w-4 h-4 mr-2" />
                        Cancelar
                      </GlassButton>
                    ) : null}
                    <GlassButton variant="danger" onClick={() => remove(c)} className="h-10">
                      Excluir
                    </GlassButton>
                  </div>
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}

      <CampaignForm
        isOpen={showForm}
        onClose={() => {
          setShowForm(false);
          setEditingCampaign(null);
        }}
        onSaved={loadCampaigns}
        tenantId={tenantId}
        editingCampaign={editingCampaign}
      />

      <StatsModal
        isOpen={statsOpen}
        onClose={() => setStatsOpen(false)}
        stats={statsLoading ? { campaign: stats?.campaign || {}, totals: { scheduled: 0, sending: 0, sent: 0, failed: 0 } } : stats}
      />
    </div>
  );
};

export default Disparos;
