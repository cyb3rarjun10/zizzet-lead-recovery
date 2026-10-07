from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Tenant


def get_current_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> Optional[str]:
    return x_tenant_id


def get_or_create_tenant(db: Session, tenant_id: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, name=f"Tenant {tenant_id}")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant