"""
Contacts routes extracted from server.py.

This module contains all contact management endpoints:
- GET /contacts - List contacts
- POST /contacts - Create contact
- GET /contacts/by-phone - Get by phone
- GET /contacts/{id} - Get contact
- PATCH /contacts/{id} - Update contact
- DELETE /contacts/{id} - Delete contact
"""

import uuid as uuid_module
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from ..supabase_client import supabase
    from ..models import ContactCreate, ContactUpdate
    from ..utils.auth_helpers import verify_token
    from ..utils.db_helpers import (
        db_call_with_retry,
        is_transient_db_error,
        is_supabase_not_configured_error,
        is_missing_table_or_schema_error,
        cache_contact_row,
        get_contacts_cache_by_tenant,
        get_contact_cache_by_id,
        get_contact_cache_by_tenant_phone,
        queue_db_write,
    )
    from ..utils.phone_utils import normalize_phone_number
except ImportError:
    from supabase_client import supabase
    from models import ContactCreate, ContactUpdate
    from utils.auth_helpers import verify_token
    from utils.db_helpers import (
        db_call_with_retry,
        is_transient_db_error,
        is_supabase_not_configured_error,
        is_missing_table_or_schema_error,
        cache_contact_row,
        get_contacts_cache_by_tenant,
        get_contact_cache_by_id,
        get_contact_cache_by_tenant_phone,
        queue_db_write,
    )
    from utils.phone_utils import normalize_phone_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["Contacts"])

# Cache references
_CONTACTS_CACHE_BY_TENANT = get_contacts_cache_by_tenant()
_CONTACT_CACHE_BY_ID = get_contact_cache_by_id()
_CONTACT_CACHE_BY_TENANT_PHONE = get_contact_cache_by_tenant_phone()


def _get_user_tenant_id(payload: dict) -> Optional[str]:
    """Get tenant ID from user payload."""
    if payload.get('role') == 'superadmin':
        return None
    return payload.get('tenant_id')


def _format_contact(c: dict) -> dict:
    """Format contact for API response."""
    return {
        'id': c.get('id'),
        'tenantId': c.get('tenant_id'),
        'name': c.get('name') or c.get('full_name'),
        'phone': c.get('phone'),
        'email': c.get('email'),
        'tags': c.get('tags') or [],
        'customFields': c.get('custom_fields') or {},
        'socialLinks': c.get('social_links') or {},
        'notesHtml': c.get('notes_html') or '',
        'status': c.get('status'),
        'firstContactAt': c.get('first_contact_at'),
        'source': c.get('source'),
        'createdAt': c.get('created_at'),
        'updatedAt': c.get('updated_at')
    }


