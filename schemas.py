from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union

# ==============================================================================
# 1. SCHEMAS PARA EL REQUEST DE ANÁLISIS (PromptBuilderRequest)
# ==============================================================================

class LinkedKey(BaseModel):
    key: str
    rules: dict = Field(default_factory=dict)
    condition: str  # Ej: "approve_if_both_are_approved"

class ComparisonOperationParameterDate(BaseModel):
    select_type_date: str  # Ej: "current_date", "exact_date"
    date_exact: Optional[str] = None
    count_date_type: int
    time_unit: str  # Ej: "days", "months", "years"

class ParameterDetail(BaseModel):
    """
    Representa el diccionario 'parameters' que cumple el triple rol:
    1. Resuelve placeholders {{key:name}} y {{key:value}}
    2. Genera el JSON schema del LLM
    3. Valida post-proceso
    """
    name: str
    value: str
    data_type: str = "string"  # "string", "date", "integer"
    condition: str = "required"  # "required", "optional"
    comparison_operation: str
    # Puede ser null, un float/int (para letras de diferencia), un string, o un dict (para fechas v3)
    comparison_operation_parameter: Optional[Union[ComparisonOperationParameterDate, float, int, str, dict, list]] = None
    linked_keys: List[LinkedKey] = Field(default_factory=list)
    normalizers: Optional[List[str]] = None  # Ej: ["resolve_arithmetic"]

class PromptBuilderRequest(BaseModel):
    """Payload exacto que se envía al POST /api/v1/analyzer/prompt-builder"""
    file: str  # base64_encoded_pdf
    mime_type: str = "application/pdf"
    prompt: List[str]  # Prompts secuenciales CON {{placeholders}}
    parameters: Dict[str, ParameterDetail]
    id_document_type: str
    id_user: str


# ==============================================================================
# 2. SCHEMAS PARA EL RESPONSE DE ANÁLISIS (AnalyzeResponse)
# ==============================================================================

class AnalyzeResponseField(BaseModel):
    value: str
    confidence: float
    status: str  # "approved" o "rejected"

class AnalyzeResponseDocument(BaseModel):
    docType: str
    confidence: float
    status: str  # "approved" o "rejected"
    fields: Dict[str, AnalyzeResponseField]

class AnalyzeResponseDetails(BaseModel):
    apiVersion: str
    modelId: str
    documents: List[AnalyzeResponseDocument]

class AnalyzeResponse(BaseModel):
    """Respuesta esperada tras la prueba del prompt en el document-analyzer"""
    status: str  # "approved" si todos los required son approved, sino "rejected"
    details: AnalyzeResponseDetails


# ==============================================================================
# 3. SCHEMAS PARA EL GUARDADO FINAL (El "Handoff" interno)
# ==============================================================================

class ComparisonConfigItem(BaseModel):
    """
    Es idéntico a ParameterDetail pero SIN 'name' y SIN 'value'.
    Se guarda en la DB para futuras ejecuciones reales.
    """
    key: str
    comparison_operation: str
    comparison_operation_parameter: Optional[Union[ComparisonOperationParameterDate, float, int, str, dict, list]] = None
    data_type: str
    condition: str
    linked_keys: List[LinkedKey] = Field(default_factory=list)
    normalizers: Optional[List[str]] = None

class PromptItem(BaseModel):
    content: str
    prompt_name: str

class PromptGroupCreate(BaseModel):
    """Payload exacto para POST /api/v1/prompts/groups"""
    name: str
    active: int = 0
    document_type_id: str
    company_id: str
    llm_model: str  # Ej: "gravity", "mercurio"
    comparison_config: List[ComparisonConfigItem]
    prompts: List[PromptItem]

class PromptGroupSimpleOut(BaseModel):
    """Respuesta esperada al guardar el grupo"""
    id_prompt_group: str
    name: str
    active: int
    document_type_id: str
    company_id: str