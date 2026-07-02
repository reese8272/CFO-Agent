from __future__ import annotations
import asyncio
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_session
from auth import get_current_user
from vault.crud import write_audit_log
from vault.models import Transaction, ImportBatch, CategoryMapping
from vault.schemas import ImportBatchRead, CategoryMappingCreate, CategoryMappingRead
from integrations.csv_import import parse_csv, parse_ofx, compute_hash, _apply_mappings_raw

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/import", tags=["import"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[str, Depends(get_current_user)]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/transactions", response_model=ImportBatchRead, status_code=status.HTTP_201_CREATED)
async def import_transactions(
    account_id: int,
    file: UploadFile = File(...),
    *,
    session: Session,
    _user: CurrentUser,
):
    if (file.size or 0) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 10 MB)")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (max 10 MB)")
    fname = file.filename or "upload"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "csv"
    # Parse untrusted upload off the event loop; any parse failure is a 422, not a 500.
    try:
        if ext in ("ofx", "qfx"):
            rows = await asyncio.to_thread(parse_ofx, content)
            file_format = "ofx"
        else:
            rows = await asyncio.to_thread(parse_csv, content)
            file_format = "csv"
    except Exception as exc:
        logger.warning("import parse failed (%s): %s", fname, exc)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "could not parse the uploaded file"
        ) from exc

    result = await session.execute(select(CategoryMapping))
    mappings = result.scalars().all()

    batch = ImportBatch(
        account_id=account_id,
        filename=fname,
        file_format=file_format,
        row_count=len(rows),
    )
    session.add(batch)
    await session.flush()
    await write_audit_log(session, _user.username, "create", "import_batch", batch.id, None, {"filename": fname, "format": file_format})

    inserted = 0
    for row in rows:
        h = compute_hash(account_id, row.occurred_at, row.amount, row.description)
        dup = await session.execute(select(Transaction).where(Transaction.import_hash == h))
        if dup.scalar_one_or_none():
            continue
        cat = _apply_mappings_raw(row.description, mappings)
        txn = Transaction(
            account_id=account_id,
            occurred_at=row.occurred_at,
            amount=row.amount,
            description=row.description,
            category=cat,
            import_hash=h,
            import_batch_id=batch.id,
        )
        session.add(txn)
        await session.flush()
        await write_audit_log(session, _user.username, "create", "transaction", txn.id, None, {"import_batch_id": batch.id})
        inserted += 1

    batch.row_count = inserted
    await session.commit()
    await session.refresh(batch)
    return batch


@router.get("/category-mappings", response_model=list[CategoryMappingRead])
async def list_category_mappings(session: Session, _user: CurrentUser):
    result = await session.execute(select(CategoryMapping).order_by(CategoryMapping.id))
    return result.scalars().all()


@router.post(
    "/category-mappings",
    response_model=CategoryMappingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_mapping(
    body: CategoryMappingCreate, session: Session, _user: CurrentUser
):
    mapping = CategoryMapping(pattern=body.pattern, category=body.category)
    session.add(mapping)
    await session.commit()
    await session.refresh(mapping)
    return mapping


@router.delete("/category-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_mapping(mapping_id: int, session: Session, _user: CurrentUser):
    result = await session.execute(
        select(CategoryMapping).where(CategoryMapping.id == mapping_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404)
    await session.delete(obj)
    await session.commit()
