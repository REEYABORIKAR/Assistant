import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from refyne.auth.credentials import generate_token, hash_password, hash_token, verify_password
from refyne.auth.policy import RegistrationRequest
from refyne.auth.tokens import create_access_token
from refyne.config import Settings
from refyne.db.models import (
    AuditEvent,
    Consent,
    Conversation,
    File,
    IdempotencyKey,
    Message,
    PasswordResetToken,
    Project,
    Requirement,
    RequirementLink,
    Risk,
    WorkflowDefinition,
    RefreshToken,
    Session as AuthSession,
    Tenant,
    TenantMember,
    User,
)


class AuthenticationError(ValueError):
    pass


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"tenant-{uuid.uuid4().hex[:12]}"


def register_user(db: Session, request: RegistrationRequest, settings: Settings) -> User:
    request.validate_consents_and_confirmation()
    email = str(request.email).lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise AuthenticationError("account could not be created")

    tenant = Tenant(slug=_slugify(request.name), name=f"{request.name}'s workspace", status="ACTIVE")
    user = User(email=email, password_hash=hash_password(request.password), name=request.name, status="ACTIVE")
    db.add_all([tenant, user])
    db.flush()
    db.add(
        TenantMember(
            tenant_id=tenant.id,
            user_id=user.id,
            status="ACTIVE",
            joined_at=datetime.now(timezone.utc),
        )
    )
    for kind in ("TERMS_OF_SERVICE", "PRIVACY_POLICY"):
        db.add(Consent(user_id=user.id, consent_kind=kind, policy_version="current", granted=True))
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str, settings: Settings) -> tuple[User, str, str, int]:
    if not settings.auth_signing_secret:
        raise RuntimeError("AUTH_SIGNING_SECRET must be configured")
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid email or password")
    membership = db.scalar(
        select(TenantMember).where(TenantMember.user_id == user.id, TenantMember.status == "ACTIVE")
    )
    if membership is None:
        raise AuthenticationError("invalid email or password")
    now = datetime.now(timezone.utc)
    session = AuthSession(
        tenant_id=membership.tenant_id,
        user_id=user.id,
        expires_at=now + timedelta(seconds=settings.access_token_ttl_seconds),
    )
    refresh_value = generate_token()
    db.add(session)
    db.flush()
    db.add(
        RefreshToken(
            session_id=session.id,
            token_hash=hash_token(refresh_value),
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    user.last_login_at = now
    db.commit()
    access_value = create_access_token(
        str(user.id), str(session.id), settings.auth_signing_secret, settings.access_token_ttl_seconds
    )
    return user, access_value, refresh_value, settings.access_token_ttl_seconds


def revoke_session(db: Session, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id))
    if session is None:
        raise AuthenticationError("session not found")
    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_reason = "USER_LOGOUT"
    db.commit()


def list_sessions(db: Session, user_id: uuid.UUID) -> list[AuthSession]:
    return list(
        db.scalars(select(AuthSession).where(AuthSession.user_id == user_id).order_by(AuthSession.issued_at.desc())).all()
    )


def get_authenticated_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> AuthSession:
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    )
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        raise AuthenticationError("invalid authentication")
    return session


def create_project(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
) -> Project:
    project = Project(
        tenant_id=tenant_id,
        project_key=f"PRJ-{uuid.uuid4().hex[:12].upper()}",
        name=name,
        description=description,
        status="ACTIVE",
        created_by=user_id,
    )
    db.add(project)
    db.flush()
    record_audit(
        db,
        event_type="PROJECT_CREATED",
        tenant_id=tenant_id,
        actor_id=user_id,
        session_id=None,
        resource_id=project.id,
    )
    db.refresh(project)
    return project


def get_project(db: Session, tenant_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
    return db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
            Project.deleted_at.is_(None),
        )
    )


def list_projects(db: Session, tenant_id: uuid.UUID, status_filter: str | None = None) -> list[Project]:
    query = select(Project).where(Project.tenant_id == tenant_id, Project.deleted_at.is_(None))
    if status_filter:
        query = query.where(Project.status == status_filter.upper())
    return list(db.scalars(query.order_by(Project.created_at.desc())).all())


def update_project(
    db: Session,
    project: Project,
    *,
    name: str | None,
    description: str | None,
    status: str | None,
    actor_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Project:
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if status is not None:
        if status.upper() not in {"ACTIVE", "ARCHIVED"}:
            raise AuthenticationError("invalid project status")
        project.status = status.upper()
    record_audit(
        db,
        event_type="PROJECT_UPDATED",
        tenant_id=tenant_id,
        actor_id=actor_id,
        session_id=None,
        resource_id=project.id,
    )
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project, actor_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    project.deleted_at = datetime.now(timezone.utc)
    project.status = "ARCHIVED"
    record_audit(
        db,
        event_type="PROJECT_DELETED",
        tenant_id=tenant_id,
        actor_id=actor_id,
        session_id=None,
        resource_id=project.id,
    )


def create_conversation(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, project_id: uuid.UUID | None, title: str | None
) -> Conversation:
    if project_id is not None and get_project(db, tenant_id, project_id) is None:
        raise AuthenticationError("project not found")
    conversation = Conversation(tenant_id=tenant_id, project_id=project_id, created_by=user_id, title=title)
    db.add(conversation)
    db.flush()
    record_audit(
        db,
        event_type="CONVERSATION_CREATED",
        tenant_id=tenant_id,
        actor_id=user_id,
        session_id=None,
        resource_id=conversation.id,
    )
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.deleted_at.is_(None),
        )
    )


def list_conversations(db: Session, tenant_id: uuid.UUID, project_id: uuid.UUID | None = None) -> list[Conversation]:
    query = select(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.deleted_at.is_(None))
    if project_id is not None:
        query = query.where(Conversation.project_id == project_id)
    return list(db.scalars(query.order_by(Conversation.updated_at.desc())).all())


def update_conversation(
    db: Session,
    conversation: Conversation,
    *,
    title: str | None,
    status: str | None,
    actor_id: uuid.UUID,
) -> Conversation:
    if title is not None:
        conversation.title = title
    if status is not None:
        normalized_status = status.upper()
        if normalized_status not in {"ACTIVE", "ARCHIVED"}:
            raise AuthenticationError("invalid conversation status")
        conversation.status = normalized_status
    record_audit(
        db,
        event_type="CONVERSATION_UPDATED",
        tenant_id=conversation.tenant_id,
        actor_id=actor_id,
        session_id=None,
        resource_id=conversation.id,
    )
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation: Conversation, actor_id: uuid.UUID) -> None:
    conversation.deleted_at = datetime.now(timezone.utc)
    conversation.status = "ARCHIVED"
    record_audit(
        db,
        event_type="CONVERSATION_DELETED",
        tenant_id=conversation.tenant_id,
        actor_id=actor_id,
        session_id=None,
        resource_id=conversation.id,
    )


def list_messages(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    return list(db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.sequence)).all())


def add_user_message(db: Session, conversation: Conversation, content: str, actor_id: uuid.UUID) -> Message:
    last_sequence = db.scalar(
        select(Message.sequence).where(Message.conversation_id == conversation.id).order_by(Message.sequence.desc()).limit(1)
    )
    message = Message(
        conversation_id=conversation.id,
        sequence=(last_sequence + 1 if last_sequence is not None else 0),
        role="USER",
        status="COMPLETE",
        content=content,
    )
    db.add(message)
    db.flush()
    record_audit(
        db,
        event_type="MESSAGE_SENT",
        tenant_id=conversation.tenant_id,
        actor_id=actor_id,
        session_id=None,
        resource_id=message.id,
    )
    db.refresh(message)
    return message


def list_files(db: Session, tenant_id: uuid.UUID, project_id: uuid.UUID | None = None) -> list[File]:
    query = select(File).where(File.tenant_id == tenant_id, File.deleted_at.is_(None))
    if project_id is not None:
        query = query.where(File.project_id == project_id)
    return list(db.scalars(query.order_by(File.created_at.desc())).all())


def get_file(db: Session, tenant_id: uuid.UUID, file_id: uuid.UUID) -> File | None:
    return db.scalar(select(File).where(File.id == file_id, File.tenant_id == tenant_id, File.deleted_at.is_(None)))


