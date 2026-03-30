import base64, json, re
from openai import AzureOpenAI  
from analyzer_client import AnalyzerClient
from schemas import PromptBuilderRequest
from database import AgentMemory
import os
import time
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompt_textos" 
from ddgs import DDGS
import config 

# ==============================================================================
# CONFIGURACIÓN DE CLIENTES HÍBRIDOS (BRAIN-MUSCLE)
# ==============================================================================

# Instanciamos el cliente (automáticamente usará MOCK_MODE si está configurado)
analyzer_client = AnalyzerClient()

# 1. EL CEREBRO (Azure OpenAI): Para lógica, auditoría, visión y optimización.
print("🔌 Conectando con el CEREBRO (Azure OpenAI)...")
client_brain = AzureOpenAI(
    azure_endpoint=config.AZURE_ENDPOINT,
    api_key=config.AZURE_API_KEY,
    api_version=config.AZURE_API_VERSION
)
MODEL_BRAIN = config.AZURE_DEPLOYMENT_NAME

db = AgentMemory()

# ==============================================================================
# NODOS DEL GRAFO
# ==============================================================================

# --- REEMPLAZAR ESTA FUNCIÓN EN nodes.py ---

def input_refinery_node(state):
    # USAMOS CEREBRO (GPT-4o) para: 1) Limpieza Estructural y 2) Asimilación de Lógica (Sin Amnesia)
    print(f"\n[PASO: REFINERÍA & LÓGICA] 🛡️ (Brain) Analizando estructura y asimilando reglas de negocio...")
    
    raw_prompt = state.get("original_prompt", "")
    if not raw_prompt: return {}

    # Si es muy corto (<500 chars), asumimos que no hay gran lógica oculta.
    # Subimos el umbral un poco para no filtrar instrucciones breves pero densas.
    if len(raw_prompt) < 500:
        print("      ✅ Prompt breve. Pase directo.")
        return {}

    # --- EL COMPILADOR DE LÓGICA DE NEGOCIO (PRESERVACIÓN DE ADN) ---
    compiler_instruction = f"""
    You are a Senior Logic Compiler and Prompt Engineer.
    Your task is to analyze the USER PROMPT, assimilate its specific business logic, and optimize its structure for an AI Agent (Llama 4) WITHOUT LOSING ANY SPECIFIC RULES.

    USER PROMPT START:
    {raw_prompt[:30000]}
    USER PROMPT END

    YOUR MISSION (2 GOALS):
    1. **STRUCTURAL REORGANIZATION**: Detect messy, duplicated, or "Frankenstein" instructions and organize them logically.
    2. **BUSINESS LOGIC ASSIMILATION (ZERO DATA LOSS)**: Detect ALL business rules, edge cases, fallbacks, and specific constraints. Translate them into structured Algorithmic Rules (Step-by-step) BUT preserve 100% of their original intent and detail.

    🔴 CRITICAL "NO AMNESIA" PROTOCOL:
    - DO NOT summarize, abstract, or delete specific business rules just to make the prompt shorter.
    - If the user specifies a bizarre, highly specific, or strict condition (e.g., "If the stamp is blue, ignore the date", or "If X is missing, look for Y in the bottom left"), YOU MUST KEEP IT EXACTLY AS INTENDED.
    - Transform "Fuzzy Natural Language" into "Llama-4 Actionable Steps" (Locate -> Evaluate -> Extract -> Fallback).

    CRITERIA FOR "REWRITE_NEEDED":
    - Case A: The prompt is structurally messy/redundant.
    - Case B: The prompt contains logic rules that are NOT formally structured in clear steps.

    TRANSFORMATION RULES (If REWRITE_NEEDED):
    1. Clean the formatting but RETAIN ALL domain-specific tactics.
    2. **INJECT A NEW SECTION**: Create `## SECTION: BUSINESS LOGIC & COMPUTED FIELDS`.
    3. Inside that section, write the logic in STEP-BY-STEP PSEUDOCODE.
    4. Keep the output in **ENGLISH** (instructions) but preserve **SPANISH KEYS/IDs**.

    OUTPUT FORMAT (JSON):
    {{
        "status": "READY" or "REWRITE_NEEDED",
        "reason": "Explanation (e.g., 'Structured logic into steps without losing rule XYZ').",
        "final_prompt": "The fully optimized prompt (only if REWRITE_NEEDED, else null)."
    }}
    """

    try:
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": compiler_instruction}], 
            response_format={"type": "json_object"},
            temperature=0.0
        )
        result = json.loads(re.sub(r"```json|```", "", response.choices[0].message.content).strip())
        
        if result.get("status") == "REWRITE_NEEDED":
            print(f"      ⚠️ ALERTA: Se detectaron mejoras estructurales (Preservando Reglas de Negocio).")
            print(f"      📝 Motivo: {result.get('reason')}")
            
            optimized_prompt = result.get("final_prompt")
            if optimized_prompt and len(optimized_prompt) > 100:
                print("      🧠 LÓGICA ASIMILADA: Pseudocódigo de negocio inyectado sin pérdida de información.")
                return {"original_prompt": optimized_prompt}
            else:
                print("      ⚠️ La reescritura falló (contenido vacío). Pasando original.")
                return {}
        else:
            print(f"      ✅ Prompt impecable. No se requiere compilación de lógica adicional.")
            return {} 

    except Exception as e:
        print(f"      ❌ Refinería (Brain) fuera de servicio: {e}. Pasando prompt original.")
        return {}
                
