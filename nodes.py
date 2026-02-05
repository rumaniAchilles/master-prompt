import base64, json, re
from fireworks.client import Fireworks
from validators import validate_result
from database import AgentMemory

# --- CONFIGURACIÓN ---
client = Fireworks(api_key="")
db = AgentMemory()
MODEL = "accounts/achilles/deployedModels/llama4-maverick-instruct-basic-qmpsmspl"

def extraction_node(state):
    print(f"\n[PASO: EXTRACCIÓN MASIVA] 🤖 Procesando lote de {len(state['batch_queue'])} documentos...")
    
    batch_results = state.get("batch_results", {})
    tactic = state.get("current_tactic", "")
    
    # Iteramos sobre cada documento del lote
    for case in state["batch_queue"]:
        cid = case["case_id"]
        # (Opcional) Log para ver progreso
        # print(f"   🔹 Procesando Caso {cid}...")
        
        # 1. Preparación del Prompt
        final_prompt = state["original_prompt"]
        
        # 2. Instrucción de Formato JSON
        keys = list(case["expected_data"].keys())
        schema_instruction = f"""
        OUTPUT SCHEMA: Return a JSON object with these EXACT keys:
        {json.dumps(keys)}
        Each value must be an object: {{"value": "extracted info", "status": "approved"}}
        """
        
        full_prompt = f"{schema_instruction}\n\nTACTIC:\n{tactic}\n\nTASK:\n{final_prompt}"
        
        # 3. Llamada al Modelo
        content = [{"type": "text", "text": full_prompt}]
        for img_path in case["images"]:
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })
            except: pass

        try:
            response = client.chat.completions.create(
                model=MODEL, 
                messages=[{"role": "user", "content": content}], 
                response_format={"type": "json_object"},
                temperature=0
            )
            raw_content = response.choices[0].message.content
            clean_json = re.sub(r"```json|```", "", raw_content).strip()
            
            match = re.search(r"\{.*\}", clean_json, re.DOTALL)
            data = json.loads(match.group(0)) if match else {}
            
        except Exception as e:
            print(f"      ❌ Error en {cid}: {e}")
            data = {}

        # Guardamos resultado
        batch_results[cid] = {
            "extraction": data,
            "expected": case["expected_data"]
        }

    return {"batch_results": batch_results, "attempts": state["attempts"] + 1}


def validation_node(state):
    print(f"[PASO: VALIDACIÓN CRUZADA] ⚖️ Calculando Score Promedio...")
    
    total_score = 0.0
    current_results = state.get("batch_results", {})
    total_cases = len(current_results)
    
    global_mismatches = [] 
    
    for cid, res in current_results.items():
        mismatches, score = validate_result(
            res["extraction"], 
            res["expected"], 
            state.get("rules", {})
        )
        
        total_score += score
        
        if mismatches:
            for m in mismatches:
                global_mismatches.append(f"[CASE {cid}] {m}")
        
        current_results[cid]["score"] = score
        current_results[cid]["mismatches"] = mismatches

    avg_score = total_score / total_cases if total_cases > 0 else 0
    print(f"      📊 Score Promedio del Lote: {avg_score:.1f}% (Mejor anterior: {state['best_avg_score']:.1f}%)")

    best_avg = state["best_avg_score"]
    best_tac = state["best_tactic"]
    
    if avg_score >= best_avg:
        best_avg = avg_score
        best_tac = state.get("current_tactic")
        if avg_score > 0:
            print("      📈 ¡Nueva Táctica Líder!")

    # Decisión de Salida
    is_final = False
    if avg_score >= 98.0 or state["attempts"] >= 5:
        is_final = True
        if best_tac:
            save_master_prompt(state["family"], state["original_prompt"], best_tac)
    else:
        # Guardamos fallos
        db.save_failure(state["family"], state.get("current_tactic"), global_mismatches[:5])

    # RETORNAMOS 'mismatches' PARA QUE EL OPTIMIZADOR LOS VEA
    return {
        "avg_score": avg_score,
        "batch_results": current_results,
        "is_final": is_final,
        "best_avg_score": best_avg,
        "best_tactic": best_tac,
        "mismatches": global_mismatches 
    }