def create_requirement(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    requirement_type: str,
    title: str,
    description: str,
    requirement_key: str | None,
) -> Requirement:
    if get_project(db, tenant_id, project_id) is None:
        raise AuthenticationError("project not found")
    item = Requirement(
        tenant_id=tenant_id,
        project_id=project_id,
        requirement_key=requirement_key or f"REQ-{uuid.uuid4().hex[:12].upper()}",
        type=requirement_type.upper(),
        title=title,
        description=description,
        status="DRAFT",
        source_type="UNVERIFIED",
        created_by=user_id,
        missing_information=[],
    )
    db.add(item)
    db.flush()
    record_audit(db, event_type="REQUIREMENT_CREATED", tenant_id=tenant_id, actor_id=user_id, session_id=None, resource_id=item.id)
    db.refresh(item)
    return item


def list_requirements(
    db: Session, tenant_id: uuid.UUID, project_id: uuid.UUID | None = None, requirement_type: str | None = None,
    status_filter: str | None = None,
) -> list[Requirement]:
    query = select(Requirement).where(Requirement.tenant_id == tenant_id)
    if project_id is not None:
        query = query.where(Requirement.project_id == project_id)
    if requirement_type:
        query = query.where(Requirement.type == requirement_type.upper())
    if status_filter:
        query = query.where(Requirement.status == status_filter.upper())
    return list(db.scalars(query.order_by(Requirement.created_at.desc())).all())


def get_requirement(db: Session, tenant_id: uuid.UUID, requirement_id: uuid.UUID) -> Requirement | None:
    return db.scalar(select(Requirement).where(Requirement.id == requirement_id, Requirement.tenant_id == tenant_id))


def update_requirement(
    db: Session, item: Requirement, *, title: str | None, description: str | None, status: str | None, actor_id: uuid.UUID
) -> Requirement:
    if title is not None:
        item.title = title
    if description is not None:
        item.description = description
    if status is not None:
        normalized = status.upper()
        allowed = {"DRAFT", "PROPOSED", "ACCEPTED", "AMBIGUOUS", "DUPLICATE", "REJECTED", "OBSOLETE"}
        if normalized not in allowed:
            raise AuthenticationError("invalid requirement status")
        item.status = normalized
    record_audit(db, event_type="REQUIREMENT_UPDATED", tenant_id=item.tenant_id, actor_id=actor_id, session_id=None, resource_id=item.id)
    db.refresh(item)
    return item


def list_requirement_links(db: Session, tenant_id: uuid.UUID, requirement_id: uuid.UUID) -> list[RequirementLink]:
    links = db.scalars(
        select(RequirementLink).where(
            RequirementLink.source_requirement_id == requirement_id,
        )
    ).all()
    requirement_ids = {link.target_requirement_id for link in links}
    if requirement_ids:
        valid_ids = set(
            db.scalars(
                select(Requirement.id).where(
                    Requirement.tenant_id == tenant_id,
                    Requirement.id.in_(requirement_ids),
                )
            ).all()
        )
        links = [link for link in links if link.target_requirement_id in valid_ids]
    return list(links)


def create_requirement_link(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    source_requirement_id: uuid.UUID,
    target_requirement_id: uuid.UUID,
    relationship: str,
    actor_id: uuid.UUID,
) -> RequirementLink:
    if source_requirement_id == target_requirement_id:
        raise AuthenticationError("requirements must be distinct")
    source = get_requirement(db, tenant_id, source_requirement_id)
    target = get_requirement(db, tenant_id, target_requirement_id)
    if source is None or target is None:
        raise AuthenticationError("requirement not found")
    allowed = {"DERIVES_FROM", "DUPLICATES", "CONFLICTS_WITH", "REFINES", "DEPENDS_ON"}
    normalized = relationship.upper()
    if normalized not in allowed:
        raise AuthenticationError("invalid requirement relationship")
    existing = db.scalar(
        select(RequirementLink).where(
            RequirementLink.source_requirement_id == source_requirement_id,
            RequirementLink.target_requirement_id == target_requirement_id,
            RequirementLink.relationship == normalized,
        )
    )
    if existing is not None:
        raise AuthenticationError("requirement link already exists")
    link = RequirementLink(
        source_requirement_id=source_requirement_id,
        target_requirement_id=target_requirement_id,
        relationship=normalized,
    )
    db.add(link)
    db.flush()
    record_audit(db, event_type="TRACE_LINK_CREATED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=link.id)
    db.refresh(link)
    return link


def list_workflow_definitions(
    db: Session, tenant_id: uuid.UUID, status_filter: str | None = None
) -> list[WorkflowDefinition]:
    query = select(WorkflowDefinition).where(WorkflowDefinition.tenant_id == tenant_id)
    if status_filter:
        query = query.where(WorkflowDefinition.status == status_filter.upper())
    return list(db.scalars(query.order_by(WorkflowDefinition.created_at.desc())).all())


def get_workflow_definition(
    db: Session, tenant_id: uuid.UUID, workflow_definition_id: uuid.UUID
) -> WorkflowDefinition | None:
    return db.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == workflow_definition_id,
            WorkflowDefinition.tenant_id == tenant_id,
        )
    )


