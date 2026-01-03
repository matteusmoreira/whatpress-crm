# WhatsApp CRM - Contracts & Backend Integration Guide

## 📋 API Contracts

### Authentication
```typescript
POST /api/auth/login
Request: { email: string, password: string }
Response: { user: User, token: string }

GET /api/auth/me
Headers: Authorization: Bearer {token}
Response: User
```

### Tenants (SuperAdmin only)
```typescript
GET /api/tenants
Response: Tenant[]

GET /api/tenants/:id
Response: Tenant

POST /api/tenants
Request: { name: string, slug: string }
Response: Tenant

PUT /api/tenants/:id
Request: Partial<Tenant>
Response: Tenant

DELETE /api/tenants/:id
Response: { success: boolean }

GET /api/tenants/stats
Response: { totalTenants, activeTenants, totalMessages, totalConnections, messagesPerDay }
```

### Connections
```typescript
GET /api/connections?tenantId={tenantId}
Response: Connection[]

POST /api/connections
Request: { tenantId, provider, instanceName, phoneNumber }
Response: Connection

POST /api/connections/:id/test
Response: { success: boolean, message: string }

PATCH /api/connections/:id/status
Request: { status: 'connected' | 'disconnected' | 'connecting' }
Response: Connection

DELETE /api/connections/:id
Response: { success: boolean }
```

### Conversations
```typescript
GET /api/conversations?tenantId={tenantId}&status={status}&connectionId={connectionId}
Response: Conversation[]

GET /api/conversations/:id
Response: Conversation

PATCH /api/conversations/:id/status
Request: { status: 'open' | 'pending' | 'resolved' }
Response: Conversation

POST /api/conversations/:id/read
Response: Conversation
```

### Messages
```typescript
GET /api/messages?conversationId={conversationId}
Response: Message[]

POST /api/messages
Request: { conversationId, content, type: 'text' | 'image' | 'audio' }
Response: Message
```

---

## 🔄 Mock Data Mapping

### Frontend Mock Files
- `/app/frontend/src/lib/mock-data.js` - Contains all mock data
- `/app/frontend/src/lib/storage.js` - Fake API layer with localStorage

### Data to Replace with Backend

| Mock Location | Backend Endpoint | Notes |
|---------------|------------------|-------|
| `mockTenants` | `/api/tenants` | SuperAdmin only |
| `mockUsers` | `/api/auth/login` | JWT auth |
| `mockConnections` | `/api/connections` | Per tenant |
| `mockConversations` | `/api/conversations` | Per tenant with filters |
| `mockMessages` | `/api/messages` | Per conversation |

---

## 🔌 Backend Implementation Steps

### Phase 2: Database & Auth
1. Set up MongoDB collections: `tenants`, `users`, `connections`, `conversations`, `messages`
2. Implement JWT authentication
3. Add tenant middleware for multi-tenancy
4. Create API routes matching contracts above

### Phase 3: WhatsApp Webhooks
1. Implement webhook endpoints for each provider:
   - `/api/webhooks/evolution`
   - `/api/webhooks/wuzapi`
   - `/api/webhooks/pastorini`
2. Parse incoming messages and create conversations/messages
3. Update message status (delivered, read)

### Phase 4: Realtime WebSockets
1. Set up Socket.io or similar
2. Emit events: `new_message`, `message_status`, `conversation_update`
3. Subscribe clients to their tenant's room

---

## 🎨 Frontend Integration Points

### Files to Modify
```
/app/frontend/src/lib/storage.js  → Replace with axios calls
/app/frontend/src/store/authStore.js → Add token management
/app/frontend/src/store/appStore.js → Add API error handling
```

### Integration Pattern
```javascript
// Current (localStorage)
const tenants = await TenantsRepository.list();

// After backend integration
const { data: tenants } = await axios.get(`${API}/tenants`, {
  headers: { Authorization: `Bearer ${token}` }
});
```

---

## 📱 Environment Variables Needed

### Backend (.env)
```
MONGO_URL=mongodb://...
JWT_SECRET=your-secret-key
EVOLUTION_API_KEY=...
WUZAPI_TOKEN=...
PASTORINI_TOKEN=...
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=https://...
```
