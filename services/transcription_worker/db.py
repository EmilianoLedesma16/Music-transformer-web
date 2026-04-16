import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_engine  = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)


def update_creacion(creacion_id: int, **kwargs) -> None:
    if not kwargs:
        return
    set_clauses  = ", ".join(f"{k} = :{k}" for k in kwargs)
    set_clauses += ", updated_at = now()"
    kwargs["creacion_id"] = creacion_id
    with _Session() as session:
        session.execute(
            text(f"UPDATE creaciones SET {set_clauses} WHERE id = :creacion_id"),
            kwargs,
        )
        session.commit()