def research_node(state):
    # USAMOS CEREBRO (GPT-4o) para Visión Panorámica y Detección Caligráfica (HTR)
    print(f"\n[PASO: INVESTIGACIÓN] 🕵️‍♂️ (Brain) Realizando Peritaje Forense COMPARATIVO y Detección de Manuscritos...")
    
    existing_context = state.get("semantic_context", "")
    if existing_context and state.get("attempts", 0) > 0:
        return {}

    batch = state.get("batch_queue", [])
    if not batch: return {}

    # --- ESTRATEGIA DE MUESTREO (PANORÁMICA) ---
    sample_indices = [0]
    if len(batch) > 1: sample_indices.append(len(batch) // 2)
    if len(batch) > 2: sample_indices.append(len(batch) - 1)
    sample_indices = sorted(list(set(sample_indices)))
    
    sample_images_b64 = []
    print(f"      📸 Tomando muestra de {len(sample_indices)} documentos para análisis de varianza y OCR...")

    for idx in sample_indices:
        case = batch[idx]
        if case.get("images"):
            img_path = case["images"][0] 
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    sample_images_b64.append(b64)
            except: pass

    if not sample_images_b64: return {}

    # --- FASE 1: VISIÓN COMPARATIVA Y DETECCIÓN HTR (GPT-4o) ---
    print("      👁️ Analizando patrones CONSTANTES, VARIABLES y tipo de escritura...")
    forensic_data = {}
    
    try:
        content_payload = [
            {"type": "text", "text": """
            Analyze these document samples belonging to the SAME FAMILY.
            YOUR TASK: Create a "Universal Navigation Guide" AND detect if there is ANY handwritten text.

            RETURN STRICT JSON (No comments, no markdown):
            {
               "identity": { "country": "Origin Country", "doc_name": "Official Name" },
               "formats": { "date_format": "DD-MM-YYYY or MM-DD-YYYY", "number_format": "Dot or Comma" },
               "layout_strategy": "Explain if layout is fixed or variable. Mention where to look.",
               "universal_anchors": ["List", "Of", "Keywords"],
               "contains_handwriting": true // Set to true ONLY if you detect manual writing, cursive, hand-drawn numbers, or signatures.
            }
            """}
        ]
        
        for b64 in sample_images_b64:
            content_payload.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        # CORRECCIÓN CLAVE: Agregamos response_format={"type": "json_object"}
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": content_payload}],
            response_format={"type": "json_object"}, 
            temperature=0.1
        )
        
        # Parseo robusto
        raw_content = response.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        
        if match:
            forensic_data = json.loads(match.group(0))
            ident = forensic_data.get('identity', {})
            print(f"      📄 Familia Identificada: {ident.get('doc_name')} ({ident.get('country')})")
            print(f"      🧩 Estrategia Híbrida: {forensic_data.get('layout_strategy')[:100]}...")
            
            # --- ALERTA HTR ---
            if forensic_data.get('contains_handwriting'):
                print("      🚨 ALERTA HTR: Texto manuscrito detectado en la muestra. Preparando protocolos visuales estrictos.")
        else:
            print(f"      ⚠️ No se encontró JSON válido en: {raw_content[:50]}...")
            raise ValueError("JSON no encontrado")

    except Exception as e:
        print(f"      ⚠️ Fallo en Visión Panorámica: {e}")
        # Fallback para que no rompa el flujo
        forensic_data = {"identity": {"doc_name": "Unknown"}, "layout_strategy": "Generic search strategy.", "contains_handwriting": False}

    # --- FASE 2: INVESTIGACIÓN WEB ---
    doc_name = forensic_data.get('identity', {}).get('doc_name', 'Official Document')
    country = forensic_data.get('identity', {}).get('country', '')
    search_query = f"official data requirements for {doc_name} {country} explanation"
    
    web_context = ""
    try:
        time.sleep(1) 
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, region="wt-wt", safesearch="moderate", max_results=2))
        if results:
            web_context = "\n".join([f"- {r.get('body', '')}" for r in results])
    except: web_context = "No web context."

    # --- FASE 3: SÍNTESIS INCLUSIVA (CON PROTOCOLO HTR) ---
    original_prompt = state.get("original_prompt", "")
    if "SECTION 1: ROLE & CONTEXT" in original_prompt:
        return {"semantic_context": "Contexto ya integrado."}

    print("      🧠 Generando 'SECTION 1' Adaptativa...")
    
    synthesis_prompt = f"""
    You are the "Context Orientation Engine".
    Create the "SECTION 1: ROLE & CONTEXT" for a Master Prompt.

    INPUT DATA:
    - Identity: {json.dumps(forensic_data.get('identity'))}
    - Formats: {json.dumps(forensic_data.get('formats'))}
    - VARIABILITY STRATEGY: {forensic_data.get('layout_strategy')}
    - Universal Anchors: {forensic_data.get('universal_anchors')}
    - Legal Context: {web_context}
    - HANDWRITING_DETECTED: {forensic_data.get('contains_handwriting', False)}

    YOUR TASK:
    Write a "SECTION 1" that prepares the extraction model for MULTIPLE LAYOUTS.
    
    CRITICAL:
    - Under "DOCUMENT HEURISTICS", explicitly state that the layout MAY CHANGE.
    - Provide a "Search Protocol" based on Anchors, not fixed positions.
    - IF HANDWRITING_DETECTED is true: You MUST add a subsection titled "🚨 PROTOCOLO MANUSCRITO (HTR)". Instruct the extraction model to: 1) NEVER auto-correct spelling of handwritten text, 2) Pay close attention to crossing lines or noise, and 3) Transcribe exactly what is seen.

    OUTPUT: Return ONLY the text starting with "## SECTION 1: ROLE & CONTEXT"
    """
    
    try:
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": synthesis_prompt}], 
            temperature=0.1
        )
        new_context = response.choices[0].message.content.strip()
        
        return {
            "semantic_context": new_context,
            "original_prompt": f"{new_context}\n\n{original_prompt}",
            "has_handwriting": forensic_data.get('contains_handwriting', False) # <--- ¡CLAVE! Guardamos el flag en el State.
        }

    except Exception as e:
        print(f"      ⚠️ Error sintetizando: {e}")
        return {}
    
