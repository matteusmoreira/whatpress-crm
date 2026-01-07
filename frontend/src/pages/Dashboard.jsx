import React, { useState, useEffect, useCallback } from 'react';
import {
    MessageSquare,
    Users,
    TrendingUp,
    Clock,
    CheckCircle,
    AlertCircle,
    Activity,
    ArrowUp,
    ArrowDown,
    RefreshCw,
    Download,
    FileText
} from 'lucide-react';
import { GlassCard, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useTheme } from '../context/ThemeContext';
import { AnalyticsAPI, ReportsAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

// Simple Bar Chart Component
const BarChart = ({ data, height = 200 }) => {
    const maxValue = Math.max(...data.map(d => d.total || 0), 1);

    return (
        <div className="flex items-end gap-2 h-full" style={{ height }}>
            {data.map((item, index) => (
                <div key={index} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex flex-col gap-0.5 items-center">
                        {/* Outbound bar */}
                        <div
                            className="w-full bg-emerald-500/80 rounded-t transition-all duration-500"
                            style={{ height: `${(item.outbound / maxValue) * (height - 40)}px` }}
                            title={`Enviadas: ${item.outbound}`}
                        />
                        {/* Inbound bar */}
                        <div
                            className="w-full bg-blue-500/80 rounded-b transition-all duration-500"
                            style={{ height: `${(item.inbound / maxValue) * (height - 40)}px` }}
                            title={`Recebidas: ${item.inbound}`}
                        />
                    </div>
                    <span className="text-xs text-white/50">{item.day}</span>
                </div>
            ))}
        </div>
    );
};

// Donut Chart Component
const DonutChart = ({ data, size = 120 }) => {
    const total = data.reduce((sum, d) => sum + d.count, 0) || 1;
    const colors = ['#10B981', '#F59E0B', '#6366F1'];

    let cumulativePercent = 0;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                {data.map((item, index) => {
                    const percent = (item.count / total) * 100;
                    const dashArray = `${percent} ${100 - percent}`;
                    const dashOffset = -cumulativePercent;
                    cumulativePercent += percent;

                    return (
                        <circle
                            key={index}
                            cx="18"
                            cy="18"
                            r="15.9155"
                            fill="transparent"
                            stroke={colors[index]}
                            strokeWidth="3"
                            strokeDasharray={dashArray}
                            strokeDashoffset={dashOffset}
                            className="transition-all duration-500"
                        />
                    );
                })}
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold text-white">{total}</span>
            </div>
        </div>
    );
};