def record_audit(
    db: Session,
    *,
    event_type: str,
    tenant_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    outcome: str = "SUCCEEDED",
    resource_id: uuid.UUID | None = None,
) -> None:
    if event_type != event_type.upper():
        raise ValueError("audit event type must be uppercase")
    if outcome not in {"SUCCEEDED", "DENIED", "FAILED"}:
        raise ValueError("invalid audit outcome")
    if tenant_id is None and session_id is not None:
        session = db.get(AuthSession, session_id)
        if session is not None:
            tenant_id = session.tenant_id
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            actor_type="USER" if actor_id else "SYSTEM",
            actor_id=actor_id,
            resource_id=resource_id,
            session_id=session_id,
            outcome=outcome,
            metadata_json={},
        )
    )
    db.commit()


def issue_password_reset(db: Session, email: str, settings: Settings) -> str | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return None
    token = generate_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.password_reset_token_ttl_hours),
        )
    )
    db.commit()
    return token


def refresh_user(db: Session, refresh_value: str, settings: Settings) -> tuple[str, str, int]:
    if not settings.auth_signing_secret:
        raise RuntimeError("AUTH_SIGNING_SECRET must be configured")
    now = datetime.now(timezone.utc)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_value)))
    if stored is None or stored.used_at is not None or stored.revoked_at is not None or stored.expires_at <= now:
        raise AuthenticationError("invalid refresh token")
    session = db.get(AuthSession, stored.session_id)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AuthenticationError("invalid refresh token")
    user = db.get(User, session.user_id)
    if user is None:
        raise AuthenticationError("invalid refresh token")
    replacement_value = generate_token()
    replacement = RefreshToken(
        session_id=session.id,
        token_hash=hash_token(replacement_value),
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(replacement)
    db.flush()
    stored.used_at = now
    stored.replaced_by = replacement.id
    session.last_seen_at = now
    db.commit()
    access_value = create_access_token(
        str(user.id), str(session.id), settings.auth_signing_secret, settings.access_token_ttl_seconds
    )
    return access_value, replacement_value, settings.access_token_ttl_seconds


def reset_password(db: Session, token: str, new_password: str) -> None:
    now = datetime.now(timezone.utc)
    stored = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if stored is None or stored.used_at is not None or stored.expires_at <= now:
        raise AuthenticationError("invalid password reset token")
    user = db.get(User, stored.user_id)
    if user is None:
        raise AuthenticationError("invalid password reset token")
    user.password_hash = hash_password(new_password)
    stored.used_at = now
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update(
        {AuthSession.revoked_at: now, AuthSession.revoked_reason: "PASSWORD_RESET"}
    )
    db.commit()


def check_idempotency_key(
    db: Session, tenant_id: uuid.UUID, idempotency_key: str, endpoint: str, session_id: uuid.UUID
) -> tuple[int, dict[str, object]] | None:
    """Check if this request was already processed. Returns (status, response_body) if found, else None."""
    stored = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.idempotency_key == idempotency_key,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.session_id == session_id,
        )
    )
    if stored is None:
        return None
    return stored.response_status, stored.response_body


def store_idempotency_key(
    db: Session,
    tenant_id: uuid.UUID,
    idempotency_key: str,
    endpoint: str,
    session_id: uuid.UUID,
    status: int,
    response_body: dict[str, object],
) -> None:
    """Store the response for future duplicate requests."""
    db.add(
        IdempotencyKey(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            endpoint=endpoint,
            session_id=session_id,
            response_status=status,
            response_body=response_body,
        )
    )
    db.commit()


