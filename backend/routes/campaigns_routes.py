"""
Campaigns routes extracted from server.py.

This module contains all campaign management endpoints:
- GET/POST /bulk-campaigns - List/Create campaigns
- PUT/DELETE /bulk-campaigns/{id} - Update/Delete
- POST /bulk-campaigns/{id}/recipients - Set recipients
- POST /bulk-campaigns/{id}/schedule - Schedule
- POST /bulk-campaigns/{id}/pause|resume|cancel - Control
- GET /bulk-campaigns/{id}/stats - Statistics
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

try:
    from ..supabase_client import supabase
    from ..models import (
        BulkCampaignCreate,
        BulkCampaignUpdate,
        BulkCampaignRecipientsSet,
        BulkCampaignSchedule,
    )
    from ..utils.auth_helpers import verify_token
except ImportError:
    from supabase_client import supabase
    from models import (
        BulkCampaignCreate,
        BulkCampaignUpdate,
        BulkCampaignRecipientsSet,
        BulkCampaignSchedule,
    )
    from utils.auth_helpers import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bulk-campaigns", tags=["Campaigns"])


def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
    """Check if exception indicates missing table."""
    s = str(exc or "").lower()
    return table_name.lower() in s and ("does not exist" in s or "not found" in s or "pgrst" in s)


def _bulk_campaigns_missing_table_http(table: str):
    """Return HTTP exception for missing campaigns table."""
    return HTTPException(
        status_code=503,
        detail=f"Tabela {table} não existe. Execute a migração de campanhas."
    )


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime from string or return None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value).strip()
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# ==================== BULK CAMPAIGNS ====================

@router.get("")
async def list_bulk_campaigns(tenant_id: str, payload: dict = Depends(verify_token)):
    """List all bulk campaigns for tenant."""
    try:
        result = (
            supabase.table("bulk_campaigns")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(200)
            .execute()
        )
        return result.data or []
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
async def create_bulk_campaign(tenant_id: str, data: BulkCampaignCreate, payload: dict = Depends(verify_token)):
    """Create a new bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        row = {
            "tenant_id": tenant_id,
            "created_by": payload.get("user_id"),
            "name": data.name,
            "template_body": data.template_body,
            "connection_id": data.connection_id,
            "status": "draft",
            "selection_mode": data.selection_mode,
            "selection_payload": data.selection_payload or {},
            "delay_seconds": int(data.delay_seconds or 0),
            "start_at": data.start_at,
            "recurrence": data.recurrence or "none",
            "next_run_at": None,
            "max_messages_per_period": data.max_messages_per_period,
            "period_unit": data.period_unit,
            "created_at": now,
            "updated_at": now,
        }
        result = supabase.table("bulk_campaigns").insert(row).execute()
        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar campanha")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{campaign_id}")