def test_analyzer_node(state):
    """
    Empaqueta el estado actual en un payload estricto (PromptBuilderRequest) 
    y lo envía al document-analyzer para probar la efectividad del prompt.
    """
    print(f"\n[PASO: PRUEBA CON ANALYZER] 🚀 (Handoff) Enviando payload al motor para {len(state['batch_queue'])} casos...")
    
    batch_results = state.get("batch_results", {})
    parameters = state.get("parameters", {})
    id_document_type = state.get("id_document_type")
    id_user = state.get("id_user")
    
    # 1. ENSAMBLAJE DEL PROMPT
    # Unimos la táctica actual con el prompt base. El document-analyzer soporta 
    # una lista de prompts secuenciales, pero para nuestra prueba lo enviaremos 
    # consolidado en el primer índice.
    tactic = state.get("current_tactic", "")
    base_prompt = state.get("original_prompt", "")
    combined_prompt = f"{tactic}\n\n{base_prompt}" if tactic else base_prompt
    
    for case in state["batch_queue"]:
        cid = case["case_id"]
        
        # 2. PREPARACIÓN DE LA IMAGEN / DOCUMENTO
        # Tomamos la primera imagen extraída por el worker y la convertimos a base64
        img_path = case["images"][0] if case["images"] else None
        b64_file = ""
        if img_path:
            try:
                with open(img_path, "rb") as f:
                    b64_file = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                print(f"      ❌ Error leyendo archivo para {cid}: {e}")
        
        # 3. ARMADO DEL PAYLOAD CON PYDANTIC
        try:
            request_payload = PromptBuilderRequest(
                file=b64_file,
                mime_type="image/jpeg", # Ajustado al formato que genera el worker
                prompt=[combined_prompt], # Array de strings con {{placeholders}}
                parameters=parameters,
                id_document_type=id_document_type,
                id_user=id_user
            )
            
            # 4. LLAMADA HTTP (MOCK O REAL)
            # Aquí es donde la magia de la orquestación ocurre
            response = analyzer_client.test_prompt(request_payload)
            
            # 5. ALMACENAMIENTO DE LA RESPUESTA
            # Convertimos el modelo Pydantic a diccionario para guardarlo en el estado
            batch_results[cid] = {
                "analyzer_response": response.model_dump(), 
                "expected": case["expected_data"]
            }
            print(f"      ✅ Prueba HTTP exitosa para el caso {cid}. Status Global del Analyzer: '{response.status}'")
            
        except Exception as e:
            print(f"      ❌ Error en la prueba HTTP para {cid}: {e}")
            # Fallback seguro para no romper el grafo: Simulamos un rechazo total
            batch_results[cid] = {
                "analyzer_response": {"status": "rejected", "details": {"documents": []}},
                "expected": case["expected_data"]
            }

    return {"batch_results": batch_results, "attempts": state["attempts"] + 1}