// Stat Card Component
const StatCard = ({ icon: Icon, label, value, change, changeType, color = 'emerald' }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    const darkColorClasses = {
        emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30',
        blue: 'from-blue-500/20 to-blue-600/10 border-blue-500/30',
        amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30',
        purple: 'from-purple-500/20 to-purple-600/10 border-purple-500/30'
    };

    const iconBgClasses = isDark
        ? {
            emerald: 'bg-emerald-500/20',
            blue: 'bg-blue-500/20',
            amber: 'bg-amber-500/20',
            purple: 'bg-purple-500/20'
        }
        : {
            emerald: 'bg-emerald-50',
            blue: 'bg-blue-50',
            amber: 'bg-amber-50',
            purple: 'bg-purple-50'
        };

    const iconTextClasses = isDark
        ? {
            emerald: 'text-emerald-400',
            blue: 'text-blue-400',
            amber: 'text-amber-400',
            purple: 'text-purple-400'
        }
        : {
            emerald: 'text-emerald-700',
            blue: 'text-blue-700',
            amber: 'text-amber-700',
            purple: 'text-purple-700'
        };

    return (
        <div className={cn(
            'p-6 rounded-2xl border',
            isDark
                ? cn('backdrop-blur-xl bg-gradient-to-br', darkColorClasses[color])
                : 'bg-white border-slate-200 shadow-sm'
        )}>
            <div className="flex items-start justify-between">
                <div className={cn(
                    'p-3 rounded-xl',
                    iconBgClasses[color]
                )}>
                    <Icon className={cn('w-6 h-6', iconTextClasses[color])} />
                </div>
                {change !== undefined && (
                    <div className={cn(
                        'flex items-center gap-1 text-sm',
                        changeType === 'up'
                            ? (isDark ? 'text-emerald-400' : 'text-emerald-700')
                            : (isDark ? 'text-red-400' : 'text-red-700')
                    )}>
                        {changeType === 'up' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
                        <span>{change}%</span>
                    </div>
                )}
            </div>
            <div className="mt-4">
                <p className={cn('text-3xl font-bold', isDark ? 'text-white' : 'text-slate-900')}>{value}</p>
                <p className={cn('text-sm mt-1', isDark ? 'text-white/50' : 'text-slate-600')}>{label}</p>
            </div>
        </div>
    );
};

// Agent Performance Card
const AgentCard = ({ agent }) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const statusColors = {
        online: 'bg-emerald-500',
        busy: 'bg-amber-500',
        offline: 'bg-gray-400'
    };

    return (
        <div className="flex items-center gap-4 p-4 bg-white/5 hover:bg-white/10 rounded-xl transition-colors">
            <div className="relative">
                <img
                    src={agent.avatar}
                    alt={agent.name}
                    className="w-12 h-12 rounded-full"
                />
                <span className={cn(
                    'absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-emerald-900',
                    !isDark && 'border-slate-200',
                    statusColors[agent.status] || 'bg-gray-400'
                )} />
            </div>
            <div className="flex-1">
                <p className="text-white font-medium">{agent.name}</p>
                <p className="text-white/50 text-sm">{agent.assignedConversations} conversas</p>
            </div>
            <div className="text-right">
                <p className="text-emerald-400 font-bold">{agent.resolutionRate}%</p>
                <p className="text-white/40 text-xs">Taxa de resolução</p>
            </div>
        </div>
    );
};

