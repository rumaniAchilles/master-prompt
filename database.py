import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, desc
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Definición Base del ORM (Object-Relational Mapping)
Base = declarative_base()

class SuccessTactic(Base):
    __tablename__ = 'success_tactics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    family = Column(String, index=True) # Indexado para búsquedas ultrarrápidas
    tactic = Column(Text)
    score = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class FailedTactic(Base):
    __tablename__ = 'failed_tactics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    family = Column(String, index=True)
    tactic = Column(Text)
    errors = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class OptimizationJob(Base):
    """Tabla para trackear el estado de la orquestación en tiempo real."""
    __tablename__ = 'optimization_jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    family = Column(String, index=True, unique=True) # Un trabajo activo por familia
    status = Column(String) # "in_progress", "completed", "failed"
    score = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentMemory:
    def __init__(self):
        """
        Inicializa la conexión preparada para Alto Tráfico.
        En producción, DATABASE_URL debe ser una base de datos real (PostgreSQL/MySQL).
        Ejemplo: postgresql://usuario:password@localhost:5432/achilles_db
        """
        # Fallback a SQLite para desarrollo local
        self.db_url = os.getenv("DATABASE_URL", "sqlite:///./agent_memory.db")
        
        # Configuraciones especiales dependiendo del motor
        connect_args = {}
        if self.db_url.startswith("sqlite"):
            # Permite múltiples hilos en SQLite (necesario para FastAPI)
            connect_args = {"check_same_thread": False}
            
        # 2. El Motor con "Connection Pooling"
        # pool_pre_ping verifica que la conexión siga viva antes de usarla
        self.engine = create_engine(
            self.db_url, 
            connect_args=connect_args,
            pool_pre_ping=True
        )
        
        # Crea las tablas si no existen en el motor seleccionado
        Base.metadata.create_all(bind=self.engine)
        
        # Fábrica de sesiones para interactuar con la DB
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_best_tactic(self, family):
        """Busca la mejor táctica histórica para esta familia."""
        family_id = str(family).strip().lower()
        with self.SessionLocal() as session:
            res = session.query(SuccessTactic)\
                .filter(SuccessTactic.family == family_id)\
                .order_by(desc(SuccessTactic.score), desc(SuccessTactic.timestamp))\
                .first()
            return res.tactic if res else None

    def save_success(self, family, tactic, score):
        """Guarda una táctica exitosa."""
        family_id = str(family).strip().lower()
        try:
            with self.SessionLocal() as session:
                new_success = SuccessTactic(family=family_id, tactic=tactic, score=score)
                session.add(new_success)
                session.commit()
        except Exception as e:
            print(f"⚠️ Error al guardar éxito en DB: {e}")

    def save_failure(self, family, tactic, errors):
        """Registra un fallo para evitar repetir la misma estrategia."""
        family_id = str(family).strip().lower()
        try:
            with self.SessionLocal() as session:
                new_fail = FailedTactic(
                    family=family_id, 
                    tactic=tactic, 
                    errors=json.dumps(errors)
                )
                session.add(new_fail)
                session.commit()
        except Exception as e:
            print(f"⚠️ Error al guardar fallo en DB: {e}")
    
    def get_recent_failures(self, family):
        """Recupera las últimas 5 tácticas fallidas de la familia."""
        family_id = str(family).strip().lower()
        with self.SessionLocal() as session:
            res = session.query(FailedTactic)\
                .filter(FailedTactic.family == family_id)\
                .order_by(desc(FailedTactic.timestamp))\
                .limit(5)\
                .all()
            return [r.tactic for r in res]

    def clear_family_memory(self, family):
        """Limpia el historial de una familia específica."""
        family_id = str(family).strip().lower()
        with self.SessionLocal() as session:
            session.query(SuccessTactic).filter(SuccessTactic.family == family_id).delete()
            session.query(FailedTactic).filter(FailedTactic.family == family_id).delete()
            session.commit()
        print(f"🧹 Memoria borrada para la familia: {family_id}")

    def create_or_update_job(self, family, status, score=0.0):
        """Crea o actualiza el estado de un trabajo de optimización."""
        family_id = str(family).strip().lower()
        with self.SessionLocal() as session:
            job = session.query(OptimizationJob).filter(OptimizationJob.family == family_id).first()
            if job:
                job.status = status
                job.score = score
            else:
                job = OptimizationJob(family=family_id, status=status, score=score)
                session.add(job)
            session.commit()

    def get_job_status(self, family):
        """Devuelve el estado actual para que lo lea el front-end."""
        family_id = str(family).strip().lower()
        with self.SessionLocal() as session:
            job = session.query(OptimizationJob).filter(OptimizationJob.family == family_id).first()
            if job:
                return {"family_id": job.family, "status": job.status, "score": job.score, "last_update": job.updated_at}
            return None