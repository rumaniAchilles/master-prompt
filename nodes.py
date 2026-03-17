import base64, json, re
from fireworks.client import Fireworks
from openai import AzureOpenAI  
from validators import validate_result
from database import AgentMemory
import os
import time
import main
from ddgs import DDGS
import config  # <--- NUEVO: Importamos tu configuración centralizada

# ==============================================================================
# CONFIGURACIÓN DE CLIENTES HÍBRIDOS (BRAIN-MUSCLE)
# ==============================================================================

# 1. EL CEREBRO (Azure OpenAI): Para lógica, auditoría, visión y optimización.
print("🔌 Conectando con el CEREBRO (Azure OpenAI)...")
client_brain = AzureOpenAI(
    azure_endpoint=config.AZURE_ENDPOINT,
    api_key=config.AZURE_API_KEY,
    api_version=config.AZURE_API_VERSION
)
MODEL_BRAIN = config.AZURE_DEPLOYMENT_NAME

# 2. EL MÚSCULO (Fireworks Llama 4): Para extracción masiva (Simulación Producción).
print("💪 Conectando con el MÚSCULO (Fireworks Llama 4)...")
client_muscle = Fireworks(api_key=config.FIREWORKS_API_KEY)
MODEL_MUSCLE = config.FIREWORKS_MODEL_ID

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
    
