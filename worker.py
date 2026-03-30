import os
import shutil
import json
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional

# Importamos la inteligencia de Achilles
from app import app as langgraph_app
from detective import auto_generate_prompt_from_image

# Nuevas importaciones para la integración HTTP y Tracking
from analyzer_client import AnalyzerClient
from schemas import PromptGroupCreate
from database import AgentMemory

# Instanciamos los clientes globales para el Worker
analyzer_client = AnalyzerClient()
db = AgentMemory()

# Configuración de Smart Paging
MAX_PAGES_BEFORE_PRUNING = 5

def extract_images_to_temp(doc_path: str, temp_dir: str, expected_data: Dict) -> List[str]:
    """
    Convierte PDFs a imágenes (a 300 DPI) y las guarda EN LA CARPETA TEMPORAL.
    """
    image_paths = []
    suffix = os.path.splitext(doc_path)[1].lower()

    if suffix in [".jpg", ".jpeg", ".png", ".bmp"]:
        return [doc_path]
    
    elif suffix == ".pdf":
        try:
            doc = fitz.open(doc_path)
            total_pages = len(doc)
            
            pages_to_process = list(range(min(total_pages, MAX_PAGES_BEFORE_PRUNING)))
            if total_pages > MAX_PAGES_BEFORE_PRUNING and expected_data:
                pages_to_process = [0, total_pages - 1] 
            
            for i in pages_to_process:
                page = doc[i]
                pix = page.get_pixmap(dpi=300)
                output_path = os.path.join(temp_dir, f"page_{i}_{os.path.basename(doc_path)}.jpg")
                pix.save(output_path)
                image_paths.append(output_path)
            doc.close()
            return image_paths
        except Exception as e:
            print(f"❌ Error extrayendo imágenes de {doc_path}: {e}")
            return []
    return []

def process_optimization_task(
    family_id: str, 
    id_document_type: str,  
    id_user: str,           
    company_id: str,        # <--- NUEVO: Recibimos el company_id desde la API
    gt_data: Dict[str, Any], 
    original_prompt: Optional[str], 
    file_paths: List[str], 
    temp_dir: str
):
    """
    WORKER PRINCIPAL: Se ejecuta en segundo plano. Aisla el proceso de la API REST.
    """
    print(f"\n⚙️ [WORKER] Iniciando orquestación para la familia: {family_id}")
    
    try:
        # 1. PREPARACIÓN DEL LOTE (En memoria temporal)
        batch_queue = []
        for file_path in file_paths:
            imgs = extract_images_to_temp(file_path, temp_dir, gt_data)
            if imgs:
                batch_queue.append({
                    "case_id": os.path.basename(file_path),
                    "images": imgs,
                    "expected_data": gt_data, 
                    "raw_truth": str(gt_data)
                })

        if not batch_queue:
            raise ValueError("No se pudieron extraer imágenes válidas de los documentos proporcionados.")

        # 2. ARRANQUE EN FRÍO (Detective)
        if not original_prompt:
            print("🕵️‍♂️ [WORKER] Prompt original no proporcionado. Disparando Detective...")
            seed_case = batch_queue[0]
            original_prompt = auto_generate_prompt_from_image(seed_case["images"][0], seed_case["expected_data"])

        # 3. ESTADO INICIAL DEL GRAFO
        initial_state = {
            "family": family_id,
            "id_document_type": id_document_type,
            "id_user": id_user,
            "company_id": company_id,  # <--- INYECTAMOS EL DATO EN LA MEMORIA DE LANGGRAPH
            "batch_queue": batch_queue,
            "original_prompt": original_prompt,
            "current_tactic": "",
            "parameters": {},         
            "best_parameters": {},    
            "batch_results": {},
            "avg_score": 0.0,
            "mismatches": [],
            "attempts": 0,
            "is_final": False,
            "best_avg_score": 0.0,
            "best_tactic": None,
            "tried_tactics": [],
            "semantic_context": ""
        }

        # 4. EJECUCIÓN DEL GRAFO (El orquestador LangGraph)
        print("🔥 [WORKER] Ejecutando Grafo de Orquestación y Pruebas HTTP...")
        final_state = langgraph_app.invoke(initial_state)

        # 5. ENSAMBLAJE DEL ARTEFACTO FINAL
        print("📦 [WORKER] Empaquetando el JSON Final del Prompt Group...")
        score = final_state.get('best_avg_score', 0.0)
        
        # Unimos la táctica y el prompt original
        best_tactic = final_state.get('best_tactic', "")
        base_prompt = final_state.get('original_prompt', "")
        
        if best_tactic:
            final_prompt = f"{base_prompt}\n\n### SECTION 2: EXTRACTION TASKS (OPTIMIZED)\n{best_tactic}"
        else:
            final_prompt = base_prompt
            
        best_params = final_state.get('best_parameters', {})
        
        # 5.1 Construimos la lista comparison_config (Removiendo 'name' y 'value')
        comparison_config = []
        for key, param_detail in best_params.items():
            config_item = {
                "key": key,
                "comparison_operation": param_detail.get("comparison_operation", "equals"),
                "comparison_operation_parameter": param_detail.get("comparison_operation_parameter"),
                "data_type": param_detail.get("data_type", "string"),
                "condition": param_detail.get("condition", "required"),
                "linked_keys": param_detail.get("linked_keys", []),
                "normalizers": param_detail.get("normalizers")
            }
            comparison_config.append(config_item)

        # 5.2 Estructura oficial del Guardado usando nuestro Pydantic Schema
        payload_resultado = PromptGroupCreate(
            name=f"Prompt Builder Auto - {family_id}",
            active=0,
            document_type_id=id_document_type,
            company_id=company_id, # <--- Usamos el ID real que nos pasó la API
            llm_model="gravity", 
            comparison_config=comparison_config,
            prompts=[
                {
                    "content": final_prompt,
                    "prompt_name": "Extracción y Razonamiento Principal"
                }
            ]
        )
        
        # 6. EL HANDOFF OFICIAL (POST HTTP)
        print(f"🚀 [WORKER] Enviando Prompt Group final al document-analyzer...")
        response_handoff = analyzer_client.save_prompt_group(payload_resultado)
        print(f"✅ [WORKER] ¡Guardado exitoso! ID del Grupo generado: {response_handoff.id_prompt_group}")
        
        # (Opcional) Guardado local para debug
        os.makedirs("prompt_groups_output", exist_ok=True)
        ruta_guardado = f"prompt_groups_output/GROUP_{family_id}.json"
        with open(ruta_guardado, "w", encoding="utf-8") as f:
            # Pydantic v2 dump
            json.dump(payload_resultado.model_dump(), f, indent=2, ensure_ascii=False)

        # 7. ACTUALIZACIÓN DE ESTADO PARA EL FRONT-END
        db.create_or_update_job(family=family_id, status="completed", score=score)

    except Exception as e:
        print(f"❌ [WORKER] Error crítico procesando la tarea: {e}")
        # Si algo explota, le avisamos a la base de datos para que el front-end no se quede esperando
        db.create_or_update_job(family=family_id, status="failed", score=0.0)
        
    finally:
        # 8. LIMPIEZA ABSOLUTA (STATELESSNESS)
        print(f"🧹 [WORKER] Limpiando archivos temporales en: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)