def optimizer_node(state):
    print(f"[PASO: OPTIMIZACIÓN] 🔧 El Arquitecto está fusionando conocimientos y auditando reglas...")
    
    # 1. Recuperar datos
    current_mismatches = state.get('mismatches', [])
    # Si es la primera vuelta, la táctica es vacía o es la semilla.
    previous_tactic = state.get('current_tactic', "")
    if not previous_tactic:
        previous_tactic = "(No specific tactic yet. Base extraction relies on the Original Prompt tasks.)"
    
    # 2. Recuperamos fallos previos (Memoria)
    recent_failures = db.get_recent_failures(state['family'])
    forbidden_zone = ""
    if recent_failures:
        forbidden_zone = "⛔ FORBIDDEN TACTICS (PREVIOUSLY FAILED):\n"
        for i, f in enumerate(recent_failures, 1):
            if f: forbidden_zone += f"{i}. {str(f)[:150]}...\n"

    # 3. Cargar la Guía Maestra (Contexto Pasivo)
    try:
        with open("MASTER_PROMPT_GUIDE.md", "r", encoding="utf-8") as f:
            master_guide = f.read()
    except:
        master_guide = "General Rule: Be precise and robust against OCR errors."

    # 4. Preparar Contexto de Ejecución
    # Solo mostramos una muestra de errores para no saturar
    errors_summary = json.dumps(current_mismatches[:15], indent=2)
    current_rules = json.dumps(state.get('rules', {}), indent=2)

    # --- PROMPT BLINDADO ---
    opt_prompt = f"""
    You are the Lead Prompt Engineer for a Document Extraction AI.
    
    CONTEXT:
    We are extracting specific fields from a document family.
    The system uses a "Master Prompt" composed of:
    1. TACTIC (Your output): Specific corrections and strategic rules.
    2. TASK (Original Prompt): The base visual layout instructions.

    REFERENCE GUIDE (THE "CONSTITUTION"):
    {master_guide}
    --------------------------------------------------
    {forbidden_zone}

    INPUT DATA:
    - Current Tactic: {previous_tactic}
    - Extraction Errors: {errors_summary}
    - Validation Rules: {current_rules}

    YOUR MISSION:
    Rewrite the "TACTIC" to fix the reported errors.
    
    CRITICAL RULES FOR YOUR OUTPUT:
    1. 🚫 DO NOT COPY THE GUIDE: Do NOT output sections like "## 1. FILOSOFÍA DE ANCLAJE". That is for YOU to read, not to write.
    2. ✅ BE SPECIFIC: Write strict, executable instructions for the fields that failed.
       - Bad: "Use relative anchoring." (Too generic)
       - Good: "For field {{347:CUIT}}, ignore the header 'Empresa' and capture the 11 digits below 'Sujeto Retenido'."
    3. ✅ PRESERVE FORMAT: You MUST refer to fields using the syntax {{{{ID:name}}}}.
       - ALWAYS use the literal suffix ":name".
       - Example: Use {{{{347:name}}}}, NEVER {{{{347:CUIT}}}}.
    4. ✅ FIX OCR ISSUES: If the error is splitting digits (e.g. "2 0 2 5" -> "2025"), write a specific rule for that field to join spaces.

    OUTPUT FORMAT (STRICT JSON):
    {{
        "tactic": "The refined, specific instructions (markdown format). Start with '### EXTRACTION STRATEGY'.",
        "rule_updates": {{ "field_id": "new_rule_type" }} 
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": opt_prompt}],
            response_format={"type": "json_object"}, 
            temperature=0.1 # Bajamos temperatura para reducir creatividad teórica
        )
        
        res_json = json.loads(re.sub(r"```json|```", "", response.choices[0].message.content).strip())
        new_tactic = res_json.get("tactic", previous_tactic)
        rule_updates = res_json.get("rule_updates", {})
        
        # --- Censura Anti-Trampa ---
        if state.get('expected_data'):
            for key, item in state['expected_data'].items():
                val_real = str(item.get("value", "")).strip()
                if len(val_real) >= 4 and val_real in new_tactic:
                    print(f"      🚫 ALERTA: Censurando valor real '{val_real}' en la táctica.")
                    new_tactic = new_tactic.replace(val_real, f"{{{{VALUE_FOR_{key}}}}}")

        if rule_updates:
            print(f"      ⚖️ JUEZ: Ajustando reglas rígidas: {rule_updates}")
            updated_rules = state.get('rules', {}).copy()
            for field, new_rule in rule_updates.items():
                if isinstance(updated_rules.get(field), dict):
                    updated_rules[field]['rule'] = new_rule
                else:
                    updated_rules[field] = new_rule
            return {"current_tactic": new_tactic, "rules": updated_rules}
        
        return {"current_tactic": new_tactic}
        
    except Exception as e:
        print(f"      ❌ Error optimizador: {e}")
        return {"current_tactic": state.get('current_tactic', "")}

def save_master_prompt(family, original, tactic):
    """Guarda el archivo maestro final"""
    content = f"=== OPTIMIZED TACTIC (Family Version) ===\n{tactic}\n\n=== ORIGINAL PROMPT ===\n{original}"
    import os
    with open(f"prompt_textos/MASTER_{family}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    print("      💾 Protocolo Maestro Actualizado.")


def configurator_node(state):
    """NODO ARQUITECTO DE DATOS"""
    # Si ya tenemos datos, no hacemos nada
    if state.get('expected_data') and state.get('rules'):
        return {}

    raw_text = state.get('raw_ground_truth', "")
    case_id = state.get('case_id', "unknown")
    
    expected_data = {}
    rules = {}

    # Intento 1: JSON Directo
    try:
        direct_json = json.loads(raw_text)
        # Normalización
        for key, val in direct_json.items():
            clean_key = str(key).strip('"').strip("'").strip()
            if isinstance(val, dict) and "value" in val:
                expected_data[clean_key] = val
                if "status" not in expected_data[clean_key]:
                    expected_data[clean_key]["status"] = "approved"
            else:
                expected_data[clean_key] = {"value": str(val), "status": "approved"}
            rules[clean_key] = "equals"
        return {"expected_data": expected_data, "rules": rules}
    except:
        pass

    # Intento 2: Arquitecto LLM
    print(f"      🐢 Vía Lenta: Detectado texto no estructurado. Activando Arquitecto AI...")
    architect_prompt = f"""
    You are a Data Parsing Architect.
    Convert this raw text into structured JSON.
    RAW INPUT: "{raw_text}"
    OUTPUT JSON: {{ "expected_data": {{ "ID": {{ "value": "val", "status": "approved" }} }}, "rules": {{ "ID": "equals" }} }}
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": architect_prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        clean_content = re.sub(r"```json|```", "", response.choices[0].message.content).strip()
        config = json.loads(clean_content)
        return config
    except Exception as e:
        print(f"      ❌ Error Configurator: {e}")
        return {"expected_data": {}, "rules": {}}