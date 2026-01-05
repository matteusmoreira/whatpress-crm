"""Evolution API Integration for WhatsApp CRM"""

import httpx
import logging
import json
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
        candidates = [url]
        last_segment = (self.base_url.rstrip('/').split('/')[-1] or '').lower()
        if last_segment != 'v2':
            candidates.append(f"{self.base_url}/v2{endpoint}")
        async with httpx.AsyncClient(timeout=30) as client:
            last_error = None
            for idx, candidate_url in enumerate(candidates):
                try:
                    if method == 'GET':
                        response = await client.get(candidate_url, headers=self.headers)
                    elif method == 'POST':
                        response = await client.post(candidate_url, headers=self.headers, json=data)
                    elif method == 'PUT':
                        response = await client.put(candidate_url, headers=self.headers, json=data)
                    elif method == 'DELETE':
                        response = await client.delete(candidate_url, headers=self.headers)
                    else:
                        raise Exception(f"Unsupported method: {method}")
                    
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    last_error = e
                    if e.response is not None and e.response.status_code == 404 and idx < len(candidates) - 1:
                        continue
                    logger.error(f"Evolution API error: {e}")
                    raise Exception(f"Evolution API error: {str(e)}")
                except httpx.HTTPError as e:
                    last_error = e
                    logger.error(f"Evolution API error: {e}")
                    raise Exception(f"Evolution API error: {str(e)}")
            
            raise Exception(f"Evolution API error: {str(last_error)}")
    
    # ==================== INSTANCE MANAGEMENT ====================
    
    async def create_instance(self, instance_name: str, webhook_url: str = None) -> dict:
        """Create a new WhatsApp instance"""
        data = {
            'instanceName': instance_name,
            'integration': 'WHATSAPP-BAILEYS',
            'qrcode': True,
            'rejectCall': False,
            'groupsIgnore': True,  # Ignorar mensagens de grupos
            'alwaysOnline': False,
            'readMessages': False,
            'readStatus': False,
            'syncFullHistory': False
        }
        
        if webhook_url:
            data['webhook'] = {
                'enabled': True,
                'url': webhook_url,
                'byEvents': False,
                'webhookByEvents': False,
                'base64': True,
                'webhookBase64': True,
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
            'text': message,
            'message': message
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
        def decode_maybe_base64_json(value):
            if not isinstance(value, str):
                return value
            s = value.strip()
            if not s or len(s) < 8:
                return value
            padded = s + ('=' * ((-len(s)) % 4))
            for decoder in (base64.b64decode, base64.urlsafe_b64decode):
                try:
                    decoded = decoder(padded)
                except Exception:
                    continue
                try:
                    decoded_text = decoded.decode('utf-8')
                except Exception:
                    continue
                try:
                    return json.loads(decoded_text)
                except Exception:
                    continue
            return value

        def deep_decode(value: Any, depth: int = 0) -> Any:
            if depth > 8:
                return value
            if isinstance(value, str):
                decoded = decode_maybe_base64_json(value)
                if decoded is not value:
                    return deep_decode(decoded, depth + 1)
                return value
            if isinstance(value, list):
                return [deep_decode(v, depth + 1) for v in value]
            if isinstance(value, dict):
                return {k: deep_decode(v, depth + 1) for k, v in value.items()}
            return value

        def unwrap_single_data_container(value: Any) -> Any:
            cur = value
            for _ in range(6):
                if isinstance(cur, dict) and len(cur.keys()) == 1 and 'data' in cur:
                    cur = cur.get('data')
                    continue
                break
            return cur

        raw_event = payload.get('event')
        event = str(raw_event or '').strip()
        normalized_event = event.lower().replace('_', '.')

        instance = payload.get('instance') or payload.get('instanceName') or payload.get('instance_name')

        data = deep_decode(payload.get('data') or {})
        data = deep_decode(unwrap_single_data_container(data))
        if isinstance(data, dict) and isinstance(data.get('data'), dict) and (
            isinstance(data.get('messages'), list) is False and isinstance(data.get('message'), dict) is False
        ):
            inner = data.get('data')
            if isinstance(inner, dict):
                data = inner

        if normalized_event == 'messages.upsert':
            messages = []
            if isinstance(data, dict) and isinstance(data.get('messages'), list):
                messages = data.get('messages') or []
            elif isinstance(data, dict) and isinstance(data.get('message'), dict):
                messages = [data.get('message')]
            elif isinstance(data, dict) and ('key' in data or 'message' in data):
                messages = [data]

            if messages:
                raw_msg = deep_decode(messages[0])
                msg = raw_msg if isinstance(raw_msg, dict) else {}
                key = msg.get('key') or {}
                message_content = msg.get('message') or {}
                message_content = deep_decode(message_content)
                if not isinstance(message_content, dict):
                    message_content = {}

                def unwrap_content(content: dict) -> dict:
                    cur = content
                    for _ in range(8):
                        if not isinstance(cur, dict):
                            return {}

                        ephemeral = cur.get('ephemeralMessage')
                        if isinstance(ephemeral, dict) and isinstance(ephemeral.get('message'), dict):
                            cur = ephemeral.get('message')
                            continue

                        view_once = cur.get('viewOnceMessage')
                        if isinstance(view_once, dict) and isinstance(view_once.get('message'), dict):
                            cur = view_once.get('message')
                            continue

                        view_once_v2 = cur.get('viewOnceMessageV2')
                        if isinstance(view_once_v2, dict) and isinstance(view_once_v2.get('message'), dict):
                            cur = view_once_v2.get('message')
                            continue

                        view_once_v2_ext = cur.get('viewOnceMessageV2Extension')
                        if isinstance(view_once_v2_ext, dict) and isinstance(view_once_v2_ext.get('message'), dict):
                            cur = view_once_v2_ext.get('message')
                            continue

                        document_with_caption = cur.get('documentWithCaptionMessage')
                        if isinstance(document_with_caption, dict) and isinstance(document_with_caption.get('message'), dict):
                            cur = document_with_caption.get('message')
                            continue

                        edited = cur.get('editedMessage')
                        if isinstance(edited, dict) and isinstance(edited.get('message'), dict):
                            cur = edited.get('message')
                            continue

                        return cur if isinstance(cur, dict) else {}

                    return cur if isinstance(cur, dict) else {}

                message_content = unwrap_content(message_content)

                def extract_text_fallback(content: Any) -> Optional[str]:
                    if content is None:
                        return None
                    if isinstance(content, (int, float, bool)):
                        return str(content)
                    if isinstance(content, str):
                        return content
                    if not isinstance(content, dict):
                        return None

                    cur: Any = content
                    for _ in range(6):
                        if isinstance(cur, dict) and isinstance(cur.get('message'), dict):
                            cur = cur.get('message')
                            continue
                        if isinstance(cur, dict) and isinstance(cur.get('data'), dict) and len(cur.keys()) == 1:
                            cur = cur.get('data')
                            continue
                        break

                    if not isinstance(cur, dict):
                        return None

                    direct_keys = [
                        'conversation',
                        'text',
                        'caption',
                        'title',
                        'selectedDisplayText',
                        'selectedButtonId',
                        'selectedId',
                        'fileName',
                        'displayText'
                    ]
                    for k in direct_keys:
                        v = cur.get(k)
                        if isinstance(v, str) and v.strip():
                            return v

                    nested = cur.get('textMessage')
                    if isinstance(nested, dict) and isinstance(nested.get('text'), str) and nested.get('text').strip():
                        return nested.get('text')

                    nested = cur.get('extendedTextMessage')
                    if isinstance(nested, dict) and isinstance(nested.get('text'), str) and nested.get('text').strip():
                        return nested.get('text')

                    nested = cur.get('buttonsResponseMessage')
                    if isinstance(nested, dict):
                        v = nested.get('selectedDisplayText') or nested.get('selectedButtonId')
                        if isinstance(v, str) and v.strip():
                            return v

                    nested = cur.get('listResponseMessage')
                    if isinstance(nested, dict):
                        v = nested.get('title')
                        if isinstance(v, str) and v.strip():
                            return v
                        ssr = nested.get('singleSelectReply')
                        if isinstance(ssr, dict) and isinstance(ssr.get('selectedRowId'), str) and ssr.get('selectedRowId').strip():
                            return ssr.get('selectedRowId')

                    nested = cur.get('templateButtonReplyMessage')
                    if isinstance(nested, dict):
                        v = nested.get('selectedDisplayText') or nested.get('selectedId')
                        if isinstance(v, str) and v.strip():
                            return v

                    nested = cur.get('reactionMessage')
                    if isinstance(nested, dict) and isinstance(nested.get('text'), str) and nested.get('text').strip():
                        return nested.get('text')

                    for v in cur.values():
                        if isinstance(v, str) and v.strip():
                            return v
                        if isinstance(v, dict):
                            inner = extract_text_fallback(v)
                            if isinstance(inner, str) and inner.strip():
                                return inner

                    return None
                
                # Extract text content
                text = None
                msg_type = 'text'
                media_url = None
                
                if 'conversation' in message_content:
                    text = message_content['conversation']
                elif 'extendedTextMessage' in message_content:
                    text = message_content['extendedTextMessage'].get('text')
                elif 'buttonsResponseMessage' in message_content:
                    br = message_content.get('buttonsResponseMessage') or {}
                    if isinstance(br, dict):
                        text = br.get('selectedDisplayText') or br.get('selectedButtonId')
                elif 'listResponseMessage' in message_content:
                    lr = message_content.get('listResponseMessage') or {}
                    if isinstance(lr, dict):
                        text = lr.get('title')
                        if not text:
                            ssr = lr.get('singleSelectReply') or {}
                            if isinstance(ssr, dict):
                                text = ssr.get('selectedRowId')
                elif 'templateButtonReplyMessage' in message_content:
                    tbr = message_content.get('templateButtonReplyMessage') or {}
                    if isinstance(tbr, dict):
                        text = tbr.get('selectedDisplayText') or tbr.get('selectedId')
                elif 'reactionMessage' in message_content:
                    rx = message_content.get('reactionMessage') or {}
                    if isinstance(rx, dict):
                        text = rx.get('text')
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
                elif 'stickerMessage' in message_content:
                    text = '[Sticker]'
                elif 'locationMessage' in message_content:
                    text = '[Localização]'
                elif 'contactMessage' in message_content:
                    text = '[Contato]'
                elif 'contactsArrayMessage' in message_content:
                    text = '[Contatos]'

                if msg_type == 'audio' and not (text or '').strip():
                    text = '[Áudio]'
                if msg_type == 'image' and not (text or '').strip():
                    text = '[Imagem]'
                if msg_type == 'video' and not (text or '').strip():
                    text = '[Vídeo]'
                if msg_type == 'document' and not (text or '').strip():
                    text = '[Documento]'
                if msg_type == 'text' and not (text or '').strip():
                    text = extract_text_fallback(message_content)
                if msg_type == 'text' and not (text or '').strip():
                    text = '[Mensagem]'
                
                remote_jid_raw = ''
                if isinstance(key, dict):
                    remote_jid_raw = key.get('remoteJid') or key.get('remote_jid') or ''
                if not remote_jid_raw and isinstance(msg, dict):
                    remote_jid_raw = msg.get('remoteJid') or msg.get('remote_jid') or ''
                if not remote_jid_raw and isinstance(data, dict):
                    data_key = data.get('key') or {}
                    if isinstance(data_key, dict):
                        remote_jid_raw = data_key.get('remoteJid') or data_key.get('remote_jid') or ''

                remote_id = remote_jid_raw
                if isinstance(remote_id, str):
                    if '@' in remote_id:
                        remote_id = remote_id.split('@')[0]
                    remote_id = remote_id.strip()
                else:
                    remote_id = ''

                return {
                    'event': 'message',
                    'instance': instance,
                    'message_id': key.get('id') if isinstance(key, dict) else None,
                    'from_me': key.get('fromMe', False) if isinstance(key, dict) else False,
                    'remote_jid': remote_id,
                    'remote_jid_raw': remote_jid_raw,
                    'content': text,
                    'type': msg_type,
                    'media_url': media_url,
                    'timestamp': msg.get('messageTimestamp'),
                    'push_name': msg.get('pushName')
                }
        
        elif normalized_event == 'connection.update':
            # Evolution API v2 pode retornar o estado em diferentes formatos
            state = data.get('state', '')
            status_reason = data.get('statusReason')
            
            # Normalizar o estado - pode ser 'open', 'close', 'connecting', etc.
            # Também pode vir como 'open' em maiúsculo ou minúsculo
            normalized_state = state.lower() if isinstance(state, str) else ''
            
            # Log para debug
            logger.info(f"Connection update received: state={state}, statusReason={status_reason}, data={data}")
            
            return {
                'event': 'connection',
                'instance': instance,
                'state': normalized_state,
                'status_reason': status_reason,
                'raw_data': data
            }
        
        elif normalized_event == 'qrcode.updated':
            return {
                'event': 'qrcode',
                'instance': instance,
                'qrcode': data.get('qrcode', {}).get('base64')
            }
        
        elif normalized_event == 'presence.update':
            # Handle typing indicator
            presence_data = data.get('presences', [{}])[0] if data.get('presences') else data
            presence_id = presence_data.get('id', '')
            if isinstance(presence_id, str) and '@' in presence_id:
                presence_id = presence_id.split('@')[0]
            return {
                'event': 'presence',
                'instance': instance,
                'remote_jid': presence_id,
                'presence': presence_data.get('presence'),  # 'composing', 'paused', 'available', 'unavailable'
                'participant': presence_data.get('participant')
            }
        
        return {'event': normalized_event or event, 'instance': instance, 'data': data}


# Global instance
evolution_api = EvolutionAPI(
    base_url="https://api.whatpress.pro",
    api_key="c5176bf19a9b2e240204522e45236822"
)