def validation_node(state):
    """
    Lee la respuesta del document-analyzer, calcula el score real 
    basado en los estados 'approved'/'rejected' del backend, y empaqueta 
    los errores (mismatches) para el Optimizador.
    """
    print(f"\n[PASO: VALIDACIÓN CRUZADA] ⚖️ Evaluando el veredicto del Analyzer...")
    total_score = 0.0
    current_results = state.get("batch_results", {})
    total_cases = len(current_results)
    global_mismatches = [] 
    
    # Necesitamos parameters para saber qué se esperaba y construir el reporte de error
    parameters = state.get("parameters", {})
    
    for cid, res in current_results.items():
        analyzer_res = res.get("analyzer_response", {})
        
        # Navegamos el JSON oficial del Analyzer
        details = analyzer_res.get("details", {})
        documents = details.get("documents", [])
        doc_data = documents[0] if documents else {}
        fields_result = doc_data.get("fields", {})
        
        correct_fields = 0
        total_fields = len(parameters)
        
        if total_fields == 0:
            score = 0.0
            global_mismatches.append(f"[CASE {cid}] ERROR FATAL: No hay parámetros configurados.")
        else:
            # Auditamos campo por campo según el veredicto del backend
            for field_key, param_info in parameters.items():
                field_res = fields_result.get(field_key, {})
                f_status = field_res.get("status", "rejected")
                f_value = field_res.get("value", "N/A")
                
                # Datos para el reporte de error
                expected_val = param_info.get("value", "N/A")
                comp_op = param_info.get("comparison_operation", "desconocida")
                
                if f_status == "approved":
                    correct_fields += 1
                else:
                    # Este string es ORO puro para el optimizer_node
                    error_msg = (
                        f"ID '{field_key}' FALLÓ. "
                        f"El LLM extrajo: '{f_value}', pero se esperaba: '{expected_val}'. "
                        f"No cumplió la regla oficial de validación: '{comp_op}'."
                    )
                    global_mismatches.append(f"[CASE {cid}] {error_msg}")
            
            score = (correct_fields / total_fields) * 100

        res["score"] = score
        res["mismatches"] = global_mismatches
        total_score += score

    avg_score = total_score / total_cases if total_cases > 0 else 0
    print(f"      📊 Score Promedio del Lote: {avg_score:.1f}% (Mejor anterior: {state['best_avg_score']:.1f}%)")

    if global_mismatches:
        print(f"      ⚠️ DIAGNÓSTICO DE FALLOS DEL ANALYZER ({len(global_mismatches)} errores):")
        for err in global_mismatches[:5]: 
            print(f"         🔴 {err}")
    else: 
        print("      ✅ ¡Cero errores! El document-analyzer aprobó el template al 100%.")

    # --- ACTUALIZACIÓN DE MÉTRICAS HISTÓRICAS ---
    best_avg = state.get("best_avg_score", 0.0)
    best_tac = state.get("best_tactic")
    best_params = state.get("best_parameters", {})
    
    if avg_score >= best_avg:
        best_avg = avg_score
        best_tac = state.get("current_tactic")
        best_params = parameters # Guardamos la configuración que logró este score
        
        if avg_score > 0 and best_tac:
            print("      📈 ¡Nueva Táctica Líder y Configuración guardadas en memoria!")
            db.save_success(state['family'], best_tac, avg_score)

    # --- CONDICIÓN DE CORTE ---
    is_final = False
    if avg_score >= 98.0 or state["attempts"] >= 5:
        is_final = True
        # Nota: El guardado del archivo maestro lo movimos al worker.py
    else: 
        db.save_failure(state["family"], state.get("current_tactic"), global_mismatches[:5])

    return {
        "avg_score": avg_score, 
        "batch_results": current_results, 
        "is_final": is_final, 
        "best_avg_score": best_avg, 
        "best_tactic": best_tac,
        "best_parameters": best_params,
        "mismatches": global_mismatches
    }

