"""
Minimal helper to update the generations table from within the ml_worker.
Uses raw SQL to avoid importing api-specific models.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_engine  = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)


def update_generation(gen_id, **kwargs):
    if not kwargs:
        return
    set_clauses  = ", ".join("{} = :{}".format(k, k) for k in kwargs)
    set_clauses += ", updated_at = now()"
    kwargs["gen_id"] = gen_id
    with _Session() as session:
        session.execute(
            text("UPDATE generations SET {} WHERE id = :gen_id".format(set_clauses)),
            kwargs,
        )
        session.commit()