def delete_requirement(db: Session, item: Requirement, actor_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    db.delete(item)
    record_audit(db, event_type="REQUIREMENT_DELETED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=item.id)
    db.commit()


def calculate_severity_score(impact: str, likelihood: str) -> int:
    weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    imp_val = weights.get(impact.upper(), 2)
    lik_val = weights.get(likelihood.upper(), 2)
    # Severity score mapped from 1-16 to 1-100 percentage
    return int((imp_val * lik_val) / 16.0 * 100)


def list_risks(
    db: Session,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    impact: str | None = None,
    likelihood: str | None = None,
    status_filter: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> list[Risk]:
    query = select(Risk).where(Risk.tenant_id == tenant_id)
    if project_id is not None:
        query = query.where(Risk.project_id == project_id)
    if impact:
        query = query.where(Risk.impact == impact.upper())
    if likelihood:
        query = query.where(Risk.likelihood == likelihood.upper())
    if status_filter:
        query = query.where(Risk.status == status_filter.upper())
    if category:
        query = query.where(Risk.category == category.upper())
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Risk.title.ilike(search_pattern)) | (Risk.description.ilike(search_pattern)) | (Risk.risk_key.ilike(search_pattern))
        )
    return list(db.scalars(query.order_by(Risk.created_at.desc())).all())


def get_risk(db: Session, tenant_id: uuid.UUID, risk_id: uuid.UUID) -> Risk | None:
    return db.scalar(select(Risk).where(Risk.id == risk_id, Risk.tenant_id == tenant_id))


def create_risk(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    risk_key: str | None = None,
    title: str,
    description: str,
    impact: str = "MEDIUM",
    likelihood: str = "MEDIUM",
    status: str = "OPEN",
    category: str = "TECHNICAL",
    mitigation_strategy: str | None = None,
    contingency_plan: str | None = None,
    owner: str | None = None,
    associated_requirement_id: uuid.UUID | None = None,
) -> Risk:
    norm_impact = impact.upper() if impact else "MEDIUM"
    norm_likelihood = likelihood.upper() if likelihood else "MEDIUM"
    norm_status = status.upper() if status else "OPEN"
    norm_category = category.upper() if category else "TECHNICAL"
    
    if not risk_key:
        count = db.scalar(select(func.count(Risk.id)).where(Risk.tenant_id == tenant_id)) or 0
        risk_key = f"RSK-{101 + count}"

    score = calculate_severity_score(norm_impact, norm_likelihood)
    
    item = Risk(
        tenant_id=tenant_id,
        project_id=project_id,
        risk_key=risk_key,
        title=title,
        description=description,
        impact=norm_impact,
        likelihood=norm_likelihood,
        status=norm_status,
        category=norm_category,
        mitigation_strategy=mitigation_strategy,
        contingency_plan=contingency_plan,
        owner=owner,
        severity_score=score,
        associated_requirement_id=associated_requirement_id,
        created_by=user_id,
    )
    db.add(item)
    db.flush()
    record_audit(db, event_type="RISK_LOGGED", tenant_id=tenant_id, actor_id=user_id, session_id=None, resource_id=item.id)
    db.refresh(item)
    return item


def update_risk(
    db: Session,
    item: Risk,
    *,
    title: str | None = None,
    description: str | None = None,
    impact: str | None = None,
    likelihood: str | None = None,
    status: str | None = None,
    category: str | None = None,
    mitigation_strategy: str | None = None,
    contingency_plan: str | None = None,
    owner: str | None = None,
    actor_id: uuid.UUID,
) -> Risk:
    if title is not None:
        item.title = title
    if description is not None:
        item.description = description
    if impact is not None:
        item.impact = impact.upper()
    if likelihood is not None:
        item.likelihood = likelihood.upper()
    if status is not None:
        item.status = status.upper()
    if category is not None:
        item.category = category.upper()
    if mitigation_strategy is not None:
        item.mitigation_strategy = mitigation_strategy
    if contingency_plan is not None:
        item.contingency_plan = contingency_plan
    if owner is not None:
        item.owner = owner

    item.severity_score = calculate_severity_score(item.impact, item.likelihood)
    record_audit(db, event_type="RISK_UPDATED", tenant_id=item.tenant_id, actor_id=actor_id, session_id=None, resource_id=item.id)
    db.commit()
    db.refresh(item)
    return item


def delete_risk(db: Session, item: Risk, actor_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    db.delete(item)
    record_audit(db, event_type="RISK_DELETED", tenant_id=tenant_id, actor_id=actor_id, session_id=None, resource_id=item.id)
    db.commit()

