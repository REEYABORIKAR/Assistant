import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from refyne.db.models import User, Tenant, TenantMember, AuditEvent, File, Requirement, WorkflowDefinition
from refyne.auth.service import record_audit
from refyne.telemetry_service import get_tenant_telemetry_stats, record_token_usage

SETTINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "admin_settings")
os.makedirs(SETTINGS_DIR, exist_ok=True)

DEFAULT_ENGINE_SETTINGS = {
    "primary_model": "qwen/qwen3.8-27b",
    "fallback_model": "openai/gpt-oss-120b",
    "secondary_fallback": "llama-3.3-70b-versatile",
    "temperature": 0.2,
    "max_tokens": 4096,
    "ocr_confidence_threshold": 80,
    "saif_strict_mode": True,
    "rtm_auto_generation": True,
    "custom_system_directive": "You are REFYNE, an elite Enterprise AI Requirements Engineering and Architectural Quality Assessor adhering to ISO/IEC/IEEE 29148 and OWASP/SAIF standards."
}


def _get_engine_file(tenant_id: str) -> str:
    safe_id = "".join([c for c in str(tenant_id) if c.isalnum() or c in "-_"]) or "default"
    return os.path.join(SETTINGS_DIR, f"engine_{safe_id}.json")


def _get_roles_file(tenant_id: str) -> str:
    safe_id = "".join([c for c in str(tenant_id) if c.isalnum() or c in "-_"]) or "default"
    return os.path.join(SETTINGS_DIR, f"roles_{safe_id}.json")


def _load_tenant_roles(tenant_id: str) -> Dict[str, str]:
    filepath = _get_roles_file(tenant_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_tenant_roles(tenant_id: str, roles_map: Dict[str, str]) -> None:
    filepath = _get_roles_file(tenant_id)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(roles_map, f, indent=2)
    except Exception:
        pass


def get_engine_settings(tenant_id: str) -> Dict[str, Any]:
    filepath = _get_engine_file(tenant_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                saved = json.load(f)
                return {**DEFAULT_ENGINE_SETTINGS, **saved}
        except Exception:
            pass
    return dict(DEFAULT_ENGINE_SETTINGS)


def update_engine_settings(tenant_id: str, new_settings: Dict[str, Any]) -> Dict[str, Any]:
    filepath = _get_engine_file(tenant_id)
    current = get_engine_settings(tenant_id)
    merged = {**current, **new_settings}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    return merged


def list_workspace_users(db: Session, tenant_id: uuid.UUID) -> List[Dict[str, Any]]:
    # Get all tenant members
    query = (
        select(User, TenantMember.status.label("member_status"), TenantMember.created_at.label("member_since"))
        .join(TenantMember, TenantMember.user_id == User.id)
        .where(TenantMember.tenant_id == tenant_id)
        .order_by(TenantMember.created_at.asc())
    )
    rows = db.execute(query).all()
    roles_map = _load_tenant_roles(str(tenant_id))
    
    results = []
    for idx, (user, member_status, member_since) in enumerate(rows):
        user_id_str = str(user.id)
        # Default role: first member is ADMIN, others default to ENGINEER
        assigned_role = roles_map.get(user_id_str, "ADMIN" if idx == 0 else "ENGINEER")
        results.append({
            "id": user_id_str,
            "name": user.name or user.email.split("@")[0].capitalize(),
            "email": user.email,
            "role": assigned_role,
            "status": member_status or user.status or "ACTIVE",
            "member_since": member_since.isoformat() if member_since else datetime.now(timezone.utc).isoformat()
        })
    return results


def invite_workspace_user(db: Session, tenant_id: uuid.UUID, email: str, name: str, role: str, actor_id: uuid.UUID) -> Dict[str, Any]:
    user = db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email.strip().lower(),
            name=name.strip() if name else email.split("@")[0].capitalize(),
            password_hash="INVITED_PENDING_ACTIVATION",
            status="ACTIVE"
        )
        db.add(user)
        db.flush()

    member = db.execute(
        select(TenantMember).where(TenantMember.tenant_id == tenant_id, TenantMember.user_id == user.id)
    ).scalar_one_or_none()

    if member is None:
        member = TenantMember(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user.id,
            status="ACTIVE",
            joined_at=datetime.now(timezone.utc)
        )
        db.add(member)
    else:
        member.status = "ACTIVE"

    db.commit()
    
    # Save role in mapping
    roles_map = _load_tenant_roles(str(tenant_id))
    roles_map[str(user.id)] = (role or "ENGINEER").upper()
    _save_tenant_roles(str(tenant_id), roles_map)
    
    record_audit(db, event_type="WORKSPACE_USER_INVITED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=user.id)

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": roles_map[str(user.id)],
        "status": user.status,
        "member_since": datetime.now(timezone.utc).isoformat()
    }


def update_user_role(db: Session, tenant_id: uuid.UUID, target_user_id: uuid.UUID, new_role: str, actor_id: uuid.UUID) -> bool:
    member = db.execute(
        select(TenantMember).where(TenantMember.tenant_id == tenant_id, TenantMember.user_id == target_user_id)
    ).scalar_one_or_none()

    if member is None:
        return False

    roles_map = _load_tenant_roles(str(tenant_id))
    roles_map[str(target_user_id)] = new_role.upper()
    _save_tenant_roles(str(tenant_id), roles_map)
    
    record_audit(db, event_type="WORKSPACE_USER_ROLE_UPDATED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=target_user_id)
    return True


def remove_workspace_user(db: Session, tenant_id: uuid.UUID, target_user_id: uuid.UUID, actor_id: uuid.UUID) -> bool:
    member = db.execute(
        select(TenantMember).where(TenantMember.tenant_id == tenant_id, TenantMember.user_id == target_user_id)
    ).scalar_one_or_none()

    if member is None:
        return False

    db.delete(member)
    db.commit()
    
    roles_map = _load_tenant_roles(str(tenant_id))
    if str(target_user_id) in roles_map:
        del roles_map[str(target_user_id)]
        _save_tenant_roles(str(tenant_id), roles_map)

    record_audit(db, event_type="WORKSPACE_USER_REMOVED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=target_user_id)
    return True


def get_audit_trail(db: Session, tenant_id: uuid.UUID, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type.upper())
    query = query.order_by(desc(AuditEvent.created_at)).limit(limit)

    rows = db.execute(query).scalars().all()
    results = []
    for evt in rows:
        results.append({
            "id": str(evt.id),
            "event_type": evt.event_type,
            "actor_type": evt.actor_type,
            "actor_id": str(evt.actor_id) if evt.actor_id else None,
            "resource_type": evt.resource_type,
            "resource_id": str(evt.resource_id) if evt.resource_id else None,
            "outcome": evt.outcome,
            "metadata": evt.metadata_json or {},
            "timestamp": evt.created_at.isoformat() if evt.created_at else datetime.now(timezone.utc).isoformat()
        })
    return results


def get_resource_usage(db: Session, tenant_id: uuid.UUID) -> Dict[str, Any]:
    return get_tenant_telemetry_stats(str(tenant_id), db)
