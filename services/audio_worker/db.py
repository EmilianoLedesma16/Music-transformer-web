"""
Minimal helper to update the generations table from within a worker.
Does NOT import SQLAlchemy models (avoids pulling in api-only deps).
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_engine  = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)


def update_generation(gen_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clauses  = ", ".join(f"{k} = :{k}" for k in kwargs)
    set_clauses += ", updated_at = now()"
    kwargs["gen_id"] = gen_id
    with _Session() as session:
        session.execute(
            text(f"UPDATE generations SET {set_clauses} WHERE id = :gen_id"),
            kwargs,
        )
        session.commit()