const Dashboard = () => {
    const { user } = useAuthStore();
    const { theme } = useTheme();
    const isDark = theme === 'dark';
    const [statsLoading, setStatsLoading] = useState(true);
    const [chartsLoading, setChartsLoading] = useState(true);
    const [agentsLoading, setAgentsLoading] = useState(true);
    const [overview, setOverview] = useState(null);
    const [messagesByDay, setMessagesByDay] = useState([]);
    const [agentPerformance, setAgentPerformance] = useState([]);
    const [conversationsByStatus, setConversationsByStatus] = useState([]);
    const [refreshing, setRefreshing] = useState(false);

    const tenantId = user?.tenantId || 'tenant-1';

    const loadData = useCallback(async () => {
        // Load stats first (fastest)
        AnalyticsAPI.getOverview(tenantId).then(data => {
            setOverview(data);
            setStatsLoading(false);
        }).catch(() => setStatsLoading(false));

        // Load charts
        Promise.all([
            AnalyticsAPI.getMessagesByDay(tenantId, 7),
            AnalyticsAPI.getConversationsByStatus(tenantId)
        ]).then(([messagesData, statusData]) => {
            setMessagesByDay(messagesData);
            setConversationsByStatus(statusData);
            setChartsLoading(false);
        }).catch(() => setChartsLoading(false));

        // Load agents (potentially slowest)
        AnalyticsAPI.getAgentPerformance(tenantId).then(data => {
            setAgentPerformance(data);
            setAgentsLoading(false);
        }).catch(() => setAgentsLoading(false));
    }, [tenantId]);

    useEffect(() => {
        loadData();

        // Refresh every 60 seconds
        const interval = setInterval(loadData, 60000);
        return () => clearInterval(interval);
    }, [loadData]);

    const handleRefresh = async () => {
        setRefreshing(true);
        setStatsLoading(true);
        setChartsLoading(true);
        setAgentsLoading(true);
        await loadData();
        setRefreshing(false);
    };

    // Skeleton Components
    const StatSkeleton = () => (
        <div className={cn(
            'p-6 rounded-2xl border animate-pulse',
            isDark
                ? 'backdrop-blur-xl bg-gradient-to-br from-white/10 to-white/5 border-white/20'
                : 'bg-white border-slate-200 shadow-sm'
        )}>
            <div className="flex items-start justify-between">
                <div className={cn('p-3 rounded-xl w-12 h-12', isDark ? 'bg-white/10' : 'bg-slate-100')} />
            </div>
            <div className="mt-4 space-y-2">
                <div className={cn('h-8 rounded w-20', isDark ? 'bg-white/10' : 'bg-slate-100')} />
                <div className={cn('h-4 rounded w-32', isDark ? 'bg-white/10' : 'bg-slate-100')} />
            </div>
        </div>
    );

    const ChartSkeleton = ({ height = 180 }) => (
        <div className="animate-pulse">
            <div className="flex items-end gap-2" style={{ height }}>
                {[...Array(7)].map((_, i) => (
                    <div
                        key={i}
                        className={cn('flex-1 rounded', isDark ? 'bg-white/10' : 'bg-slate-100')}
                        style={{ height: `${30 + Math.random() * 70}%` }}
                    />
                ))}
            </div>
        </div>
    );

    const AgentSkeleton = () => (
        <div className={cn('flex items-center gap-4 p-4 rounded-xl animate-pulse', isDark ? 'bg-white/5' : 'bg-slate-50')}>
            <div className={cn('w-12 h-12 rounded-full', isDark ? 'bg-white/10' : 'bg-slate-100')} />
            <div className="flex-1 space-y-2">
                <div className={cn('h-4 rounded w-24', isDark ? 'bg-white/10' : 'bg-slate-100')} />
                <div className={cn('h-3 rounded w-16', isDark ? 'bg-white/10' : 'bg-slate-100')} />
            </div>
            <div className="text-right space-y-2">
                <div className={cn('h-5 rounded w-12', isDark ? 'bg-white/10' : 'bg-slate-100')} />
                <div className={cn('h-3 rounded w-20', isDark ? 'bg-white/10' : 'bg-slate-100')} />
            </div>
        </div>
    );



    return (
        <div className="p-6 space-y-6 overflow-y-auto h-full">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <p className="text-white/50">Visão geral do seu WhatsApp CRM</p>
                </div>
                <div className="flex items-center gap-2">
                    {/* Export Buttons */}
                    <div className="relative group">
                        <GlassButton variant="secondary">
                            <Download className="w-4 h-4 mr-2" />
                            Exportar
                        </GlassButton>
                        <div className="absolute right-0 top-full mt-2 w-48 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                            <div className="p-2">
                                <button
                                    onClick={async () => {
                                        try {
                                            const url = ReportsAPI.getConversationsCsvUrl(tenantId);
                                            await ReportsAPI.downloadCsv(url, `conversas_${new Date().toISOString().split('T')[0]}.csv`);
                                            toast.success('Relatório exportado!');
                                        } catch (e) {
                                            toast.error('Erro ao exportar');
                                        }
                                    }}
                                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                                >
                                    <FileText className="w-4 h-4" />
                                    Conversas (CSV)
                                </button>
                                <button
                                    onClick={async () => {
                                        try {
                                            const url = ReportsAPI.getAgentsCsvUrl(tenantId);
                                            await ReportsAPI.downloadCsv(url, `agentes_${new Date().toISOString().split('T')[0]}.csv`);
                                            toast.success('Relatório exportado!');
                                        } catch (e) {
                                            toast.error('Erro ao exportar');
                                        }
                                    }}
                                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                                >
                                    <Users className="w-4 h-4" />
                                    Agentes (CSV)
                                </button>
                            </div>
                        </div>
                    </div>
                    <GlassButton onClick={handleRefresh} disabled={refreshing}>
                        <RefreshCw className={cn('w-4 h-4 mr-2', refreshing && 'animate-spin')} />
                        Atualizar
                    </GlassButton>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {statsLoading ? (
                    <>
                        <StatSkeleton />
                        <StatSkeleton />
                        <StatSkeleton />
                        <StatSkeleton />
                    </>
                ) : (
                    <>
                        <StatCard
                            icon={MessageSquare}
                            label="Mensagens Hoje"
                            value={overview?.messages?.today || 0}
                            color="emerald"
                        />
                        <StatCard
                            icon={TrendingUp}
                            label="Mensagens este Mês"
                            value={overview?.messages?.thisMonth || 0}
                            color="blue"
                        />
                        <StatCard
                            icon={Users}
                            label="Conversas Abertas"
                            value={overview?.conversations?.open || 0}
                            color="amber"
                        />
                        <StatCard
                            icon={Activity}
                            label="Agentes Online"
                            value={overview?.agents?.online || 0}
                            color="purple"
                        />
                    </>
                )}
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Messages Chart */}
                <GlassCard className="lg:col-span-2 p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-lg font-semibold text-white">Mensagens por Dia</h2>
                        <div className="flex items-center gap-4 text-sm">
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-emerald-500" />
                                <span className="text-white/60">Enviadas</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full bg-blue-500" />
                                <span className="text-white/60">Recebidas</span>
                            </div>
                        </div>
                    </div>
                    {chartsLoading ? (
                        <ChartSkeleton height={180} />
                    ) : messagesByDay.length > 0 ? (
                        <BarChart data={messagesByDay} height={180} />
                    ) : (
                        <div className="h-[180px] flex items-center justify-center text-white/40">
                            Sem dados disponíveis
                        </div>
                    )}
                </GlassCard>

                {/* Conversations Status */}
                <GlassCard className="p-6">
                    <h2 className="text-lg font-semibold text-white mb-6">Status das Conversas</h2>
                    <div className="flex flex-col items-center">
                        <DonutChart data={conversationsByStatus} size={140} />
                        <div className="mt-6 w-full space-y-2">
                            {conversationsByStatus.map((item, index) => {
                                const colors = ['text-emerald-400', 'text-amber-400', 'text-indigo-400'];
                                const bgColors = ['bg-emerald-500', 'bg-amber-500', 'bg-indigo-500'];
                                return (
                                    <div key={item.status} className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <span className={cn('w-2 h-2 rounded-full', bgColors[index])} />
                                            <span className="text-white/60 text-sm">{item.label}</span>
                                        </div>
                                        <span className={cn('font-semibold', colors[index])}>{item.count}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </GlassCard>
            </div>

            {/* Agent Performance */}
            <GlassCard className="p-6">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-white">Performance dos Agentes</h2>
                    <span className="text-white/40 text-sm">{agentsLoading ? '...' : `${agentPerformance.length} agentes`}</span>
                </div>
                {agentsLoading ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <AgentSkeleton />
                        <AgentSkeleton />
                        <AgentSkeleton />
                    </div>
                ) : agentPerformance.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {agentPerformance.map(agent => (
                            <AgentCard key={agent.id} agent={agent} />
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-8 text-white/40">
                        Nenhum agente encontrado
                    </div>
                )}
            </GlassCard>

            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <GlassCard className="p-6 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-emerald-500/20">
                        <CheckCircle className="w-8 h-8 text-emerald-400" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-white">{overview?.conversations?.resolved || 0}</p>
                        <p className="text-white/50 text-sm">Conversas Resolvidas</p>
                    </div>
                </GlassCard>

                <GlassCard className="p-6 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-amber-500/20">
                        <Clock className="w-8 h-8 text-amber-400" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-white">{overview?.conversations?.pending || 0}</p>
                        <p className="text-white/50 text-sm">Pendentes</p>
                    </div>
                </GlassCard>

                <GlassCard className="p-6 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-blue-500/20">
                        <AlertCircle className="w-8 h-8 text-blue-400" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-white">{overview?.messages?.avgPerDay || 0}</p>
                        <p className="text-white/50 text-sm">Média Diária</p>
                    </div>
                </GlassCard>
            </div>
        </div>
    );
};

export default Dashboard;
