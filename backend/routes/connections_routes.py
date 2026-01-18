"""
Connections routes extracted from server.py.

This module contains all WhatsApp connection management endpoints:
- GET /connections - List connections
- POST /connections - Create connection
- POST /connections/{id}/test - Test connection
- GET /connections/{id}/qrcode - Get QR code
- POST /connections/{id}/sync - Sync status
- PATCH /connections/{id}/status - Update status
- DELETE /connections/{id} - Delete connection
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

try:
    from ..supabase_client import supabase
    from ..models import ConnectionCreate, ConnectionStatusUpdate
    from ..utils.auth_helpers import verify_token
    from ..whatsapp.container import get_whatsapp_container
    from ..whatsapp.observability import LogContext
    from ..whatsapp.providers.base import ConnectionRef, ProviderContext
except ImportError:
    from supabase_client import supabase
    from models import ConnectionCreate, ConnectionStatusUpdate
    from utils.auth_helpers import verify_token
    from whatsapp.container import get_whatsapp_container
    from whatsapp.observability import LogContext
    from whatsapp.providers.base import ConnectionRef, ProviderContext

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/connections", tags=["Connections"])


# ==================== HELPER FUNCTIONS ====================

def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return payload.get('tenant_id')
    return payload.get('tenant_id')


def _get_whatsapp_container_instance():
    return get_whatsapp_container()


def _get_whatsapp_provider(provider_id: str):
    return _get_whatsapp_container_instance().registry.get(provider_id)


def _make_provider_ctx(*, tenant_id: str, provider: str, instance_name: str, correlation_id: str = None):
    container = _get_whatsapp_container_instance()
    log_ctx = LogContext(
        tenant_id=str(tenant_id or ""),
        provider=str(provider or ""),
        instance_name=str(instance_name or ""),
        correlation_id=str(correlation_id) if correlation_id else None,
    )
    return container, ProviderContext(obs=container.obs, log_ctx=log_ctx)


def _resolve_public_base_url(request: Optional[Request] = None) -> str:
    """Resolve the public base URL for webhooks."""
    public_url = os.getenv("PUBLIC_BACKEND_URL", "").strip()
    if public_url:
        return public_url.rstrip("/")
    if request:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip().lower()
        host = request.headers.get("x-forwarded-host") or request.url.netloc
        return f"{proto}://{host}"
    return "https://altarcrm.up.railway.app"


def _resolve_provider_webhook_url(request: Request, provider: str, instance_name: str) -> str:
    base = _resolve_public_base_url(request)
    return f"{base}/api/webhooks/{provider}/{instance_name}"


def _is_local_webhook_url(url: str) -> bool:
    """Check if URL is a local/development URL."""
    if not url:
        return False
    lowered = url.lower()
    return any(x in lowered for x in ["localhost", "127.0.0.1", "0.0.0.0", "ngrok", "host.docker.internal"])


def _extract_qrcode_value(obj: Any) -> Optional[str]:
    """Extract QR code value from response object."""
    if not obj:
        return None
    if isinstance(obj, str):
        return obj if obj.startswith("data:image") or len(obj) > 100 else None
    if isinstance(obj, dict):
        for key in ["qrcode", "qr", "qr_code", "qrCode", "base64", "code", "pairingCode"]:
            val = obj.get(key)
            if val and isinstance(val, str) and (val.startswith("data:image") or len(val) > 100):
                return val
        for val in obj.values():
            result = _extract_qrcode_value(val)
            if result:
                return result
    return None


def _extract_uazapi_instance_token(obj: Any) -> Optional[str]:
    """Extract UAZAPI instance token from response."""
    if not obj:
        return None
    
    def walk(value: Any, depth: int) -> Optional[str]:
        if depth > 5:
            return None
        if isinstance(value, str):
            if value.startswith("Bearer "):
                return value[7:].strip()
            if len(value) > 32 and all(c.isalnum() or c in "-_" for c in value):
                return value
        if isinstance(value, dict):
            for key in ["token", "apikey", "api_key", "apiToken", "authorization", "instanceToken"]:
                if key in value:
                    result = walk(value[key], depth + 1)
                    if result:
                        return result
            for v in value.values():
                result = walk(v, depth + 1)
                if result:
                    return result
        if isinstance(value, list):
            for item in value:
                result = walk(item, depth + 1)
                if result:
                    return result
        return None
    
    return walk(obj, 0)


def _is_connected_state(provider: str, state: dict) -> bool:
    """Check if connection state indicates connected status."""
    if not state:
        return False
    provider_id = str(provider or "").lower()
    
    # Check direct state field
    state_val = str(state.get("state") or state.get("status") or "").lower()
    if state_val in {"open", "connected", "online", "authenticated"}:
        return True
    
    # Check nested instance.state
    instance = state.get("instance") or {}
    if isinstance(instance, dict):
        inst_state = str(instance.get("state") or "").lower()
        if inst_state in {"open", "connected", "online", "authenticated"}:
            return True
    
    return False


def _get_connection_status(provider: str, state: dict) -> str:
    """Get normalized connection status from provider state."""
    if _is_connected_state(provider, state):
        return "connected"
    
    state_val = str(state.get("state") or state.get("status") or "").lower()
    if state_val in {"connecting", "qrcode", "waiting", "pairing"}:
        return "connecting"
    
    return "disconnected"


def _whatsapp_http_error(e: Exception) -> HTTPException:
    """Convert WhatsApp provider exception to HTTP exception."""
    msg = str(e)
    if "401" in msg or "unauthorized" in msg.lower():
        return HTTPException(status_code=401, detail="Credenciais do provedor inválidas")
    if "404" in msg or "not found" in msg.lower():
        return HTTPException(status_code=404, detail="Instância não encontrada no provedor")
    if "timeout" in msg.lower():
        return HTTPException(status_code=504, detail="Timeout ao conectar com o provedor")
    return HTTPException(status_code=502, detail=f"Erro do provedor: {msg[:200]}")


def _enforce_connections_limit(tenant_id: Optional[str]):
    """Check if tenant has reached connections limit."""
    if not tenant_id:
        return
    # TODO: Implement actual limit checking from plans table
    pass


# ==================== ROUTES ====================

@router.get("")
async def list_connections(tenant_id: str, payload: dict = Depends(verify_token)):
    """List connections for a tenant."""
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin':
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")
        if tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
    
    result = supabase.table('connections').select('*').eq('tenant_id', tenant_id).execute()
    
    connections = []
    for c in result.data:
        connections.append({
            'id': c['id'],
            'tenantId': c['tenant_id'],
            'provider': c['provider'],
            'instanceName': c['instance_name'],
            'phoneNumber': c['phone_number'],
            'status': c['status'],
            'webhookUrl': c['webhook_url'],
            'config': c['config'],
            'createdAt': c['created_at']
        })
    
    return connections


@router.post("")
async def create_connection(connection: ConnectionCreate, payload: dict = Depends(verify_token)):
    """Create a new connection."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin':
        if not user_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")
        if connection.tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")
    
    _enforce_connections_limit(connection.tenant_id)
    cfg = connection.config if isinstance(connection.config, dict) else {}
    
    data = {
        'tenant_id': connection.tenant_id,
        'provider': connection.provider,
        'instance_name': connection.instance_name,
        'phone_number': connection.phone_number or '',
        'status': 'disconnected',
        'webhook_url': '',
        'config': cfg,
    }
    
    result = supabase.table('connections').insert(data).execute()
    
    # Update tenant connections count
    tenant = supabase.table('tenants').select('connections_count').eq('id', connection.tenant_id).execute()
    if tenant.data:
        new_count = tenant.data[0]['connections_count'] + 1
        supabase.table('tenants').update({'connections_count': new_count}).eq('id', connection.tenant_id).execute()
    
    c = result.data[0]
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'provider': c['provider'],
        'instanceName': c['instance_name'],
        'phoneNumber': c['phone_number'],
        'status': c['status'],
        'webhookUrl': c['webhook_url'],
        'config': c['config'],
        'createdAt': c['created_at']
    }


