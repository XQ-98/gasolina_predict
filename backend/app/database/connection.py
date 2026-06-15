"""Conexion a la base de datos PostgreSQL.

Configura el engine de SQLAlchemy, la sesion y la base declarativa.
Si PostgreSQL no esta disponible, las funciones que dependan de la BD
simplemente no se ejecutaran (el sistema tiene fallback).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import os
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://gaspredict:gaspredict2026@localhost:5436/gaspredict"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Generador de sesiones de base de datos para dependency injection en FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