@router.get("")
async def list_contacts(
    tenant_id: Optional[str] = Query(None),
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    payload: dict = Depends(verify_token)
):
    """List all contacts for the tenant."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id or tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        query = supabase.table('contacts').select('*').eq('tenant_id', effective_tenant_id)

        if search:
            search_term = f"%{search}%"
            query = query.or_(f"name.ilike.{search_term},phone.ilike.{search_term},email.ilike.{search_term}")

        try:
            result = db_call_with_retry(
                "contacts.list",
                lambda: query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            )
        except Exception as e:
            if is_transient_db_error(e) or is_missing_table_or_schema_error(e, "contacts"):
                cached = _CONTACTS_CACHE_BY_TENANT.get(str(effective_tenant_id))
                if isinstance(cached, dict) and isinstance(cached.get("data"), list):
                    return {
                        'contacts': cached.get("data") or [],
                        'total': cached.get("total") or len(cached.get("data") or []),
                        'limit': limit,
                        'offset': offset,
                        'cached': True
                    }
                return {'contacts': [], 'total': 0, 'limit': limit, 'offset': offset}
            raise

        contacts = []
        for c in (result.data or []):
            cache_contact_row(c)
            contacts.append(_format_contact(c))

        total = len(result.data or [])
        try:
            count_result = db_call_with_retry(
                "contacts.count",
                lambda: supabase.table('contacts').select('id', count='exact').eq('tenant_id', effective_tenant_id).execute()
            )
            if hasattr(count_result, 'count') and count_result.count:
                total = count_result.count
        except Exception:
            pass

        _CONTACTS_CACHE_BY_TENANT[str(effective_tenant_id)] = {
            "data": contacts,
            "total": total,
            "cached_at": datetime.utcnow().isoformat(),
        }

        return {'contacts': contacts, 'total': total, 'limit': limit, 'offset': offset}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing contacts: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar contatos: {str(e)}")


@router.post("")
async def create_contact(
    data: ContactCreate,
    tenant_id: Optional[str] = Query(None),
    payload: dict = Depends(verify_token),
):
    """Create a new contact."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)
        effective_tenant_id = user_tenant_id or tenant_id
        if not effective_tenant_id:
            raise HTTPException(status_code=403, detail="Tenant não identificado")

        name = (data.name or '').strip()
        raw_phone = (data.phone or '').strip()

        if not name or len(name) < 2 or len(name) > 100:
            raise HTTPException(status_code=400, detail="Nome deve ter entre 2 e 100 caracteres")
        if not raw_phone:
            raise HTTPException(status_code=400, detail="Telefone é obrigatório")

        phone = normalize_phone_number(raw_phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Telefone é inválido")

        # Check if contact already exists
        existing = db_call_with_retry(
            "contacts.exists",
            lambda: supabase.table('contacts').select('id').eq('tenant_id', effective_tenant_id).eq('phone', phone).limit(1).execute()
        )
        if existing.data:
            raise HTTPException(status_code=400, detail="Já existe um contato com este telefone")

        insert_data = {
            'tenant_id': effective_tenant_id,
            'name': name,
            'phone': phone,
            'email': (data.email or '').strip() or None,
            'tags': data.tags or [],
            'custom_fields': data.custom_fields or {},
            'source': data.source or 'manual',
            'status': 'verified',
            'first_contact_at': datetime.utcnow().isoformat()
        }

        result = db_call_with_retry(
            "contacts.insert",
            lambda: supabase.table('contacts').insert(insert_data).execute()
        )

        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar contato")

        c = result.data[0]
        cache_contact_row(c)
        return _format_contact(c)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar contato: {str(e)}")


@router.get("/by-phone")
async def get_contact_by_phone(tenant_id: str, phone: str, payload: dict = Depends(verify_token)):
    """Get contact by phone number."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)
        if user_tenant_id and tenant_id != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        normalized_phone = normalize_phone_number(phone) or phone.strip()
        if not normalized_phone:
            raise HTTPException(status_code=400, detail="Telefone inválido")

        try:
            existing = db_call_with_retry(
                "contacts.get_by_phone",
                lambda: supabase.table('contacts').select('*').eq('tenant_id', tenant_id).eq('phone', normalized_phone).limit(1).execute()
            )
            if existing.data:
                c = existing.data[0]
                cache_contact_row(c)
                return _format_contact(c)
        except Exception as e:
            if is_transient_db_error(e):
                cached = _CONTACT_CACHE_BY_TENANT_PHONE.get(f"{tenant_id}:{normalized_phone}")
                if isinstance(cached, dict):
                    return {**_format_contact(cached), 'cached': True}

        # Return empty contact
        return {
            'id': None,
            'tenantId': tenant_id,
            'phone': normalized_phone,
            'name': normalized_phone,
            'email': None,
            'tags': [],
            'customFields': {},
            'status': 'pending',
            'isNew': True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_contact_by_phone: {e}")
        return {'id': None, 'tenantId': tenant_id, 'phone': phone, 'isNew': True}


@router.get("/{contact_id}")
async def get_contact(contact_id: str, payload: dict = Depends(verify_token)):
    """Get a single contact by ID."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)

        try:
            uuid_module.UUID(contact_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        result = db_call_with_retry(
            "contacts.get",
            lambda: supabase.table('contacts').select('*').eq('id', contact_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        c = result.data[0]
        cache_contact_row(c)
        
        if user_tenant_id and c.get('tenant_id') != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        return _format_contact(c)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar contato: {str(e)}")


@router.patch("/{contact_id}")
async def update_contact(contact_id: str, data: ContactUpdate, payload: dict = Depends(verify_token)):
    """Update a contact by ID."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)

        result = supabase.table('contacts').select('*').eq('id', contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        c = result.data[0]
        if user_tenant_id and c.get('tenant_id') != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        update_data: Dict[str, Any] = {'updated_at': datetime.utcnow().isoformat()}
        
        if data.name is not None:
            update_data['name'] = data.name.strip()
        if data.phone is not None:
            update_data['phone'] = normalize_phone_number(data.phone) or data.phone.strip()
        if data.email is not None:
            update_data['email'] = data.email.strip() or None
        if data.tags is not None:
            update_data['tags'] = data.tags
        if data.custom_fields is not None:
            update_data['custom_fields'] = data.custom_fields
        if data.status is not None:
            update_data['status'] = data.status

        updated = supabase.table('contacts').update(update_data).eq('id', contact_id).execute()
        if not updated.data:
            raise HTTPException(status_code=400, detail="Erro ao atualizar contato")

        return _format_contact(updated.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar contato: {str(e)}")


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, payload: dict = Depends(verify_token)):
    """Delete a contact by ID."""
    try:
        user_tenant_id = _get_user_tenant_id(payload)

        result = supabase.table('contacts').select('tenant_id').eq('id', contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contato não encontrado")

        if user_tenant_id and result.data[0].get('tenant_id') != user_tenant_id:
            raise HTTPException(status_code=403, detail="Acesso negado")

        supabase.table('contacts').delete().eq('id', contact_id).execute()
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao excluir contato: {str(e)}")
