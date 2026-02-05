from typing import TypedDict, List, Dict, Optional, Any

class AgentState(TypedDict):
    # --- Identificación ---
    family: str
    
    # --- Modo Batch (Lotes) ---
    # En lugar de un solo caso, tenemos una lista de casos activos
    # Cada ítem del batch es un dict: { "case_id": str, "images": [], "ground_truth": {}, "raw_truth": str }
    batch_queue: List[Dict[str, Any]] 
    
    # --- Prompt Maestro ---
    original_prompt: str         # El prompt base (sin reglas dinámicas)
    current_tactic: str          # La estrategia de corrección actual
    
    # --- Estado de Ejecución (Resultados Agregados) ---
    # Resultados por caso: { "case_id": { "extraction": {}, "score": 0.0, "mismatches": [] } }
    batch_results: Dict[str, Dict] 
    
    # Métricas Globales (Promedio de la familia)
    avg_score: float
    
    # Datos compartidos (Reglas aprendidas)
    rules: Optional[Dict]
    
    # Control de Flujo
    attempts: int
    is_final: bool
    
    # Histórico de sesión (para Hill Climbing)
    best_avg_score: float
    best_tactic: str
    tried_tactics: List[str]