@router.post("/{connection_id}/test")
async def test_connection(connection_id: str, request: Request, payload: dict = Depends(verify_token)):
    """Test a connection - creates instance and gets QR code."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    
    if not instance_name or len(instance_name) > 80:
        raise HTTPException(status_code=400, detail="instanceName inválido.")
    
    for ch in instance_name:
        if not (ch.isalnum() or ch in {"_", "-", "."}):
            raise HTTPException(status_code=400, detail="instanceName inválido.")
    
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )

    container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"conn_test:{connection_id}",
    )
    provider = _get_whatsapp_provider(provider_id)

    cfg = conn_ref.config or {}
    token_present = bool(
        str(
            cfg.get("token")
            or cfg.get("instance_token")
            or cfg.get("apikey")
            or cfg.get("api_key")
            or cfg.get("apiKey")
            or ""
        ).strip()
    )
    
    uazapi_mode = ""
    if provider_id == "uazapi":
        uazapi_mode = str(cfg.get("uazapi_mode") or cfg.get("uazapiMode") or cfg.get("mode") or "").strip().lower()
    
    uazapi_admin_token_present = bool(
        str(
            cfg.get("admintoken")
            or cfg.get("admin_token")
            or cfg.get("globalApikey")
            or cfg.get("global_apikey")
            or os.getenv("UAZAPI_ADMIN_TOKEN")
            or ""
        ).strip()
    )
    allow_admin_flow = provider_id == "uazapi" and uazapi_admin_token_present
    
    if provider_id == "uazapi" and uazapi_mode == "create" and not uazapi_admin_token_present:
        raise HTTPException(status_code=400, detail="Uazapi não configurada (admintoken).")

    async def _create_and_get_qr() -> Dict[str, Any]:
        webhook_url = _resolve_provider_webhook_url(request, provider_id, instance_name)
        local_conn_ref = conn_ref
        
        # Para UAZAPI, verificar se a instância já existe
        if provider_id == "uazapi":
            try:
                existing_instances = await provider.list_instances(ctx, connection=conn_ref)
                existing_token = None
                
                if isinstance(existing_instances, list):
                    for inst in existing_instances:
                        if isinstance(inst, dict):
                            inst_name = str(
                                inst.get("name") or inst.get("instanceName") or 
                                inst.get("instance_name") or inst.get("instance") or ""
                            ).strip().lower()
                            if inst_name == instance_name.lower():
                                existing_token = _extract_uazapi_instance_token(inst)
                                logger.info(f"UAZAPI instance '{instance_name}' already exists, reusing token")
                                break
                elif isinstance(existing_instances, dict):
                    instances_list = existing_instances.get("instances") or existing_instances.get("data") or []
                    if isinstance(instances_list, list):
                        for inst in instances_list:
                            if isinstance(inst, dict):
                                inst_name = str(
                                    inst.get("name") or inst.get("instanceName") or
                                    inst.get("instance_name") or inst.get("instance") or ""
                                ).strip().lower()
                                if inst_name == instance_name.lower():
                                    existing_token = _extract_uazapi_instance_token(inst)
                                    logger.info(f"UAZAPI instance '{instance_name}' already exists, reusing token")
                                    break
                
                if existing_token:
                    merged_cfg = dict(local_conn_ref.config or {})
                    merged_cfg["token"] = existing_token
                    supabase.table("connections").update({"config": merged_cfg}).eq("id", connection_id).execute()
                    local_conn_ref = ConnectionRef(
                        tenant_id=local_conn_ref.tenant_id,
                        provider=local_conn_ref.provider,
                        instance_name=local_conn_ref.instance_name,
                        phone_number=local_conn_ref.phone_number,
                        config=merged_cfg,
                    )
                    
                    # Verificar se já está conectado
                    try:
                        state = await provider.get_connection_state(ctx, connection=local_conn_ref)
                        if isinstance(state, dict) and _is_connected_state(provider_id, state):
                            try:
                                await provider.ensure_webhook(ctx, connection=local_conn_ref, webhook_url=webhook_url)
                                supabase.table("connections").update({"webhook_url": webhook_url}).eq("id", connection_id).execute()
                            except Exception as e:
                                logger.warning(f"Could not set webhook: {e}")
                            
                            supabase.table("connections").update({"status": "connected"}).eq("id", connection_id).execute()
                            return {"success": True, "message": "Instância já conectada! Configuração atualizada."}
                    except Exception as e:
                        logger.warning(f"Error checking existing instance: {e}")
                    
                    try:
                        await provider.ensure_webhook(ctx, connection=local_conn_ref, webhook_url=webhook_url)
                        supabase.table("connections").update({"webhook_url": webhook_url}).eq("id", connection_id).execute()
                    except Exception as e:
                        logger.warning(f"Could not set webhook: {e}")
                    
                    qr_result = await container.connections.connect_with_retries(
                        provider, connection=local_conn_ref, correlation_id=f"connect_existing:{connection_id}"
                    )
                    qrcode = _extract_qrcode_value(qr_result)
                    pairing_code = qr_result.get("pairingCode") or qr_result.get("code")
                    
                    if qrcode:
                        supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
                        return {"success": True, "message": "Escaneie o QR Code para conectar", "qrcode": qrcode, "pairingCode": pairing_code}
                    if pairing_code:
                        supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
                        return {"success": True, "message": "Use o código de pareamento para conectar", "pairingCode": pairing_code}
            except Exception as e:
                logger.warning(f"Could not check existing UAZAPI instances: {e}")
        
        if provider_id == "uazapi" and uazapi_mode != "create":
            raise HTTPException(status_code=404, detail="Instância não encontrada na Uazapi.")
        
        # Criar nova instância
        create_result = await provider.create_instance(ctx, connection=conn_ref, webhook_url=webhook_url)
        
        if provider_id == "uazapi":
            token = _extract_uazapi_instance_token(create_result)
            if token:
                merged_cfg = dict(local_conn_ref.config or {})
                merged_cfg["token"] = token
                supabase.table("connections").update({"config": merged_cfg}).eq("id", connection_id).execute()
                local_conn_ref = ConnectionRef(
                    tenant_id=local_conn_ref.tenant_id,
                    provider=local_conn_ref.provider,
                    instance_name=local_conn_ref.instance_name,
                    phone_number=local_conn_ref.phone_number,
                    config=merged_cfg,
                )
                
                try:
                    await provider.ensure_webhook(ctx, connection=local_conn_ref, webhook_url=webhook_url)
                    supabase.table("connections").update({"webhook_url": webhook_url}).eq("id", connection_id).execute()
                except Exception as e:
                    logger.warning(f"Could not set webhook: {e}")

        qrcode = _extract_qrcode_value(create_result)
        pairing_code = create_result.get("pairingCode") or create_result.get("code")
        
        if not qrcode:
            qr_result = await container.connections.connect_with_retries(
                provider, connection=local_conn_ref, correlation_id=f"connect_after_create:{connection_id}"
            )
            qrcode = _extract_qrcode_value(qr_result)
            pairing_code = qr_result.get("pairingCode") or qr_result.get("code")

        if not qrcode and not pairing_code:
            raise HTTPException(status_code=502, detail="Instância criada, mas não foi possível obter QR Code.")

        supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
        
        if pairing_code and not qrcode:
            return {"success": True, "message": "Use o código de pareamento para conectar", "pairingCode": pairing_code}
        
        return {"success": True, "message": "Instância criada! Escaneie o QR Code para conectar", "qrcode": qrcode, "pairingCode": pairing_code}

    # Check current state
    state: Optional[Dict[str, Any]] = None
    if provider_id != "uazapi" or token_present:
        try:
            state = await provider.get_connection_state(ctx, connection=conn_ref)
        except Exception as e:
            logger.warning(f"Could not get connection state for {instance_name}: {e}")

    if isinstance(state, dict) and _is_connected_state(provider_id, state):
        webhook_url = _resolve_provider_webhook_url(request, provider_id, instance_name)
        try:
            await provider.ensure_webhook(ctx, connection=conn_ref, webhook_url=webhook_url)
        except Exception as e:
            logger.warning(f"Could not set webhook for {instance_name}: {e}")
        supabase.table("connections").update({"status": "connected", "webhook_url": webhook_url}).eq("id", connection_id).execute()
        return {"success": True, "message": "Conexão estabelecida com sucesso!"}

    if not token_present and provider_id == "uazapi" and not allow_admin_flow:
        raise HTTPException(status_code=400, detail="Uazapi não configurada (token ou admintoken).")

    try:
        if token_present:
            qr_result = await container.connections.connect_with_retries(
                provider, connection=conn_ref, correlation_id=f"connect:{connection_id}"
            )
            qrcode = _extract_qrcode_value(qr_result)
            pairing_code = qr_result.get("pairingCode") or qr_result.get("code")
            
            if qrcode:
                supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
                return {"success": True, "message": "Escaneie o QR Code para conectar", "qrcode": qrcode, "pairingCode": pairing_code}
            if pairing_code:
                supabase.table("connections").update({"status": "connecting"}).eq("id", connection_id).execute()
                return {"success": True, "message": "Use o código de pareamento para conectar", "pairingCode": pairing_code}
        
        if allow_admin_flow:
            return await _create_and_get_qr()
        
        raise HTTPException(status_code=502, detail="Não foi possível obter QR Code ou código.")
    except Exception as e:
        if allow_admin_flow and not token_present:
            try:
                return await _create_and_get_qr()
            except Exception as e2:
                raise _whatsapp_http_error(e2)
        raise _whatsapp_http_error(e)


@router.get("/{connection_id}/qrcode")
async def get_qrcode(connection_id: str, payload: dict = Depends(verify_token)):
    """Get QR code for a provider connection."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )
    
    container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"qrcode:{connection_id}",
    )

    try:
        provider = _get_whatsapp_provider(provider_id)
        qr_result = await container.connections.connect_with_retries(
            provider, connection=conn_ref, correlation_id=f"connect:{connection_id}"
        )
        qrcode = _extract_qrcode_value(qr_result)
        return {"qrcode": qrcode, "pairingCode": qr_result.get("pairingCode"), "code": qr_result.get("code")}
    except Exception as e:
        raise _whatsapp_http_error(e)


@router.post("/{connection_id}/sync")
async def sync_connection_status(connection_id: str, request: Request, payload: dict = Depends(verify_token)):
    """Sync connection status with provider."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    
    conn_ref = ConnectionRef(
        tenant_id=str(connection.get("tenant_id") or ""),
        provider=provider_id,
        instance_name=instance_name,
        phone_number=str(connection.get("phone_number") or "") or None,
        config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
    )
    
    _container, ctx = _make_provider_ctx(
        tenant_id=conn_ref.tenant_id,
        provider=provider_id,
        instance_name=instance_name,
        correlation_id=f"sync:{connection_id}",
    )

    try:
        provider = _get_whatsapp_provider(provider_id)
        state = await provider.get_connection_state(ctx, connection=conn_ref)
        new_status = _get_connection_status(provider_id, state if isinstance(state, dict) else {})
        is_connected = new_status == "connected"
        
        update_data: Dict[str, Any] = {"status": new_status}
        existing_webhook_url = str(connection.get("webhook_url") or "").strip()
        
        if new_status == "disconnected":
            update_data["webhook_url"] = ""
        
        if is_connected:
            desired_webhook_url = _resolve_provider_webhook_url(request, provider_id, instance_name)
            if _is_local_webhook_url(desired_webhook_url) and existing_webhook_url and not _is_local_webhook_url(existing_webhook_url):
                desired_webhook_url = existing_webhook_url
            update_data['webhook_url'] = desired_webhook_url
            
            should_force_uazapi_webhook_update = False
            if provider_id == "uazapi":
                cfg = connection.get("config") if isinstance(connection.get("config"), dict) else {}
                should_force_uazapi_webhook_update = not bool(
                    cfg.get("uazapi_webhook_url_params") or cfg.get("uazapiWebhookUrlParams")
                )
                if should_force_uazapi_webhook_update:
                    update_data["config"] = {**cfg, "uazapi_webhook_url_params": True}

            if desired_webhook_url and (desired_webhook_url != existing_webhook_url or should_force_uazapi_webhook_update):
                try:
                    await provider.ensure_webhook(ctx, connection=conn_ref, webhook_url=desired_webhook_url)
                except Exception as e:
                    logger.warning(f"Could not set webhook for {instance_name}: {e}")
        
        result = supabase.table('connections').update(update_data).eq('id', connection_id).execute()
        
        c = result.data[0] if result.data else connection
        return {
            'id': c['id'],
            'status': new_status,
            'instanceState': (state.get('instance', {}) or {}).get('state', '') if isinstance(state, dict) else '',
            'phoneNumber': c.get('phone_number'),
            'message': f"Status atualizado para: {new_status}"
        }
        
    except Exception as e:
        logger.error(f"Error syncing connection status: {e}")
        raise _whatsapp_http_error(e)


@router.patch("/{connection_id}/status")
async def update_connection_status(connection_id: str, status_update: ConnectionStatusUpdate, payload: dict = Depends(verify_token)):
    """Update connection status."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = supabase.table('connections').select('id, tenant_id').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and conn.data[0].get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    data: Dict[str, Any] = {'status': status_update.status}
    if status_update.status == 'disconnected':
        data['webhook_url'] = ''
    
    result = supabase.table('connections').update(data).eq('id', connection_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    c = result.data[0]
    return {
        'id': c['id'],
        'tenantId': c['tenant_id'],
        'provider': c['provider'],
        'instanceName': c['instance_name'],
        'phoneNumber': c['phone_number'],
        'status': c['status'],
        'webhookUrl': c['webhook_url'],
        'config': c['config'],
        'createdAt': c['created_at']
    }


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str, payload: dict = Depends(verify_token)):
    """Delete a connection and its provider instance."""
    if payload.get('role') not in ['admin', 'superadmin']:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    conn = supabase.table('connections').select('*').eq('id', connection_id).execute()
    if not conn.data:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    
    connection = conn.data[0]
    user_tenant_id = _get_user_tenant_id(payload)
    if payload.get('role') != 'superadmin' and user_tenant_id and connection.get('tenant_id') != user_tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    tenant_id = connection['tenant_id']
    
    provider_id = str(connection.get("provider") or "").strip().lower()
    instance_name = str(connection.get("instance_name") or "").strip()
    
    if provider_id and instance_name:
        conn_ref = ConnectionRef(
            tenant_id=str(connection.get("tenant_id") or ""),
            provider=provider_id,
            instance_name=instance_name,
            phone_number=str(connection.get("phone_number") or "") or None,
            config=connection.get("config") if isinstance(connection.get("config"), dict) else {},
        )
        _container, ctx = _make_provider_ctx(
            tenant_id=conn_ref.tenant_id,
            provider=provider_id,
            instance_name=instance_name,
            correlation_id=f"conn_delete:{connection_id}",
        )
        try:
            provider = _get_whatsapp_provider(provider_id)
            await provider.delete_instance(ctx, connection=conn_ref)
            logger.info(f"Provider instance deleted: provider={provider_id} instance={instance_name}")
        except Exception as e:
            logger.warning(f"Could not delete provider instance: provider={provider_id} instance={instance_name} err={e}")
    
    # Update tenant connections count
    tenant = supabase.table('tenants').select('connections_count').eq('id', tenant_id).execute()
    if tenant.data and tenant.data[0]['connections_count'] > 0:
        new_count = tenant.data[0]['connections_count'] - 1
        supabase.table('tenants').update({'connections_count': new_count}).eq('id', tenant_id).execute()
    
    # Delete connection from database
    supabase.table('connections').delete().eq('id', connection_id).execute()
    return {"success": True}
