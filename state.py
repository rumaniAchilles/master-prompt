from typing import TypedDict, List, Dict, Optional, Any

class AgentState(TypedDict):
    # --- Identificación y Metadatos del Request ---
    family: str
    id_document_type: str  # Requerido por document-analyzer
    id_user: str           # Requerido por document-analyzer
    company_id: str        # Requerido para el guardado final (Handoff)
    
    # --- Modo Batch (Lotes de prueba) ---
    # Cada ítem del batch es un dict: { "case_id": str, "images": [str], "expected_data": {}, "raw_truth": str }
    batch_queue: List[Dict[str, Any]] 
    
    # --- El Corazón del Prompt Builder ---
    parameters: Dict[str, Any]   # Diccionario que cumple con ParameterDetail
    original_prompt: str         # El prompt base con {{placeholders}}
    current_tactic: str          # La estrategia de corrección actual (también con placeholders)
    
    # --- Estado de Ejecución y Resultados ---
    # Almacenará el feedback estructurado que devuelva AnalyzeResponse
    batch_results: Dict[str, Dict] 
    
    # Métricas Globales (Promedio de la familia)
    avg_score: float
    mismatches: List[str]        # Errores extraídos del analyzer ("approved" vs "rejected")
    
    # --- Control de Flujo ---
    attempts: int
    is_final: bool
    
    # --- Histórico de sesión (para Hill Climbing) ---
    best_avg_score: float
    best_tactic: str
    best_parameters: Dict[str, Any] # Guardamos el mejor config de parámetros
    tried_tactics: List[str]
    semantic_context: str