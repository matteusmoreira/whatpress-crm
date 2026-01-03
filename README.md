# 🚀 WhatsApp CRM SaaS

Um CRM WhatsApp multi-tenant com design glassmorphism moderno, construído em React.

## ✅ Fase 1 - Frontend Completo (ATUAL)

### 🎨 Features Implementadas
- **Login com autenticação mock** - Duas opções: SuperAdmin e Admin Tenant
- **Dashboard SuperAdmin** - KPIs, lista de tenants, CRUD completo
- **Inbox de Conversas** - Chat em tempo real com bubbles estilo WhatsApp
- **Conexões WhatsApp** - Suporte a Evolution API, Wuzapi, Pastorini
- **Design Glassmorphism** - Visual impressionante com gradientes verdes
- **Responsivo** - Mobile-first, sidebar colapsável

### 🛠️ Stack
- React 19 + React Router v7
- TailwindCSS + Glassmorphism custom
- Zustand para estado global
- localStorage para persistência
- Lucide React para ícones

## 🚀 Como Rodar

```bash
# Acesse a URL do projeto
https://[seu-dominio]/sign-in

# Credenciais de demonstração:

# SuperAdmin
Email: super@admin.com
Senha: 123456

# Admin de Tenant
Email: admin@minhaempresa.com
Senha: 123456
```

## 📁 Estrutura do Projeto

```
frontend/src/
├── components/
│   ├── GlassCard.jsx          # Componentes glass reutilizáveis
│   └── Layout/
│       ├── MainLayout.jsx     # Layout principal com Outlet
│       └── Sidebar.jsx        # Navegação lateral
├── pages/
│   ├── SignIn.jsx             # Tela de login
│   ├── SuperAdminDashboard.jsx # Dashboard admin
│   ├── Inbox.jsx              # Chat principal
│   ├── Connections.jsx        # Config de conexões
│   └── Settings.jsx           # Configurações
├── store/
│   ├── authStore.js           # Estado de autenticação
│   └── appStore.js            # Estado global da app
├── lib/
│   ├── types.js               # Tipos e constantes
│   ├── mock-data.js           # Dados mock
│   └── storage.js             # API fake com localStorage
└── App.js                     # Rotas da aplicação
```

## 🎯 Funcionalidades por Tela

### Login (/sign-in)
- Form glassmorphism com validação
- Botões de acesso rápido para demo
- Redirect automático por role

### SuperAdmin (/superadmin)
- 4 KPI cards com métricas
- Tabela de tenants com filtros
- Modal para criar novo tenant
- Ações de editar/excluir

### Inbox (/app/inbox)
- Lista de conversas com busca
- Filtros por status e conexão
- Chat com bubbles e status
- Envio de mensagens (persistido)
- Scroll automático

### Conexões (/app/settings/connections)
- Cards por provedor
- Status de conexão (conectado/desconectado)
- Teste de conexão simulado
- Modal para nova conexão

## 🗺️ Roadmap

```
✅ Fase 1: UI + localStorage (COMPLETO)
⏳ Fase 2: Backend FastAPI + MongoDB
⏳ Fase 3: Webhooks reais WhatsApp
⏳ Fase 4: WebSockets tempo real
```

## 📝 Notas

- Todos os dados são persistidos em localStorage
- Ao limpar localStorage, dados mock são restaurados
- API fake simula delays realistas (300-800ms)
- Design segue paleta verde: #10B981, #059669, #047857

---

**Desenvolvido com ❤️ usando React + TailwindCSS**
