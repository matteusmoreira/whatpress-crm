"""Evolution API Integration for WhatsApp CRM"""

import httpx
import logging
from typing import Optional, Dict, Any, List
import base64

logger = logging.getLogger(__name__)

class EvolutionAPI:
    """Client for Evolution API v2"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request to Evolution API"""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                if method == 'GET':
                    response = await client.get(url, headers=self.headers)
                elif method == 'POST':
                    response = await client.post(url, headers=self.headers, json=data)
                elif method == 'PUT':
                    response = await client.put(url, headers=self.headers, json=data)
                elif method == 'DELETE':
                    response = await client.delete(url, headers=self.headers)
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Evolution API error: {e}")
                raise Exception(f"Evolution API error: {str(e)}")
    
    # ==================== INSTANCE MANAGEMENT ====================
    
    async def create_instance(self, instance_name: str, webhook_url: str = None) -> dict:
        """Create a new WhatsApp instance"""
        data = {
            'instanceName': instance_name,
            'integration': 'WHATSAPP-BAILEYS',
            'qrcode': True,
            'rejectCall': False,
            'groupsIgnore': False,
            'alwaysOnline': False,
            'readMessages': False,
            'readStatus': False,
            'syncFullHistory': False
        }
        
        if webhook_url:
            data['webhook'] = {
                'url': webhook_url,
                'byEvents': False,
                'base64': True,
                'headers': {},
                'events': [
                    'MESSAGES_UPSERT',
                    'MESSAGES_UPDATE',
                    'CONNECTION_UPDATE',
                    'QRCODE_UPDATED',
                    'PRESENCE_UPDATE'
                ]
            }
        
        return await self._request('POST', '/instance/create', data)
    
    async def fetch_instances(self) -> list:
        """Fetch all instances"""
        return await self._request('GET', '/instance/fetchInstances')
    
    async def get_instance(self, instance_name: str) -> dict:
        """Get specific instance"""
        instances = await self.fetch_instances()
        for inst in instances:
            if inst['name'] == instance_name:
                return inst
        return None
    
    async def delete_instance(self, instance_name: str) -> dict:
        """Delete an instance"""
        return await self._request('DELETE', f'/instance/delete/{instance_name}')
    
    async def logout_instance(self, instance_name: str) -> dict:
        """Logout from WhatsApp"""
        return await self._request('DELETE', f'/instance/logout/{instance_name}')
    
    async def restart_instance(self, instance_name: str) -> dict:
        """Restart an instance"""
        return await self._request('PUT', f'/instance/restart/{instance_name}')
    
    # ==================== CONNECTION ====================
    
    async def get_connection_state(self, instance_name: str) -> dict:
        """Get connection state"""
        return await self._request('GET', f'/instance/connectionState/{instance_name}')
    
    async def get_qrcode(self, instance_name: str) -> dict:
        """Get QR code for connection"""
        return await self._request('GET', f'/instance/connect/{instance_name}')
    
    async def connect_instance(self, instance_name: str) -> dict:
        """Connect instance (get QR code)"""
        return await self._request('GET', f'/instance/connect/{instance_name}')
    
    # ==================== MESSAGING ====================
    
    async def send_text(self, instance_name: str, phone: str, message: str) -> dict:
        """Send text message"""
        # Format phone number
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'text': message
        }
        
        return await self._request('POST', f'/message/sendText/{instance_name}', data)
    
    async def send_media(self, instance_name: str, phone: str, media_type: str, 
                         media_url: str = None, media_base64: str = None,
                         caption: str = None, filename: str = None) -> dict:
        """Send media message (image, audio, video, document)"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'mediatype': media_type,  # 'image', 'video', 'audio', 'document'
            'caption': caption or '',
            'fileName': filename or 'file'
        }
        
        if media_url:
            data['media'] = media_url
        elif media_base64:
            data['media'] = media_base64
        
        return await self._request('POST', f'/message/sendMedia/{instance_name}', data)
    
    async def send_audio(self, instance_name: str, phone: str, audio_url: str) -> dict:
        """Send audio as voice message"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'audio': audio_url
        }
        
        return await self._request('POST', f'/message/sendWhatsAppAudio/{instance_name}', data)
    
    async def send_location(self, instance_name: str, phone: str, 
                            latitude: float, longitude: float,
                            name: str = None, address: str = None) -> dict:
        """Send location"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'latitude': latitude,
            'longitude': longitude,
            'name': name or '',
            'address': address or ''
        }
        
        return await self._request('POST', f'/message/sendLocation/{instance_name}', data)
    
    async def send_contact(self, instance_name: str, phone: str, 
                           contact_name: str, contact_phone: str) -> dict:
        """Send contact card"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'contact': [{
                'fullName': contact_name,
                'wuid': self._format_phone(contact_phone),
                'phoneNumber': contact_phone
            }]
        }
        
        return await self._request('POST', f'/message/sendContact/{instance_name}', data)
    
    async def send_buttons(self, instance_name: str, phone: str, 
                           text: str, buttons: List[Dict], 
                           title: str = None, footer: str = None) -> dict:
        """Send interactive buttons"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'title': title or '',
            'description': text,
            'footer': footer or '',
            'buttons': buttons
        }
        
        return await self._request('POST', f'/message/sendButtons/{instance_name}', data)
    
    async def send_list(self, instance_name: str, phone: str,
                        title: str, description: str, button_text: str,
                        sections: List[Dict], footer: str = None) -> dict:
        """Send list message"""
        number = self._format_phone(phone)
        
        data = {
            'number': number,
            'title': title,
            'description': description,
            'buttonText': button_text,
            'footerText': footer or '',
            'sections': sections
        }
        
        return await self._request('POST', f'/message/sendList/{instance_name}', data)
    
    # ==================== CHAT OPERATIONS ====================
    
    async def fetch_messages(self, instance_name: str, phone: str, count: int = 50) -> dict:
        """Fetch messages from a chat"""
        number = self._format_phone(phone)
        
        data = {
            'where': {
                'key': {
                    'remoteJid': f"{number}@s.whatsapp.net"
                }
            },
            'limit': count
        }
        
        return await self._request('POST', f'/chat/findMessages/{instance_name}', data)
    
    async def fetch_contacts(self, instance_name: str) -> dict:
        """Fetch all contacts"""
        return await self._request('POST', f'/chat/findContacts/{instance_name}', {})
    
    async def fetch_chats(self, instance_name: str) -> dict:
        """Fetch all chats"""
        return await self._request('POST', f'/chat/findChats/{instance_name}', {})
    
    async def mark_as_read(self, instance_name: str, phone: str) -> dict:
        """Mark chat as read"""
        number = self._format_phone(phone)
        
        data = {
            'readMessages': [{
                'remoteJid': f"{number}@s.whatsapp.net",
                'fromMe': False,
                'id': 'all'
            }]
        }
        
        return await self._request('POST', f'/chat/markMessageAsRead/{instance_name}', data)
    
    async def send_presence(self, instance_name: str, phone: str, presence: str = 'composing') -> dict:
        """Send presence (typing indicator)"""
        number = self._format_phone(phone)
        
        data = {
            'number': f"{number}@s.whatsapp.net",
            'presence': presence  # 'composing', 'recording', 'paused'
        }
        
        return await self._request('POST', f'/chat/sendPresence/{instance_name}', data)
    
    # ==================== PROFILE ====================
    
    async def get_profile(self, instance_name: str) -> dict:
        """Get instance profile"""
        return await self._request('GET', f'/instance/fetchInstances')
    
    async def get_profile_picture(self, instance_name: str, phone: str) -> dict:
        """Get profile picture URL"""
        number = self._format_phone(phone)
        
        data = {'number': f"{number}@s.whatsapp.net"}
        
        return await self._request('POST', f'/chat/fetchProfilePictureUrl/{instance_name}', data)
    
    # ==================== WEBHOOK ====================
    
    async def set_webhook(self, instance_name: str, webhook_url: str, events: list = None) -> dict:
        """Configure webhook for instance"""
        if events is None:
            events = [
                'MESSAGES_UPSERT',
                'MESSAGES_UPDATE', 
                'CONNECTION_UPDATE',
                'QRCODE_UPDATED',
                'MESSAGES_DELETE',
                'SEND_MESSAGE'
            ]
        
        data = {
            'webhook': {
                'enabled': True,
                'url': webhook_url,
                'webhookByEvents': False,
                'webhookBase64': True,
                'events': events
            }
        }
        
        return await self._request('PUT', f'/webhook/set/{instance_name}', data)
    
    async def get_webhook(self, instance_name: str) -> dict:
        """Get webhook configuration"""
        return await self._request('GET', f'/webhook/find/{instance_name}')
    
    # ==================== HELPERS ====================
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number for WhatsApp"""
        # Remove all non-numeric characters
        number = ''.join(filter(str.isdigit, phone))
        
        # Ensure Brazilian format if starts with local code
        if len(number) == 11 and number[0] != '5':
            number = '55' + number
        elif len(number) == 10:
            number = '55' + number
        
        return number
    
    def parse_webhook_message(self, payload: dict) -> dict:
        """Parse incoming webhook message"""
        event = payload.get('event')
        instance = payload.get('instance')
        data = payload.get('data', {})
        
        if event == 'messages.upsert':
            messages = data.get('messages', [])
            if messages:
                msg = messages[0]
                key = msg.get('key', {})
                message_content = msg.get('message', {})
                
                # Extract text content
                text = None
                msg_type = 'text'
                media_url = None
                
                if 'conversation' in message_content:
                    text = message_content['conversation']
                elif 'extendedTextMessage' in message_content:
                    text = message_content['extendedTextMessage'].get('text')
                elif 'imageMessage' in message_content:
                    msg_type = 'image'
                    text = message_content['imageMessage'].get('caption', '')
                    media_url = message_content['imageMessage'].get('url')
                elif 'videoMessage' in message_content:
                    msg_type = 'video'
                    text = message_content['videoMessage'].get('caption', '')
                    media_url = message_content['videoMessage'].get('url')
                elif 'audioMessage' in message_content:
                    msg_type = 'audio'
                    media_url = message_content['audioMessage'].get('url')
                elif 'documentMessage' in message_content:
                    msg_type = 'document'
                    text = message_content['documentMessage'].get('fileName', 'document')
                    media_url = message_content['documentMessage'].get('url')
                
                return {
                    'event': 'message',
                    'instance': instance,
                    'message_id': key.get('id'),
                    'from_me': key.get('fromMe', False),
                    'remote_jid': key.get('remoteJid', '').replace('@s.whatsapp.net', ''),
                    'content': text,
                    'type': msg_type,
                    'media_url': media_url,
                    'timestamp': msg.get('messageTimestamp'),
                    'push_name': msg.get('pushName')
                }
        
        elif event == 'connection.update':
            return {
                'event': 'connection',
                'instance': instance,
                'state': data.get('state'),
                'status_reason': data.get('statusReason')
            }
        
        elif event == 'qrcode.updated':
            return {
                'event': 'qrcode',
                'instance': instance,
                'qrcode': data.get('qrcode', {}).get('base64')
            }
        
        elif event == 'presence.update':
            # Handle typing indicator
            presence_data = data.get('presences', [{}])[0] if data.get('presences') else data
            return {
                'event': 'presence',
                'instance': instance,
                'remote_jid': presence_data.get('id', '').replace('@s.whatsapp.net', ''),
                'presence': presence_data.get('presence'),  # 'composing', 'paused', 'available', 'unavailable'
                'participant': presence_data.get('participant')
            }
        
        return {'event': event, 'instance': instance, 'data': data}


# Global instance
evolution_api = EvolutionAPI(
    base_url="https://api.whatpress.pro",
    api_key="c5176bf19a9b2e240204522e45236822"
)
