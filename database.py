import sqlite3
import json

class AgentMemory:
    def __init__(self):
        # check_same_thread=False permite que LangGraph/Streamlit accedan a la DB desde distintos hilos sin crashear
        self.conn = sqlite3.connect("agent_memory.db", check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("CREATE TABLE IF NOT EXISTS success_tactics (family TEXT, tactic TEXT, score REAL)")
        # CAMBIO: Cambiamos doc_id por family
        self.conn.execute("CREATE TABLE IF NOT EXISTS failed_tactics (family TEXT, tactic TEXT, errors TEXT)")
        self.conn.commit()

    def get_best_tactic(self, family):
        """
        Busca la mejor táctica histórica para esta familia documental.
        Retorna: La táctica (str) O None si no existe historial.
        """
        cursor = self.conn.cursor()
        res = cursor.execute(
            "SELECT tactic FROM success_tactics WHERE family = ? ORDER BY score DESC LIMIT 1", 
            (family,)
        ).fetchone()
        
        # --- CORRECCIÓN CRÍTICA ---
        # Antes devolvía un string por defecto, lo que engañaba al main.py.
        # Ahora devuelve None para que el sistema sepa que es un caso nuevo (Cold Start).
        return res[0] if res else None

    def save_success(self, family, tactic, score):
        self.conn.execute(
            "INSERT INTO success_tactics (family, tactic, score) VALUES (?, ?, ?)", 
            (family, tactic, score)
        )
        self.conn.commit()

    # Ajusta los métodos para usar 'family'
    def save_failure(self, family, tactic, errors):
        self.conn.execute(
            "INSERT INTO failed_tactics (family, tactic, errors) VALUES (?, ?, ?)", 
            (family, tactic, json.dumps(errors))
        )
        self.conn.commit()
    
    def get_recent_failures(self, family):
        """Recupera las tácticas tóxicas de TODA la familia."""
        res = self.conn.execute(
            "SELECT tactic FROM failed_tactics WHERE family = ? ORDER BY rowid DESC LIMIT 5", 
            (family,)
        ).fetchall()
        return [r[0] for r in res]

    def clear_family_memory(self, family):
        """
        UTILIDAD: Úsala si guardaste basura por error en una familia.
        Ej: db.clear_family_memory("6496")
        """
        self.conn.execute("DELETE FROM success_tactics WHERE family = ?", (family,))
        self.conn.commit()
        print(f"🧹 Memoria borrada para la familia: {family}")