def extraction_node(state):
    # --- CRÍTICO: USAMOS MÚSCULO (FIREWORKS) ---
    # Este nodo SIMULA PRODUCCIÓN. Debe fallar si Llama falla.
    print(f"\n[PASO: EXTRACCIÓN MASIVA] 🤖 (Muscle - Llama 4) Procesando lote de {len(state['batch_queue'])} documentos...")
    batch_results = state.get("batch_results", {})
    tactic = state.get("current_tactic", "")
    
    for case in state["batch_queue"]:
        cid = case["case_id"]
        final_prompt = state["original_prompt"]
        keys = list(case["expected_data"].keys())
        
        schema_instruction = f"""
        OUTPUT INSTRUCTIONS:
        1. ANALYSIS PHASE (Optional): You MAY output natural language reasoning strictly BEFORE the JSON block if the tactic requires it.
        2. JSON PHASE (Mandatory): You MUST output a valid JSON object containing these EXACT keys:
        {json.dumps(keys)}
        3. FORMAT: Each value must be an object with SPANISH keys:
           {{
             "valor": "extracted info", 
             "confianza": 0.99, 
             "Estado": "Aprobado"
           }}
           (Use dot for decimals in JSON, e.g., 0.99)
        """
        full_prompt = f"{schema_instruction}\n\nTACTIC (Specific Rules):\n{tactic}\n\nTASK (Visual Layout):\n{final_prompt}"
        
        content = [{"type": "text", "text": full_prompt}]
        for img_path in case["images"]:
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            except: pass

        try:
            # CAMBIO: Usamos explícitamente client_muscle y MODEL_MUSCLE
            response = client_muscle.chat.completions.create(
                model=MODEL_MUSCLE, 
                messages=[{"role": "user", "content": content}], 
                response_format={"type": "json_object"}, 
                temperature=0
            )
            clean_json = re.sub(r"```json|```", "", response.choices[0].message.content).strip()
            match = re.search(r"\{.*\}", clean_json, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
        except Exception as e:
            print(f"      ❌ Error en {cid}: {e}")
            data = {}

        batch_results[cid] = {"extraction": data, "expected": case["expected_data"]}
    
    return {"batch_results": batch_results, "attempts": state["attempts"] + 1}

def validation_node(state):
    # LÓGICA PURA: NO REQUIERE CAMBIOS DE IA
    print(f"[PASO: VALIDACIÓN CRUZADA] ⚖️ Calculando Score Promedio...")
    total_score = 0.0
    current_results = state.get("batch_results", {})
    total_cases = len(current_results)
    global_mismatches = [] 
    
    for cid, res in current_results.items():
        mismatches, score = validate_result(res["extraction"], res["expected"], state.get("rules", {}))
        total_score += score
        if mismatches:
            for m in mismatches: global_mismatches.append(f"[CASE {cid}] {m}")
        current_results[cid]["score"] = score
        current_results[cid]["mismatches"] = mismatches

    avg_score = total_score / total_cases if total_cases > 0 else 0
    print(f"      📊 Score Promedio del Lote: {avg_score:.1f}% (Mejor anterior: {state['best_avg_score']:.1f}%)")

    if global_mismatches:
        print(f"      ⚠️ DIAGNÓSTICO DE FALLOS ({len(global_mismatches)} errores):")
        for err in global_mismatches[:5]: print(f"         🔴 {err}")
    else: print("      ✅ ¡Cero errores detectados!")

    best_avg = state["best_avg_score"]
    best_tac = state["best_tactic"]
    
    if avg_score >= best_avg:
        best_avg = avg_score
        best_tac = state.get("current_tactic")
        if avg_score > 0 and best_tac:
            print("      📈 ¡Nueva Táctica Líder identificada!")
            db.save_success(state['family'], best_tac, avg_score)

    is_final = False
    if avg_score >= 98.0 or state["attempts"] >= 5:
        is_final = True
        if best_tac: save_master_prompt(state["family"], state["original_prompt"], best_tac)
    else: db.save_failure(state["family"], state.get("current_tactic"), global_mismatches[:5])

    return {"avg_score": avg_score, "batch_results": current_results, "is_final": is_final, "best_avg_score": best_avg, "best_tactic": best_tac, "mismatches": global_mismatches}

def optimizer_node(state):
    # USAMOS CEREBRO (GPT-4o) para razonar sobre los fallos, PRESERVANDO EL ADN DEL NEGOCIO
    print(f"[PASO: OPTIMIZACIÓN] 🔧 (Brain) El Arquitecto está ajustando la táctica (Protegiendo Lógica de Negocio)...")
    
    current_mismatches = state.get('mismatches', [])
    previous_tactic = state.get('current_tactic')
    original_prompt = state.get('original_prompt', "")
    
    if not previous_tactic: previous_tactic = "(No specific tactic yet.)"
    
    # --- CARGA DEL ESPEJO DE ORO (REFERENCE ARCHITECTURE) ---
    try:
        path_gold = main.BASE_DIR / "GOLD_STANDARD_TEMPLATE.txt"
        with open(path_gold, "r", encoding="utf-8") as f: 
            gold_standard = f.read()
    except: 
        gold_standard = "(Reference not available. Rely strictly on the Constitution.)"

    try:
        path_guide = main.BASE_DIR / "MASTER_PROMPT_GUIDE.md"
        with open(path_guide, "r", encoding="utf-8") as f: 
            constitution = f.read()
    except: 
        constitution = "RULES: Use {{variable:name}} syntax (e.g. {{rut_trabajador:name}}). Dates to ISO."

    # Memoria de Fallos
    recent_failures = db.get_recent_failures(state['family'])
    failures_context = "None yet."
    if recent_failures:
        print(f"      🧠 Memoria activada: Evitando {len(recent_failures)} estrategias fallidas previas.")
        failures_context = "\n".join([f"- {f[:200]}..." for f in recent_failures])
    
    errors_summary = json.dumps(current_mismatches[:15], indent=2)
    current_rules = json.dumps(state.get('rules', {}), indent=2)
    
    valid_vars = []
    if state.get('expected_data'):
        valid_vars = [f"{{{{{k}:name}}}}" for k in state['expected_data'].keys()]
    vars_instruction = ", ".join(valid_vars)
    
    # --- PROMPT DEL ARQUITECTO: MODO PRESERVACIÓN ESTRICTA ---
    opt_prompt = f"""
    You are the Lead Prompt Architect. 
    Your goal is to fix the FAILED TACTIC based on the ERRORS, but you MUST PRESERVE the USER'S SACRED LOGIC.

    🏆 GOLD STANDARD (STRUCTURE):
    <TEMPLATE>{gold_standard}</TEMPLATE>
    
    📜 INPUT CONTEXT:
    1. USER'S LOGIC (SACRED - DO NOT MODIFY ITS INTENT): "{original_prompt[:15000]}..."
    2. FAILED TACTIC: "{previous_tactic}"
    3. ERRORS TO FIX: {errors_summary}
    4. RULES: {current_rules}
    
    🔴 PROTOCOL OF BUSINESS LOGIC PRESERVATION (ZERO DATA LOSS):
    1. **NEVER DELETE BUSINESS RULES**: The USER'S LOGIC contains specific edge cases, fallbacks, constraints, and industry knowledge. You MUST carry ALL of them over to the new tactic. Do not abstract, summarize, or simplify them away.
    2. **FORMAT, DO NOT PRUNE**: Translate the business rules into Llama-4 actionable steps (Locate -> Evaluate -> Extract -> Fallback), but keep every condition intact.
    3. **EFFICIENCY WITHOUT AMNESIA**: You must remove "meta-talk" (e.g., "Your task is to analyze..."), BUT you CANNOT remove conditionals (e.g., "If the document says X, do Y").
    4. **FIXING ERRORS**: To fix the ERRORS, you must ADD specific navigational anchors or formatting rules, but NEVER by overriding the original business intent.

    3. **VARIABLE SYNTAX**: You MUST use: {vars_instruction}.

    YOUR MISSION:
    Rewrite the tactic to fix the errors. Make the instructions direct and actionable for an AI, while acting as an absolute vault for the user's business logic.

    OUTPUT FORMAT (JSON):
    {{
        "tactic": "For {{rut:name}}: 1. Locate 'RUT'. 2. Extract value. 3. [Insert User's Specific Business Logic here]...",
        "rule_updates": {{ "ID": "name" }} 
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
        rule_updates = res_json.get("rule_updates", {})
        
        if new_tactic == "NO_ACTION":
            print("      🛡️ ALTO EL FUEGO: El Arquitecto determinó que la táctica actual ya es óptima y no requiere ajustes.")
            return {"current_tactic": previous_tactic}

        # Censura anti-leakage
        if state.get('expected_data'):
            for key, item in state['expected_data'].items():
                val_real = str(item.get("value", "")).strip()
                if len(val_real) >= 4 and val_real in new_tactic:
                    new_tactic = new_tactic.replace(val_real, f"{{{{VALUE_FOR_{key}}}}}")

        if rule_updates:
            print(f"      ⚖️ JUEZ (Ajuste de Reglas Preservando ADN):")
            updated_rules = state.get('rules', {}).copy()
            for field, new_rule in rule_updates.items():
                clean_id = str(field).split(":")[0].strip()
                print(f"         - ID '{clean_id}': Regla ajustada a -> '{new_rule}'")
                if isinstance(updated_rules.get(clean_id), dict): updated_rules[clean_id]['rule'] = new_rule
                else: updated_rules[clean_id] = new_rule
            return {"current_tactic": new_tactic, "rules": updated_rules}
        
        elif new_tactic != previous_tactic:
            print("      📝 ARQUITECTO: Táctica iterada (Reglas de negocio blindadas).")
            return {"current_tactic": new_tactic}
        else:
            return {"current_tactic": new_tactic + "\n\n(Refining based on Fidelity Protocol)"}
        
    except Exception as e:
        print(f"      ❌ Error optimizador: {e}")
        return {"current_tactic": state.get('current_tactic', "")}
        
def save_master_prompt(family, original, tactic):
    content = f"=== OPTIMIZED TACTIC (Family Version) ===\n{tactic}\n\n=== ORIGINAL PROMPT ===\n{original}"
    # Usamos la ruta absoluta definida en main para consistencia total
    path = main.PROMPTS_DIR / f"MASTER_{family}.txt"
    os.makedirs(main.PROMPTS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("      💾 Protocolo Maestro Actualizado.")

def syntax_enforcer_agent(full_prompt_text, expected_keys, has_handwriting=False):
    """
    AGENTE FINALIZADOR (Esquema Español): 
    Genera un Prompt Maestro Limpio con Ejemplo JSON {valor, confianza, Estado}.
    """
    print(f"      👮‍♂️ AGENTE DE SINTAXIS (Brain): Generando Prompt Maestro (Esquema Español) para {len(expected_keys)} variables...")
    
    if not expected_keys: 
        return full_prompt_text.replace("=== OPTIMIZED TACTIC (Family Version) ===", "").replace("=== ORIGINAL PROMPT ===", "").strip()

    keys_str = ", ".join(expected_keys)

    # --- EXCEPCIÓN HTR DINÁMICA ---
    htr_rule = ""
    if has_handwriting:
        htr_rule = "\n       - 🚨 HTR EXCEPTION: Handwriting detected. You MUST ALLOW and PRESERVE 'Visual Chain-of-Thought' instructions for handwritten fields. Do not delete visual analysis steps for these fields."

    enforcer_prompt = f"""
    You are a Master Prompt Publisher. Think like a super expert in model Llama4 Maverick, for data extraction.
    Transform the input draft into a polished PRODUCTION PROMPT.

    INPUT DRAFT:
    <DRAFT>
    {full_prompt_text}
    </DRAFT>

    REQUIRED KEYS: [{keys_str}]

    YOUR MISSION:
    1. **CLEAN & MERGE**: 
       - Remove redundant internal headers, BUT YOU MUST PRESERVE the strict structure of "PHASE 1: REASONING" and "PHASE 2: JSON" if present.
       - Do not flatten the reasoning section into the general text.
       - 🚨 ELIMINATE REDUNDANT SCHEMAS: STRICTLY DELETE any generic "OUTPUT FORMAT" sections or pre-existing JSON blocks that use placeholders (like `<valor>`, `<float>`, `<yyyy-mm-dd>`, or `<NIF/CIF>`). The final prompt MUST contain ONLY ONE JSON block (the realistic example you generate at the end).

    2. **KILL THE BUREAUCRACY**: 
       - DETECT and REMOVE any section named "REASONING PHASE", "ANALYSIS", or similar IF it asks the model to "explain", "document", "describe", or "summarize" its findings.{htr_rule}
       - WE DO NOT WANT A REPORT. We want JSON.
       
    3. **INTEGRATED REASONING**:
       - Ensure the "Search/Locate" instructions are kept inside the "TASKS" section for each field.
       - Example: "For 'date', locate the header 'Fecha' and extract value." (Keep this).
       - Example: "Write a paragraph explaining where you found the date." (DELETE THIS).
       
    4. **TAG INJECTION (CRITICAL)**: 
       - In the Tasks section, ensure the specific tag `{{{{variable_name:name}}}}` is placed next to every field ID.
       - EXAMPLE: For field "rut_trabajador", write: `rut_trabajador {{{{rut_trabajador:name}}}}`.
       - DO NOT use the literal word "ID" inside the brackets like `{{{{ID:...}}}}`.

    5. **LANGUAGE ENFORCEMENT**: 
       - Translate all *instructions*, *reasoning steps*, and *descriptions* into **PROFESSIONAL ENGLISH**.
       - **CRITICAL EXCEPTION**: Do NOT translate the **JSON Keys** or the **Variables** inside curly braces.

    6. **VARIABLE PROTECTION PROTOCOL**:
       - If the required key is `fecha_inicio`, the instruction MUST look like: 
         "Extract the start date and assign it to the field `fecha_inicio`."
       - The tag MUST remain: `{{{{fecha_inicio:name}}}}`. 
       - NEVER change `{{{{fecha_inicio:name}}}}` to `{{{{start_date:name}}}}`.

    7. **JSON EXAMPLE GENERATION (CRITICAL - SPANISH SCHEMA)**:
       You MUST write a "SECTION 3: JSON EXAMPLE" at the end.
       
       ✅ CORRECT FORMAT (MUST USE):
       {{
          "347": {{
              "valor": "B12345678",
              "confianza": 0.89,
              "Estado": "Aprobado"
          }},
          "15188": {{
              "valor": "2026-01-28",
              "confianza": 0.95,
              "Estado": "Aprobado"
          }}
       }}

       INSTRUCTIONS FOR JSON:
       - Use "valor", "confianza", "Estado".
       - Do NOT use placeholders. Generate REALISTIC DUMMY DATA.
       - Use dot (.) for decimals to ensure valid JSON syntax (e.g., 0.76).

    OUTPUT:
    Return ONLY the final prompt text.
    """

    try:
        # CAMBIO: Usamos client_brain
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": enforcer_prompt}], 
            temperature=0.1
        )
        cleaned_content = response.choices[0].message.content.strip()
        cleaned_content = re.sub(r"```.*?", "", cleaned_content).strip()
        return cleaned_content

    except Exception as e:
        print(f"      ❌ Error en Agente de Sintaxis: {e}")
        return full_prompt_text
              
def configurator_node(state):
    # --- CONFIGURADOR REFORZADO: MÁXIMA DETECCIÓN ---
    if state.get('expected_data') and state.get('rules'): return {}
    
    raw_text = state.get('raw_ground_truth', "").strip()
    if not raw_text: 
        print("      ⚠️ Advertencia: El archivo de datos esperados está vacío.")
        return {"expected_data": {}, "rules": {}}

    # Intento 1: Parseo directo de JSON
    try:
        direct_json = json.loads(raw_text)
        expected_data = {}; rules = {}
        for key, val in direct_json.items():
            clean_key = str(key).strip()
            if isinstance(val, dict) and "value" in val:
                expected_data[clean_key] = val
            else:
                expected_data[clean_key] = {"value": str(val), "status": "approved"}
            # Auto-asignación de regla de fecha si el valor parece ISO
            if re.match(r"^\d{4}-\d{2}-\d{2}$", str(expected_data[clean_key]["value"])):
                rules[clean_key] = "date_match"
            else:
                rules[clean_key] = "equals"
        return {"expected_data": expected_data, "rules": rules}
    except: pass

    # Intento 2: ARQUITECTO REFORZADO (Brain)
    print("      🐢 Vía Lenta: Activando Arquitecto AI con Detección de Patrones (Brain)...")
    
    architect_prompt = f"""
    You are a Data Parsing Architect. Extract ID-VALUE pairs from this RAW TEXT.
    
    INPUT TEXT:
    "{raw_text}"

    CRITICAL INSTRUCTIONS:
    1. Look for patterns: "ID: Value", "ID - Value", or columns like "ID [Space] Value".
    2. If you see a table-like structure, the first column is the ID and the second is the Value.
    3. ASSIGN RULES: 
       - If Value is a date (YYYY-MM-DD), use "date_match".
       - If Value is long text, use "contains_fuzzy".
       - Otherwise, use "equals".
    4. IGNORE status words like "Approved", "Pending", or confidence scores.

    EXAMPLE INPUT: "21428  2025-08-01  Approved" 
    EXAMPLE OUTPUT: {{"expected_data": {{"21428": {{"value": "2025-08-01", "status": "approved"}}}}, "rules": {{"21428": "date_match"}}}}

    Respond ONLY with the JSON object.
    """
    
    try:
        # CAMBIO: Usamos client_brain
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": architect_prompt}], 
            response_format={"type": "json_object"}, 
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        config = json.loads(re.sub(r"```json|```", "", content).strip())
        
        # Validar y limpiar reglas detectadas
        if config.get("expected_data"):
            actual_data = config["expected_data"]
            actual_rules = config.get("rules", {})
            for k, v in actual_data.items():
                val = str(v.get("value", ""))
                # Refuerzo de regla de fecha por si la IA no la puso
                if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                    actual_rules[k] = "date_match"
                elif k not in actual_rules:
                    actual_rules[k] = "equals"
            return {"expected_data": actual_data, "rules": actual_rules}
        
        return {"expected_data": None, "rules": None}

    except Exception as e: 
        print(f"      ❌ ERROR EN ARQUITECTO: {e}")
        return {"expected_data": None, "rules": None}
                  
def configurator_node(state):
    # --- CONFIGURADOR REFORZADO: MÁXIMA DETECCIÓN ---
    if state.get('expected_data') and state.get('rules'): return {}
    
    raw_text = state.get('raw_ground_truth', "").strip()
    if not raw_text: 
        print("      ⚠️ Advertencia: El archivo de datos esperados está vacío.")
        return {"expected_data": {}, "rules": {}}

    # Intento 1: Parseo directo de JSON
    try:
        direct_json = json.loads(raw_text)
        expected_data = {}; rules = {}
        for key, val in direct_json.items():
            clean_key = str(key).strip()
            if isinstance(val, dict) and "value" in val:
                expected_data[clean_key] = val
            else:
                expected_data[clean_key] = {"value": str(val), "status": "approved"}
            # Auto-asignación de regla de fecha si el valor parece ISO
            if re.match(r"^\d{4}-\d{2}-\d{2}$", str(expected_data[clean_key]["value"])):
                rules[clean_key] = "date_match"
            else:
                rules[clean_key] = "equals"
        return {"expected_data": expected_data, "rules": rules}
    except: pass

    # Intento 2: ARQUITECTO REFORZADO (Brain)
    print("      🐢 Vía Lenta: Activando Arquitecto AI con Detección de Patrones (Brain)...")
    
    architect_prompt = f"""
    You are a Data Parsing Architect. Extract ID-VALUE pairs from this RAW TEXT.
    
    INPUT TEXT:
    "{raw_text}"

    CRITICAL INSTRUCTIONS:
    1. Look for patterns: "ID: Value", "ID - Value", or columns like "ID [Space] Value".
    2. If you see a table-like structure, the first column is the ID and the second is the Value.
    3. ASSIGN RULES: 
       - If Value is a date (YYYY-MM-DD), use "date_match".
       - If Value is long text, use "contains_fuzzy".
       - Otherwise, use "equals".
    4. IGNORE status words like "Approved", "Pending", or confidence scores.

    EXAMPLE INPUT: "21428  2025-08-01  Approved" 
    EXAMPLE OUTPUT: {{"expected_data": {{"21428": {{"value": "2025-08-01", "status": "approved"}}}}, "rules": {{"21428": "date_match"}}}}

    Respond ONLY with the JSON object.
    """
    
    try:
        # CAMBIO: Usamos client_brain
        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN, 
            messages=[{"role": "user", "content": architect_prompt}], 
            response_format={"type": "json_object"}, 
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        config = json.loads(re.sub(r"```json|```", "", content).strip())
        
        # Validar y limpiar reglas detectadas
        if config.get("expected_data"):
            actual_data = config["expected_data"]
            actual_rules = config.get("rules", {})
            for k, v in actual_data.items():
                val = str(v.get("value", ""))
                # Refuerzo de regla de fecha por si la IA no la puso
                if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                    actual_rules[k] = "date_match"
                elif k not in actual_rules:
                    actual_rules[k] = "equals"
            return {"expected_data": actual_data, "rules": actual_rules}
        
        return {"expected_data": None, "rules": None}

    except Exception as e: 
        print(f"      ❌ ERROR EN ARQUITECTO: {e}")
        return {"expected_data": None, "rules": None}