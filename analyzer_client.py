import os
import requests
from typing import Dict, Any
from schemas import PromptBuilderRequest, AnalyzeResponse, PromptGroupCreate, PromptGroupSimpleOut

class AnalyzerClient:
    """
    Cliente oficial para comunicarse con el servicio interno 'document-analyzer'.
    Maneja el endpoint de prueba de prompts, el guardado final, y el modo Mock.
    """

    def __init__(self):
        # Configuraciones leídas desde variables de entorno
        self.base_url = os.getenv("ANALYZER_BASE_URL", "http://localhost:8000")
        self.token = os.getenv("ANALYZER_API_TOKEN", "dummy-dev-token")
        
        # MOCK_MODE en True evita llamadas de red y devuelve respuestas dummy
        self.mock_mode = os.getenv("MOCK_MODE", "True").lower() in ("true", "1", "yes")

    # =========================================================================
    # 1. PRUEBA Y ORQUESTACIÓN (POST /api/v1/analyzer/prompt-builder)
    # =========================================================================
    def test_prompt(self, request_payload: PromptBuilderRequest) -> AnalyzeResponse:
        """
        Envía el prompt y los parameters al endpoint de análisis para ser evaluado.
        """
        if self.mock_mode:
            print("      [MOCK MODE ACTIVO] 🛡️ Simulando respuesta del document-analyzer...")
            return self._get_mock_response(request_payload)

        endpoint = f"{self.base_url}/api/v1/analyzer/prompt-builder"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                endpoint, 
                json=request_payload.model_dump(), 
                headers=headers,
                timeout=60
            )
            response.raise_for_status() 
            return AnalyzeResponse(**response.json())

        except requests.exceptions.HTTPError as http_err:
            print(f"❌ Error HTTP del Analyzer: {http_err.response.text}")
            raise
        except Exception as e:
            print(f"❌ Error de conexión con el Analyzer: {e}")
            raise

    # =========================================================================
    # 2. ENTREGA FINAL / HANDOFF (POST /api/v1/prompts/groups)
    # =========================================================================
    def save_prompt_group(self, request_payload: PromptGroupCreate) -> PromptGroupSimpleOut:
        """
        Guarda definitivamente el template aprobado y su configuración de comparadores
        en la base de datos principal de document-analyzer.
        """
        if self.mock_mode:
            print("      [MOCK MODE ACTIVO] 🛡️ Simulando guardado exitoso de Prompt Group...")
            # Devolvemos una respuesta falsa de éxito basándonos en los datos enviados
            return PromptGroupSimpleOut(
                id_prompt_group="mock-pg-uuid-001",
                name=request_payload.name,
                active=request_payload.active,
                document_type_id=request_payload.document_type_id,
                company_id=request_payload.company_id
            )

        endpoint = f"{self.base_url}/api/v1/prompts/groups"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                endpoint, 
                json=request_payload.model_dump(), 
                headers=headers,
                timeout=30 
            )
            response.raise_for_status() 
            return PromptGroupSimpleOut(**response.json())

        except requests.exceptions.HTTPError as http_err:
            print(f"❌ Error HTTP guardando Prompt Group: {http_err.response.text}")
            raise
        except Exception as e:
            print(f"❌ Error de conexión guardando Prompt Group: {e}")
            raise

    # =========================================================================
    # 3. DATOS DE SIMULACIÓN (MOCKS)
    # =========================================================================
    def _get_mock_response(self, request_payload: PromptBuilderRequest) -> AnalyzeResponse:
        """Devuelve la respuesta Dummy exacta documentada en la sección 2 del manual."""
        dummy_response = {
            "status": "approved",
            "details": {
                "apiVersion": "1.0",
                "modelId": "gravity",
                "documents": [
                    {
                        "docType": "Certificado de Seguro",
                        "confidence": 0.92,
                        "status": "approved",
                        "fields": {
                            "nombre_asegurado": {
                                "value": "Achilles Information Ltd",
                                "confidence": 0.98,
                                "status": "approved"
                            },
                            "numero_poliza": {
                                "value": "770541799",
                                "confidence": 0.95,
                                "status": "approved"
                            },
                            "fecha_emision": {
                                "value": "2025-01-15",
                                "confidence": 0.90,
                                "status": "approved"
                            },
                            "fecha_vencimiento": {
                                "value": "2026-06-15",
                                "confidence": 0.88,
                                "status": "approved"
                            },
                            "monto_asegurado": {
                                "value": "500000.00",
                                "confidence": 0.85,
                                "status": "approved"
                            }
                        }
                    }
                ]
            }
        }
        return AnalyzeResponse(**dummy_response)