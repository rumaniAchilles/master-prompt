import base64, json, re
from fireworks.client import Fireworks
from validators import validate_result
from database import AgentMemory
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN ---
# Usamos el modelo explícito para evitar errores si falla la variable de entorno
client = Fireworks(api_key=os.getenv("FIREWORKS_API_KEY"))
db = AgentMemory()
MODEL = ""

def extraction_node(state):
    print(f"\n[PASO: EXTRACCIÓN MASIVA] 🤖 Procesando lote de {len(state['batch_queue'])} documentos...")
    batch_results = state.get("batch_results", {})
    tactic = state.get("current_tactic", "")
    
    for case in state["batch_queue"]:
        cid = case["case_id"]
        final_prompt = state["original_prompt"]
        keys = list(case["expected_data"].keys())
        
        schema_instruction = f"""
        OUTPUT SCHEMA: Return a JSON object with these EXACT keys:
        {json.dumps(keys)}
        Each value must be an object: {{"value": "extracted info", "status": "approved"}}
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
            response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": content}], response_format={"type": "json_object"}, temperature=0)
            clean_json = re.sub(r"```json|```", "", response.choices[0].message.content).strip()
            match = re.search(r"\{.*\}", clean_json, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
        except Exception as e:
            print(f"      ❌ Error en {cid}: {e}")
            data = {}

        batch_results[cid] = {"extraction": data, "expected": case["expected_data"]}
    
    return {"batch_results": batch_results, "attempts": state["attempts"] + 1}

def validation_node(state):
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
    print(f"[PASO: OPTIMIZACIÓN] 🔧 El Arquitecto está auditando reglas, estrategia y MEMORIA HISTÓRICA...")
    
    current_mismatches = state.get('mismatches', [])
    previous_tactic = state.get('current_tactic')
    original_prompt = state.get('original_prompt', "")
    
    if not previous_tactic: previous_tactic = "(No specific tactic yet.)"
    
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
    
    try:
        with open("MASTER_PROMPT_GUIDE.md", "r", encoding="utf-8") as f: constitution = f.read()
    except: constitution = "RULES: Use {{ID:name}} syntax. Dates to ISO."

    opt_prompt = f"""
    You are the Lead Prompt Engineer.
    
    📜 CONSTITUTION:
    {constitution}
    
    INPUT CONTEXT:
    1. BASE INSTRUCTIONS (The User's Original Intent - DO NOT CONTRADICT UNLESS NECESSARY):
    "{original_prompt}"
    
    2. CURRENT REFINEMENT TACTIC (This failed):
    "{previous_tactic}"
    
    3. ⛔ KNOWN FAILED TACTICS (MEMORY - DO NOT REPEAT THESE):
    {failures_context}
    
    4. EXECUTION ERRORS:
    {errors_summary}
    
    5. CURRENT RULES:
    {current_rules}
    
    🔴 CRITICAL SYNTAX REQUIREMENT:
    You MUST refer to the fields using ONLY these variables: [{vars_instruction}]

    YOUR MISSION:
    Fix the errors by updating the TACTIC or the RULES.
    
    STRATEGY:
    - If the Base Instruction is ignored, REINFORCE it.
    - If the Base Instruction is wrong, refine it in the tactic.
    - Avoid strategies listed in "Known Failed Tactics".
    
    🚨 OUTPUT FORMAT RULES (STRICT):
    1. Field "tactic": MUST contain ONLY the new instructions/rules. 
       - NO conversational text.
       - JUST the directive sentences (e.g., "For ID 21428, convert date to ISO format.").
    2. Field "rule_updates": Use only if validation logic needs changing.

    OUTPUT FORMAT (JSON):
    {{
        "tactic": "For {{21428:name}}, ensure the date is converted to YYYY-MM-DD...",
        "rule_updates": {{ "ID": "name" }} 
    }}
    """
    
    try:
        response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": opt_prompt}], response_format={"type": "json_object"}, temperature=0.1)
        res_json = json.loads(re.sub(r"```json|```", "", response.choices[0].message.content).strip())
        new_tactic = res_json.get("tactic", previous_tactic)
        rule_updates = res_json.get("rule_updates", {})
        
        # Censura anti-leakage
        if state.get('expected_data'):
            for key, item in state['expected_data'].items():
                val_real = str(item.get("value", "")).strip()
                if len(val_real) >= 4 and val_real in new_tactic:
                    new_tactic = new_tactic.replace(val_real, f"{{{{VALUE_FOR_{key}}}}}")

        if rule_updates:
            print(f"      ⚖️ JUEZ (Cambios en Reglas):")
            updated_rules = state.get('rules', {}).copy()
            for field, new_rule in rule_updates.items():
                clean_id = str(field).split(":")[0].strip()
                print(f"         - ID '{clean_id}': Se cambia a regla '{new_rule}'")
                if isinstance(updated_rules.get(clean_id), dict): updated_rules[clean_id]['rule'] = new_rule
                else: updated_rules[clean_id] = new_rule
            return {"current_tactic": new_tactic, "rules": updated_rules}
        
        elif new_tactic != previous_tactic:
            print("      📝 EL ARQUITECTO REESCRIBIÓ LA TÁCTICA.")
            return {"current_tactic": new_tactic}
        else:
            return {"current_tactic": new_tactic + "\n\n(Re-evaluating formatting rules)"}
        
    except Exception as e:
        print(f"      ❌ Error optimizador: {e}")
        return {"current_tactic": state.get('current_tactic', "")}

def save_master_prompt(family, original, tactic):
    content = f"=== OPTIMIZED TACTIC (Family Version) ===\n{tactic}\n\n=== ORIGINAL PROMPT ===\n{original}"
    import os
    with open(f"prompt_textos/MASTER_{family}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    print("      💾 Protocolo Maestro Actualizado.")

def syntax_enforcer_agent(full_prompt_text, expected_keys):
    """
    AGENTE FINALIZADOR: Inyecta etiquetas y limpia el output usando XML tags.
    """
    print(f"      👮‍♂️ AGENTE DE SINTAXIS: Formateando prompt para {len(expected_keys)} variables...")
    if not expected_keys: return full_prompt_text

    enforcer_prompt = f"""
    You are a Syntax Compliance Bot.
    Your ONLY job is to inject variable tags into a prompt.

    INPUT DATA:
    1. PROMPT TEXT:
    "{full_prompt_text}"

    2. REQUIRED VARIABLES (Keys):
    {json.dumps(expected_keys)}

    INSTRUCTIONS:
    - Scan the PROMPT TEXT.
    - Whenever you see a reference to one of the Keys (e.g., "TASK 347", "Field 21428"), insert the strict syntax tag `{{{{KEY:name}}}}` immediately after the ID.
    - Example: "TASK 347: Extract..." -> "TASK 347: {{{{347:name}}}} Extract..."
    - DO NOT change the extraction logic.
    - DO NOT remove text.

    🔴 CRITICAL OUTPUT RULE:
    Wrap your final response inside <OUTPUT> tags. 
    Example:
    <OUTPUT>
    === OPTIMIZED TACTIC...
    ...
    </OUTPUT>
    """

    try:
        response = client.chat.completions.create(
            model=MODEL, 
            messages=[{"role": "user", "content": enforcer_prompt}], 
            temperature=0.0
        )
        raw_content = response.choices[0].message.content.strip()
        
        match = re.search(r"<OUTPUT>(.*?)</OUTPUT>", raw_content, re.DOTALL)
        
        if match:
            # Limpiamos markdown si el modelo lo puso dentro del tag
            return re.sub(r"```.*?", "", match.group(1).strip()).strip()
        else:
            # Fallback
            return re.sub(r"```.*?", "", raw_content).strip()

    except Exception as e:
        print(f"      ❌ Error en Agente de Sintaxis: {e}")
        return full_prompt_text
    
def configurator_node(state):
    # --- CONFIGURADOR ROBUSTO: LA CLAVE PARA QUE NO FALLE SIN PROMPT BASE ---
    
    # Si ya tenemos datos parseados, salimos (Caso feliz)
    if state.get('expected_data') and state.get('rules'): return {}
    
    raw_text = state.get('raw_ground_truth', "").strip()
    if not raw_text: 
        print("      ⚠️ Advertencia: El archivo de datos esperados está vacío.")
        return {"expected_data": {}, "rules": {}}

    # Intento 1: Parseo directo de JSON (si el usuario es ordenado)
    try:
        direct_json = json.loads(raw_text)
        expected_data = {}
        rules = {}
        for key, val in direct_json.items():
            clean_key = str(key).strip('"').strip("'").strip()
            if isinstance(val, dict) and "value" in val:
                expected_data[clean_key] = val
                if "status" not in expected_data[clean_key]: expected_data[clean_key]["status"] = "approved"
            else:
                expected_data[clean_key] = {"value": str(val), "status": "approved"}
            rules[clean_key] = "equals"
        return {"expected_data": expected_data, "rules": rules}
    except: pass

    # Intento 2: ARQUITECTO INTELIGENTE (Para Tablas o Texto Pegado)
    print("      🐢 Vía Lenta: Detectado texto no estructurado. Activando Arquitecto AI...")
    
    architect_prompt = f"""
    You are a Data Parsing Architect.
    Your goal is to extract valid ID-VALUE pairs from a raw text dump.

    RAW INPUT:
    "{raw_text}"

    INSTRUCTIONS:
    1. Analyze the text structure. It typically follows patterns like:
       - "ID: Value"
       - "Label  Confidence  Content  Status" (IGNORE Confidence/Status, use Content as Value)
       - Tab separated values
    2. IGNORE columns like:
       - Confidence scores
       - Status words ("Approved", "Rejected")
    3. EXTRACT only the meaningful content.
    4. Auto-Assign RULES: Dates -> "date_match", Numbers -> "equals", Long text -> "contains_fuzzy".

    OUTPUT FORMAT (Strict JSON):
    {{
        "expected_data": {{ 
            "ID_HERE": {{ "value": "CLEAN_VALUE", "status": "approved" }}
        }},
        "rules": {{
            "ID_HERE": "equals"
        }}
    }}
    """
    
    try:
        response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": architect_prompt}], response_format={"type": "json_object"}, temperature=0)
        config = json.loads(re.sub(r"```json|```", "", response.choices[0].message.content).strip())
        
        # Verificación extra: Si devolvió vacío, avisamos
        if not config.get("expected_data"):
             print("      ❌ El Arquitecto no pudo extraer datos del texto.")
        
        return config
    except Exception as e: 
        print(f"      ❌ Error en Arquitecto: {e}")
        return {"expected_data": {}, "rules": {}}