def optimizer_node(state):
    """
    Toma los errores estructurados que devolvió el Analyzer y usa el Cerebro (GPT-4o) 
    para ajustar la táctica de extracción. 
    PROHÍBE la generación de schemas JSON manuales y fuerza el uso de {{placeholders}}.
    """
    print(f"[PASO: OPTIMIZACIÓN] 🔧 (Brain) El Arquitecto está ajustando la táctica basándose en el feedback del Analyzer...")
    
    current_mismatches = state.get('mismatches', [])
    previous_tactic = state.get('current_tactic', "")
    original_prompt = state.get('original_prompt', "")
    parameters = state.get('parameters', {})
    
    if not previous_tactic: 
        previous_tactic = "(Sin táctica específica aún. Usando solo el prompt base.)"
    
    # Preparamos el resumen de errores para el LLM
    errors_summary = json.dumps(current_mismatches[:15], indent=2, ensure_ascii=False)
    
    # Construimos la lista estricta de placeholders permitidos
    valid_placeholders = [f"{{{{{k}:name}}}}" for k in parameters.keys()]
    placeholders_instruction = ", ".join(valid_placeholders)
    
    # --- PROMPT DEL ARQUITECTO: MODO 'SINTAXIS PURA' ---
    opt_prompt = f"""
    You are the Lead Prompt Architect for a Document Extraction System. 
    Your goal is to fix the FAILED TACTIC based on the ERRORS returned by our backend validation engine.

    📜 INPUT CONTEXT:
    1. BASE PROMPT (Context only): "{original_prompt[:2000]}..."
    2. FAILED TACTIC: "{previous_tactic}"
    3. ERRORS TO FIX: {errors_summary}
    
    🔴 CRITICAL RULES FOR THE NEW TACTIC:
    1. **NO JSON FORMATTING**: DO NOT write JSON examples. DO NOT ask the model to output JSON. The backend system natively forces the JSON schema. Your tactic must ONLY contain the natural language logical steps to locate and extract the data.
    2. **STRICT VARIABLE SYNTAX**: You MUST represent fields using EXACTLY these placeholders: {placeholders_instruction}. 
       Example: "Locate the issue date and extract it for the field {{{{fecha_emision:name}}}}."
       DO NOT use the literal ID like `{{{{ID:fecha_emision}}}}` or `<fecha_emision>`.
    3. **FIXING THE LOGIC**: The errors tell you what the LLM extracted vs what the backend expected to pass the mathematical/logical comparison. Adjust your instructions so the LLM extracts the EXACT expected format (e.g., "strip currency symbols", "take the right-most date", "concatenate without spaces").
    4. **NO HARDCODING**: Never put the exact expected value in the prompt. Teach the model *how* to find it.

    OUTPUT FORMAT (JSON):
    {{
        "tactic": "#### Field: {{{{fecha_emision:name}}}}\n1. Locate the 'Date' header.\n2. Extract only the ISO format.\n\n#### Field: {{{{monto_asegurado:name}}}}\n1. Ignore the currency symbol..."
    }}
    
    """
    
    try:
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": opt_prompt}], 
            response_format={"type": "json_object"}, 
            temperature=0.1
        )
        res_json = json.loads(re.sub(r"```json|```", "", response.choices[0].message.content).strip())
        new_tactic = res_json.get("tactic", previous_tactic)
        
        # --- CENSURA ANTI-LEAKAGE (Cero Trampas) ---
        # Si GPT hace trampa y pone la respuesta correcta en la instrucción, la bloqueamos.
        for key, param in parameters.items():
            val_real = str(param.get("value", "")).strip()
            if len(val_real) >= 4 and val_real in new_tactic:
                new_tactic = new_tactic.replace(val_real, f"{{{{VALUE_FOR_{key}}}}}")

        if new_tactic != previous_tactic:
            print("      📝 ARQUITECTO: Táctica iterada (Placeholders protegidos, sin JSON manual).")
            return {"current_tactic": new_tactic}
        else:
            print("      🛡️ ARQUITECTO: La táctica no cambió. Forzando ajuste heurístico.")
            return {"current_tactic": previous_tactic + "\n\n(Refining search strategy based on errors)"}
        
    except Exception as e:
        print(f"      ❌ Error optimizador: {e}")
        return {"current_tactic": previous_tactic}

              
