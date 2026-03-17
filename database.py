import sqlite3
import json
import sys
from pathlib import Path

class AgentMemory:
    def __init__(self):
        # 1. Localización Robusta (Integración con el Paso 2)
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parent
            
        self.db_path = base_path / "agent_memory.db"
        
        # 2. Conexión con Timeout y Aislamiento
        # timeout=20: Si la base de datos está ocupada, espera hasta 20 segundos antes de fallar.
        self.conn = sqlite3.connect(
            str(self.db_path), 
            check_same_thread=False, 
            timeout=20 
        )
        # WAL Mode: Permite que varios hilos lean mientras uno escribe, evitando bloqueos.
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._init_db()

    def _init_db(self):
        """Inicializa las tablas si no existen."""
        with self.conn: # Usar contexto 'with' asegura que se haga commit automáticamente
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS success_tactics 
                (family TEXT, tactic TEXT, score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS failed_tactics 
                (family TEXT, tactic TEXT, errors TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
            """)

    def get_best_tactic(self, family):
        """Busca la mejor táctica histórica para esta familia."""
        family_id = str(family).strip().lower()
        cursor = self.conn.cursor()
        res = cursor.execute(
            "SELECT tactic FROM success_tactics WHERE family = ? ORDER BY score DESC, timestamp DESC LIMIT 1", 
            (family_id,)
        ).fetchone()
        return res[0] if res else None

    def save_success(self, family, tactic, score):
        """Guarda una táctica exitosa."""
        family_id = str(family).strip().lower()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO success_tactics (family, tactic, score) VALUES (?, ?, ?)", 
                    (family_id, tactic, score)
                )
        except sqlite3.Error as e:
            print(f"⚠️ Error al guardar éxito en DB: {e}")

    def save_failure(self, family, tactic, errors):
        """Registra un fallo para evitar repetir la misma estrategia."""
        family_id = str(family).strip().lower()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO failed_tactics (family, tactic, errors) VALUES (?, ?, ?)", 
                    (family_id, tactic, json.dumps(errors))
                )
        except sqlite3.Error as e:
            print(f"⚠️ Error al guardar fallo en DB: {e}")
    
    def get_recent_failures(self, family):
        """Recupera las últimas tácticas fallidas de la familia."""
        family_id = str(family).strip().lower()
        res = self.conn.execute(
            "SELECT tactic FROM failed_tactics WHERE family = ? ORDER BY timestamp DESC LIMIT 5", 
            (family_id,)
        ).fetchall()
        return [r[0] for r in res]

    def clear_family_memory(self, family):
        """Limpia el historial de una familia específica."""
        family_id = str(family).strip().lower()
        with self.conn:
            self.conn.execute("DELETE FROM success_tactics WHERE family = ?", (family_id,))
            self.conn.execute("DELETE FROM failed_tactics WHERE family = ?", (family_id,))
        print(f"🧹 Memoria borrada para la familia: {family_id}")