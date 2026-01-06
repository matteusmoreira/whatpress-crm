"""Quick Replies and Templates for WhatsApp CRM"""

from typing import List, Dict
from supabase_client import supabase
from datetime import datetime

# Default quick replies
DEFAULT_QUICK_REPLIES = [
    {
        'id': 'greeting',
        'title': 'Saudação',
        'content': 'Olá! 👋 Seja bem-vindo(a)! Como posso ajudar você hoje?',
        'category': 'greeting'
    },
    {
        'id': 'thanks',
        'title': 'Agradecimento',
        'content': 'Muito obrigado pelo contato! 😊 Estamos sempre à disposição.',
        'category': 'closing'
    },
    {
        'id': 'wait',
        'title': 'Aguarde',
        'content': 'Por favor, aguarde um momento enquanto verifico as informações. ⏳',
        'category': 'support'
    },
    {
        'id': 'hours',
        'title': 'Horário de Atendimento',
        'content': '🕐 Nosso horário de atendimento é de segunda a sexta, das 9h às 18h.',
        'category': 'info'
    },
    {
        'id': 'transfer',
        'title': 'Transferir',
        'content': 'Vou transferir seu atendimento para um especialista. Por favor, aguarde um momento.',
        'category': 'support'
    },
    {
        'id': 'resolved',
        'title': 'Resolvido',
        'content': '✅ Ótimo! Fico feliz em ter ajudado. Caso precise de mais alguma coisa, estou à disposição!',
        'category': 'closing'
    }
]

# Conversation labels/tags
DEFAULT_LABELS = [
    {'id': 'urgent', 'name': 'Urgente', 'color': '#EF4444'},
    {'id': 'vip', 'name': 'VIP', 'color': '#F59E0B'},
    {'id': 'new', 'name': 'Novo Cliente', 'color': '#10B981'},
    {'id': 'followup', 'name': 'Follow-up', 'color': '#3B82F6'},
    {'id': 'complaint', 'name': 'Reclamação', 'color': '#EF4444'},
    {'id': 'sale', 'name': 'Venda', 'color': '#8B5CF6'},
    {'id': 'support', 'name': 'Suporte', 'color': '#06B6D4'},
    {'id': 'question', 'name': 'Dúvida', 'color': '#6366F1'}
]


class QuickRepliesService:
    """Service for managing quick replies"""
    
    @staticmethod
    async def get_quick_replies(tenant_id: str) -> List[Dict]:
        """Get quick replies for a tenant"""
        try:
            result = supabase.table('quick_replies').select('*').eq('tenant_id', tenant_id).execute()
            if result.data:
                return result.data
            # Return defaults if none exist
            return DEFAULT_QUICK_REPLIES
        except:
            return DEFAULT_QUICK_REPLIES
    
    @staticmethod
    async def create_quick_reply(tenant_id: str, title: str, content: str, category: str = 'custom') -> Dict:
        """Create a new quick reply"""
        data = {
            'tenant_id': tenant_id,
            'title': title,
            'content': content,
            'category': category
        }
        result = supabase.table('quick_replies').insert(data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    async def delete_quick_reply(reply_id: str) -> bool:
        """Delete a quick reply"""
        supabase.table('quick_replies').delete().eq('id', reply_id).execute()
        return True


class LabelsService:
    """Service for managing conversation labels"""
    
    @staticmethod
    async def get_labels(tenant_id: str) -> List[Dict]:
        """Get labels for a tenant"""
        try:
            result = supabase.table('labels').select('*').eq('tenant_id', tenant_id).execute()
            if result.data:
                return result.data
            return DEFAULT_LABELS
        except:
            return DEFAULT_LABELS
    
    @staticmethod
    async def create_label(tenant_id: str, name: str, color: str) -> Dict:
        """Create a new label"""
        data = {
            'tenant_id': tenant_id,
            'name': name,
            'color': color
        }
        result = supabase.table('labels').insert(data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    async def add_label_to_conversation(conversation_id: str, label_id: str) -> bool:
        """Add label to conversation"""
        try:
            # Get current labels
            conv = supabase.table('conversations').select('labels').eq('id', conversation_id).execute()
            if conv.data:
                current_labels = conv.data[0].get('labels') or []
                if label_id not in current_labels:
                    current_labels.append(label_id)
                    supabase.table('conversations').update({'labels': current_labels}).eq('id', conversation_id).execute()
                return True
            else:
                print(f"Conversation {conversation_id} not found when adding label {label_id}")
                return False
        except Exception as e:
            print(f"Error adding label to conversation: {e}")
            raise e
    
    @staticmethod
    async def remove_label_from_conversation(conversation_id: str, label_id: str) -> bool:
        """Remove label from conversation"""
        try:
            conv = supabase.table('conversations').select('labels').eq('id', conversation_id).execute()
            if conv.data:
                current_labels = conv.data[0].get('labels') or []
                if label_id in current_labels:
                    current_labels.remove(label_id)
                    supabase.table('conversations').update({'labels': current_labels}).eq('id', conversation_id).execute()
                return True
            else:
                print(f"Conversation {conversation_id} not found when removing label {label_id}")
                return False
        except Exception as e:
            print(f"Error removing label from conversation: {e}")
            raise e


class AgentService:
    """Service for agent assignment"""
    
    @staticmethod
    async def assign_conversation(conversation_id: str, agent_id: str) -> Dict:
        """Assign conversation to agent"""
        result = supabase.table('conversations').update({
            'assigned_to': agent_id
        }).eq('id', conversation_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    async def unassign_conversation(conversation_id: str) -> Dict:
        """Unassign conversation"""
        result = supabase.table('conversations').update({
            'assigned_to': None
        }).eq('id', conversation_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    async def get_agent_stats(tenant_id: str, agent_id: str) -> Dict:
        """Get agent statistics"""
        # Get assigned conversations
        assigned = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('assigned_to', agent_id).execute()
        
        # Get open conversations
        open_convs = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('assigned_to', agent_id).eq('status', 'open').execute()
        
        # Get resolved today
        today = datetime.utcnow().date().isoformat()
        resolved = supabase.table('conversations').select('id', count='exact').eq('tenant_id', tenant_id).eq('assigned_to', agent_id).eq('status', 'resolved').gte('updated_at', today).execute()
        
        return {
            'total_assigned': assigned.count or 0,
            'open': open_convs.count or 0,
            'resolved_today': resolved.count or 0
        }
    
    @staticmethod
    async def get_agents(tenant_id: str) -> List[Dict]:
        """Get all agents for a tenant"""
        result = supabase.table('users').select('*').eq('tenant_id', tenant_id).in_('role', ['admin', 'agent']).execute()
        return result.data or []