def configurator_node(state):
    """
    Toma los datos esperados (Ground Truth) y construye el diccionario estricto 
    'parameters' requerido por el servicio de Prompt Builder (document-analyzer).
    """
    if state.get('parameters'): 
        return {}
    
    # ⬇️ EL ARREGLO ESTÁ AQUÍ ⬇️
    # Buscamos la data esperada dentro del primer caso del batch_queue
    batch_queue = state.get('batch_queue', [])
    expected_data = batch_queue[0].get('expected_data', {}) if batch_queue else {}

    if not expected_data:
        print("      ⚠️ Advertencia: No hay datos esperados para configurar los parámetros.")
        return {"parameters": {}}

    print("      🐢 (Brain) Diseñando matriz de validación (Parameters Config)...")
    
    # Preparamos un string limpio con las keys y values para que el LLM trabaje
    raw_key_values = json.dumps(expected_data, indent=2, ensure_ascii=False)

    architect_prompt = f"""
    You are a Data Configuration Architect for a Document Validation System.
    I will provide you a JSON with ID-VALUE pairs. 
    Your task is to convert this into a strict 'parameters' dictionary.

    INPUT DATA:
    {raw_key_values}

    CRITICAL INSTRUCTIONS & SCHEMA:
    For each key in the input, you MUST create an object with these exact properties:
    - "name": A human-readable name for the key (infer it from the key string).
    - "value": The EXACT expected value from the input.
    - "data_type": Must be "string", "date" (if YYYY-MM-DD format), or "integer" (if pure numbers/monetary).
    - "condition": Use "required" for all fields.
    - "comparison_operation": 
        * For "string": Use "containment" (default for text) or "onlyAlphanumericEquals" (for IDs).
        * For "date": Use "equal" (from date v3 operators).
        * For "integer": Use "equals".
    - "comparison_operation_parameter": null
    - "linked_keys": []
    - "normalizers": If it's a monetary amount or math is needed, use ["resolve_arithmetic"], otherwise null.

    EXAMPLE OUTPUT FORMAT:
    {{
      "parameters": {{
        "nombre_asegurado": {{
          "name": "Nombre del Asegurado",
          "value": "Achilles Information Ltd",
          "data_type": "string",
          "condition": "required",
          "comparison_operation": "containment",
          "comparison_operation_parameter": null,
          "linked_keys": [],
          "normalizers": null
        }},
        "fecha_emision": {{
          ...
          "data_type": "date",
          "comparison_operation": "equal"
        }}
      }}
    }}

    Respond ONLY with the JSON object. Do not include markdown or explanations.
    """
    
    try:
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": architect_prompt}], 
            response_format={"type": "json_object"}, 
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        config_json = json.loads(re.sub(r"```json|```", "", content).strip())
        
        parameters = config_json.get("parameters", {})
        
        # Validación de seguridad: Aseguramos que todas las keys originales estén en parameters
        for k, v in expected_data.items():
            if k not in parameters:
                # Fallback manual en caso de que la IA omita una llave
                val_str = str(v.get("value", v) if isinstance(v, dict) else v)
                parameters[k] = {
                    "name": str(k).replace("_", " ").title(),
                    "value": val_str,
                    "data_type": "string",
                    "condition": "required",
                    "comparison_operation": "containment",
                    "comparison_operation_parameter": None,
                    "linked_keys": [],
                    "normalizers": None
                }
                
        print(f"      ✅ Matriz de parámetros generada con {len(parameters)} campos de validación.")
        return {"parameters": parameters}

    except Exception as e: 
        print(f"      ❌ ERROR EN ARQUITECTO CONFIGURADOR: {e}")
        return {"parameters": {}}