async def update_bulk_campaign(campaign_id: str, data: BulkCampaignUpdate, payload: dict = Depends(verify_token)):
    """Update a bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        update_data: Dict[str, Any] = {"updated_at": now}
        for k in (
            "name",
            "template_body",
            "connection_id",
            "selection_mode",
            "selection_payload",
            "delay_seconds",
            "start_at",
            "recurrence",
            "max_messages_per_period",
            "period_unit",
            "status",
        ):
            v = getattr(data, k, None)
            if v is not None:
                update_data[k] = v
        result = supabase.table("bulk_campaigns").update(update_data).eq("id", campaign_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{campaign_id}")
async def delete_bulk_campaign(campaign_id: str, payload: dict = Depends(verify_token)):
    """Delete a bulk campaign."""
    try:
        supabase.table("bulk_campaigns").delete().eq("id", campaign_id).execute()
        return {"success": True}
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/recipients")
async def set_bulk_campaign_recipients(
    campaign_id: str,
    tenant_id: str,
    data: BulkCampaignRecipientsSet,
    payload: dict = Depends(verify_token)
):
    """Set recipients for a bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        ids = [str(x).strip() for x in (data.contact_ids or []) if str(x).strip()]
        ids = list(dict.fromkeys(ids))
        result = (
            supabase.table("bulk_campaigns")
            .update({
                "selection_mode": "explicit",
                "selection_payload": {"contact_ids": ids},
                "updated_at": now,
            })
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/schedule")
async def schedule_bulk_campaign(
    campaign_id: str,
    tenant_id: str,
    data: BulkCampaignSchedule,
    payload: dict = Depends(verify_token)
):
    """Schedule a bulk campaign."""
    try:
        now_dt = datetime.utcnow()
        now = now_dt.isoformat()
        start_dt = _parse_datetime(data.start_at) or now_dt
        next_run_at = start_dt.isoformat()
        update_data: Dict[str, Any] = {
            "status": "scheduled",
            "start_at": start_dt.isoformat(),
            "next_run_at": next_run_at,
            "updated_at": now,
        }
        if data.recurrence is not None:
            update_data["recurrence"] = data.recurrence
        if data.delay_seconds is not None:
            update_data["delay_seconds"] = int(data.delay_seconds or 0)
        if data.max_messages_per_period is not None:
            update_data["max_messages_per_period"] = data.max_messages_per_period
        if data.period_unit is not None:
            update_data["period_unit"] = data.period_unit
        result = (
            supabase.table("bulk_campaigns")
            .update(update_data)
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/pause")
async def pause_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Pause a bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "paused", "paused_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/resume")
async def resume_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Resume a paused bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "scheduled", "paused_at": None, "next_run_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/cancel")
async def cancel_bulk_campaign(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Cancel a bulk campaign."""
    try:
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("bulk_campaigns")
            .update({"status": "cancelled", "cancelled_at": now, "updated_at": now})
            .eq("id", campaign_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        # Cancel pending recipients
        try:
            supabase.table("bulk_campaign_recipients").update({
                "status": "skipped",
                "error": "Campanha cancelada",
                "updated_at": now
            }).eq("campaign_id", campaign_id).eq("status", "scheduled").execute()
        except Exception:
            pass
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{campaign_id}/stats")
async def bulk_campaign_stats(campaign_id: str, tenant_id: str, payload: dict = Depends(verify_token)):
    """Get statistics for a bulk campaign."""
    try:
        campaign_r = supabase.table("bulk_campaigns").select("*").eq("id", campaign_id).eq("tenant_id", tenant_id).limit(1).execute()
        if not campaign_r.data:
            raise HTTPException(status_code=404, detail="Campanha não encontrada")
        campaign = campaign_r.data[0]

        def count_status(status: str) -> int:
            try:
                r = supabase.table("bulk_campaign_recipients").select("id", count="exact").eq("campaign_id", campaign_id).eq("status", status).execute()
                return int(getattr(r, "count", 0) or 0)
            except Exception:
                return 0

        totals = {
            "scheduled": count_status("scheduled"),
            "sending": count_status("sending"),
            "sent": count_status("sent"),
            "failed": count_status("failed"),
            "skipped": count_status("skipped"),
        }

        # If no recipients yet, count from selection_payload
        if sum(totals.values()) == 0:
            selection_mode = str(campaign.get("selection_mode") or "").lower()
            selection_payload = campaign.get("selection_payload") or {}
            if selection_mode == "explicit" and isinstance(selection_payload, dict):
                raw_ids = selection_payload.get("contact_ids") or []
                if isinstance(raw_ids, list):
                    totals["scheduled"] = len(raw_ids)

        # Get last run
        run = None
        try:
            run_r = supabase.table("bulk_campaign_runs").select("*").eq("campaign_id", campaign_id).order("created_at", desc=True).limit(1).execute()
            if run_r.data:
                run = run_r.data[0]
        except Exception:
            pass

        return {"campaign": campaign, "totals": totals, "lastRun": run}
    except HTTPException:
        raise
    except Exception as e:
        if _is_missing_table_error(e, "bulk_campaigns"):
            raise _bulk_campaigns_missing_table_http("bulk_campaigns")
        raise HTTPException(status_code=400, detail=str(e))
