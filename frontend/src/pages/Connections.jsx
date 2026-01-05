import React, { useEffect, useState } from 'react';
import {
  Plug,
  Plus,
  Wifi,
  WifiOff,
  Loader2,
  Copy,
  Trash2,
  CheckCircle,
  XCircle,
  RefreshCw,
  X,
  QrCode,
  Smartphone,
  Globe
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { useAuthStore } from '../store/authStore';
import { EvolutionAPI, ConnectionsAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const ConnectionCard = ({ connection, onTest, onToggle, onDelete, onShowQR, onSync }) => {
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(connection.id);
      if (result.qrcode) {
        // Show QR Code modal
        onShowQR(result.qrcode, result.pairingCode);
        setTestResult({ success: true, message: 'Escaneie o QR Code para conectar' });
      } else {
        setTestResult({ success: true, message: result.message });
        setTimeout(() => onToggle(connection.id, 'connected'), 500);
      }
    } catch (error) {
      setTestResult({ success: false, message: error.response?.data?.detail || error.message });
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    await onToggle(connection.id, 'disconnected');
    toast.success('Desconectado');
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copiado!');
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await onSync(connection.id);
      toast.success(result.message || 'Status sincronizado!');
      // Recarregar a lista de conexões é feito pelo componente pai
    } catch (error) {
      toast.error('Erro ao sincronizar', { description: error.response?.data?.detail || error.message });
    } finally {
      setSyncing(false);
    }
  };

  const getProviderInfo = (provider) => {
    switch (provider) {
      case 'evolution':
        return {
          name: 'Evolution API',
          color: 'from-green-500/30 to-emerald-600/30',
          icon: <Globe className="w-4 h-4" />
        };
      case 'wuzapi':
        return {
          name: 'Wuzapi',
          color: 'from-blue-500/30 to-cyan-600/30',
          icon: <Smartphone className="w-4 h-4" />
        };
      case 'pastorini':
        return {
          name: 'Pastorini',
          color: 'from-purple-500/30 to-violet-600/30',
          icon: <Plug className="w-4 h-4" />
        };
      default:
        return {
          name: provider,
          color: 'from-gray-500/30 to-slate-600/30',
          icon: <Plug className="w-4 h-4" />
        };
    }
  };

  const providerInfo = getProviderInfo(connection.provider);

  return (
    <GlassCard
      className={cn(
        'relative overflow-hidden',
        connection.status === 'connected' && 'ring-2 ring-emerald-500/30'
      )}
    >
      {/* Status indicator */}
      <div className="absolute top-4 right-4">
        {connection.status === 'connected' ? (
          <div className="flex items-center gap-2 text-emerald-400">
            <Wifi className="w-5 h-5" />
            <span className="text-sm font-medium">Conectado</span>
          </div>
        ) : connection.status === 'connecting' ? (
          <div className="flex items-center gap-2 text-amber-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm font-medium">Conectando...</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-red-400">
            <WifiOff className="w-5 h-5" />
            <span className="text-sm font-medium">Desconectado</span>
          </div>
        )}
      </div>

      {/* Provider badge */}
      <div className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-xl mb-4',
        'bg-gradient-to-r',
        providerInfo.color
      )}>
        {providerInfo.icon}
        <span className="text-white font-medium">{providerInfo.name}</span>
      </div>

      {/* Info */}
      <div className="space-y-3 mb-6">
        <div>
          <label className="text-white/50 text-sm">Instance Name</label>
          <p className="text-white font-medium">{connection.instanceName}</p>
        </div>
        <div>
          <label className="text-white/50 text-sm">Número</label>
          <p className="text-white font-medium">{connection.phoneNumber}</p>
        </div>
        {connection.webhookUrl && (
          <div>
            <label className="text-white/50 text-sm">Webhook URL</label>
            <div className="flex items-center gap-2">
              <p className="text-white/80 text-sm truncate flex-1">{connection.webhookUrl}</p>
              <button
                onClick={() => copyToClipboard(connection.webhookUrl)}
                className="p-1.5 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Test result */}
      {testResult && (
        <div className={cn(
          'p-3 rounded-xl mb-4 flex items-center gap-2',
          testResult.success ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'
        )}>
          {testResult.success ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          <span className="text-sm">{testResult.message}</span>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {connection.status === 'connected' ? (
          <GlassButton
            variant="secondary"
            onClick={handleDisconnect}
            className="flex-1 flex items-center justify-center gap-2"
          >
            <WifiOff className="w-4 h-4" />
            Desconectar
          </GlassButton>
        ) : (
          <GlassButton
            onClick={handleTest}
            loading={testing}
            className="flex-1 flex items-center justify-center gap-2"
          >
            {connection.provider === 'evolution' ? (
              <>
                <QrCode className="w-4 h-4" />
                Conectar
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Testar
              </>
            )}
          </GlassButton>
        )}
        {/* Botão de Sincronização para Evolution API */}
        {connection.provider === 'evolution' && (
          <button
            onClick={handleSync}
            disabled={syncing}
            className="p-3 rounded-xl bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 transition-colors disabled:opacity-50"
            title="Sincronizar status com Evolution API"
          >
            <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
          </button>
        )}
        <button
          onClick={() => onDelete(connection.id)}
          className="p-3 rounded-xl bg-red-500/20 hover:bg-red-500/30 text-red-400 transition-colors"
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>
    </GlassCard>
  );
};

// QR Code Modal Component
const QRCodeModal = ({ qrcode, pairingCode, onClose }) => {
  if (!qrcode) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <GlassCard className="w-full max-w-md text-center" hover={false}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">Conectar WhatsApp</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="bg-white p-4 rounded-2xl mb-6">
          <img
            src={qrcode.startsWith('data:') ? qrcode : `data:image/png;base64,${qrcode}`}
            alt="QR Code"
            className="w-full h-auto"
          />
        </div>

        {pairingCode && (
          <div className="mb-6">
            <p className="text-white/60 text-sm mb-2">Ou use o código de pareamento:</p>
            <p className="text-2xl font-mono font-bold text-emerald-400 tracking-wider">
              {pairingCode}
            </p>
          </div>
        )}

        <div className="text-white/60 text-sm space-y-2">
          <p>1. Abra o WhatsApp no seu celular</p>
          <p>2. Toque em <strong>Configurações</strong> → <strong>Dispositivos conectados</strong></p>
          <p>3. Toque em <strong>Conectar dispositivo</strong></p>
          <p>4. Escaneie o QR Code acima</p>
        </div>

        <GlassButton onClick={onClose} variant="secondary" className="w-full mt-6">
          Fechar
        </GlassButton>
      </GlassCard>
    </div>
  );
};

// Evolution Instances Component
const EvolutionInstances = ({ tenantId }) => {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInstances();
  }, [tenantId]);

  const loadInstances = async () => {
    try {
      const data = await EvolutionAPI.listInstances(tenantId);
      setInstances(data);
    } catch (error) {
      console.error('Error loading Evolution instances:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
      </div>
    );
  }

  const connectedInstances = instances.filter(i => i.status === 'open');

  return (
    <GlassCard className="p-6 mb-8" hover={false}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Globe className="w-5 h-5 text-emerald-400" />
          Instâncias Evolution API
        </h3>
        <GlassBadge variant="success">
          {connectedInstances.length} conectadas
        </GlassBadge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {instances.slice(0, 12).map((instance) => (
          <div
            key={instance.id}
            className={cn(
              'p-3 rounded-xl border transition-all',
              instance.status === 'open'
                ? 'bg-emerald-500/10 border-emerald-500/30'
                : 'bg-white/5 border-white/10'
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              {instance.profilePicUrl ? (
                <img
                  src={instance.profilePicUrl}
                  alt={instance.name}
                  className="w-8 h-8 rounded-full"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
                  <Smartphone className="w-4 h-4 text-white/40" />
                </div>
              )}
              <div className={cn(
                'w-2 h-2 rounded-full',
                instance.status === 'open' ? 'bg-emerald-500' : 'bg-red-500'
              )} />
            </div>
            <p className="text-white text-sm font-medium truncate">{instance.name}</p>
            <p className="text-white/40 text-xs truncate">{instance.profileName || 'Sem nome'}</p>
          </div>
        ))}
      </div>

      {instances.length > 12 && (
        <p className="text-white/40 text-sm mt-4 text-center">
          +{instances.length - 12} outras instâncias
        </p>
      )}
    </GlassCard>
  );
};

const Connections = () => {
  const { user } = useAuthStore();
  const {
    connections,
    connectionsLoading,
    fetchConnections,
    createConnection,
    testConnection,
    updateConnectionStatus,
    deleteConnection,
    syncConnection
  } = useAppStore();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [qrCodeData, setQrCodeData] = useState({ qrcode: null, pairingCode: null });
  const [newConnection, setNewConnection] = useState({
    provider: 'evolution',
    instanceName: '',
    phoneNumber: ''
  });

  const tenantId = user?.tenantId || 'tenant-1';

  useEffect(() => {
    fetchConnections(tenantId);
  }, [tenantId, fetchConnections]);

  const handleCreateConnection = async (e) => {
    e.preventDefault();
    try {
      await createConnection({
        tenantId,
        ...newConnection
      });
      setShowCreateModal(false);
      setNewConnection({ provider: 'evolution', instanceName: '', phoneNumber: '' });
      toast.success('Conexão criada!', { description: 'Configure-a para começar a receber mensagens.' });
    } catch (error) {
      toast.error('Erro ao criar conexão', { description: error.message });
    }
  };

  const handleDeleteConnection = async (id) => {
    if (window.confirm('Tem certeza que deseja excluir esta conexão?')) {
      await deleteConnection(id);
      toast.success('Conexão removida');
    }
  };

  const handleShowQR = (qrcode, pairingCode) => {
    setQrCodeData({ qrcode, pairingCode });
    setShowQRModal(true);
  };

  const providers = [
    { id: 'evolution', name: 'Evolution API', description: 'API oficial para WhatsApp' },
    { id: 'wuzapi', name: 'Wuzapi', description: 'Solução alternativa' },
    { id: 'pastorini', name: 'Pastorini', description: 'Gateway brasileiro' }
  ];

  return (
    <div className="min-h-screen p-6 lg:p-8 overflow-auto">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Conexões WhatsApp</h1>
          <p className="text-white/60">Gerencie suas conexões com diferentes provedores</p>
        </div>
        <GlassButton onClick={() => setShowCreateModal(true)} className="flex items-center gap-2">
          <Plus className="w-5 h-5" />
          Nova Conexão
        </GlassButton>
      </div>

      {/* Note: EvolutionInstances foi removido para melhorar performance */}
      {/* Os dados das conexões já mostram todas as informações necessárias */}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <GlassCard className="p-5">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-emerald-500/30">
              <Wifi className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <p className="text-white/60 text-sm">Conectadas</p>
              <p className="text-2xl font-bold text-white">
                {connections.filter(c => c.status === 'connected').length}
              </p>
            </div>
          </div>
        </GlassCard>
        <GlassCard className="p-5">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-red-500/30">
              <WifiOff className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <p className="text-white/60 text-sm">Desconectadas</p>
              <p className="text-2xl font-bold text-white">
                {connections.filter(c => c.status === 'disconnected').length}
              </p>
            </div>
          </div>
        </GlassCard>
        <GlassCard className="p-5">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-500/30">
              <Plug className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-white/60 text-sm">Total</p>
              <p className="text-2xl font-bold text-white">{connections.length}</p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Connections Grid */}
      {connectionsLoading ? (
        <div className="flex items-center justify-center p-12">
          <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
        </div>
      ) : connections.length === 0 ? (
        <GlassCard className="p-12 text-center" hover={false}>
          <div className="w-20 h-20 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-4">
            <Plug className="w-10 h-10 text-white/40" />
          </div>
          <h3 className="text-xl font-medium text-white mb-2">Nenhuma conexão configurada</h3>
          <p className="text-white/60 mb-6">Configure sua primeira conexão para começar a receber mensagens</p>
          <GlassButton onClick={() => setShowCreateModal(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Adicionar Conexão
          </GlassButton>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {connections.map((connection) => (
            <ConnectionCard
              key={connection.id}
              connection={connection}
              onTest={testConnection}
              onToggle={updateConnectionStatus}
              onDelete={handleDeleteConnection}
              onShowQR={handleShowQR}
              onSync={syncConnection}
            />
          ))}
        </div>
      )}

      {/* QR Code Modal */}
      {showQRModal && (
        <QRCodeModal
          qrcode={qrCodeData.qrcode}
          pairingCode={qrCodeData.pairingCode}
          onClose={() => setShowQRModal(false)}
        />
      )}

      {/* Create Connection Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <GlassCard className="w-full max-w-lg" hover={false}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white">Nova Conexão</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateConnection} className="space-y-6">
              {/* Provider Selection */}
              <div>
                <label className="text-white/80 text-sm font-medium block mb-3">Provedor</label>
                <div className="grid grid-cols-3 gap-3">
                  {providers.map((provider) => (
                    <button
                      key={provider.id}
                      type="button"
                      onClick={() => setNewConnection(prev => ({ ...prev, provider: provider.id }))}
                      className={cn(
                        'p-4 rounded-xl text-center transition-all border',
                        newConnection.provider === provider.id
                          ? 'bg-emerald-500/30 border-emerald-500 text-white'
                          : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10'
                      )}
                    >
                      <p className="font-medium text-sm">{provider.name}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Instance Name */}
              <div>
                <label className="text-white/80 text-sm font-medium block mb-2">Nome da Instância</label>
                <GlassInput
                  type="text"
                  placeholder="Ex: principal-whatsapp"
                  value={newConnection.instanceName}
                  onChange={(e) => setNewConnection(prev => ({ ...prev, instanceName: e.target.value }))}
                  required
                />
              </div>

              {/* Phone Number - Opcional para Evolution API */}
              <div>
                <label className="text-white/80 text-sm font-medium block mb-2">
                  Número WhatsApp <span className="text-white/40">(opcional para Evolution API)</span>
                </label>
                <GlassInput
                  type="tel"
                  placeholder="+55 21 99999-8888"
                  value={newConnection.phoneNumber}
                  onChange={(e) => setNewConnection(prev => ({ ...prev, phoneNumber: e.target.value }))}
                />
                {newConnection.provider === 'evolution' && (
                  <p className="text-white/40 text-xs mt-1">
                    O número será associado automaticamente após escanear o QR Code
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-4">
                <GlassButton
                  type="button"
                  variant="secondary"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1"
                >
                  Cancelar
                </GlassButton>
                <GlassButton type="submit" className="flex-1">
                  Criar Conexão
                </GlassButton>
              </div>
            </form>
          </GlassCard>
        </div>
      )}
    </div>
  );
};

export default Connections;
