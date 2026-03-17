import base64
import json
import re
from pathlib import Path
from openai import AzureOpenAI
import config  # <--- Importamos configuración centralizada

try:
    from main import BASE_DIR
except ImportError:
    import sys
    BASE_DIR = Path(__file__).resolve().parent

# ==============================================================================
# CONFIGURACIÓN DEL DETECTIVE (CEREBRO / AZURE)
# ==============================================================================
# El Detective requiere la máxima capacidad de razonamiento visual (GPT-4o)
client_brain = AzureOpenAI(
    azure_endpoint=config.AZURE_ENDPOINT,
    api_key=config.AZURE_API_KEY,
    api_version=config.AZURE_API_VERSION
)
MODEL_BRAIN = config.AZURE_DEPLOYMENT_NAME

def load_context_files():
    """Carga la Constitución y el Gold Standard para educar al Detective."""
    guide_text = "RULES: Use anchors, ISO dates, and specific formatting."
    gold_text = "Example: PHASE 1 Reasoning... PHASE 2 JSON..."
    
    try:
        path_guide = BASE_DIR / "MASTER_PROMPT_GUIDE.md"
        if path_guide.exists():
            guide_text = path_guide.read_text(encoding="utf-8")
            
        path_gold = BASE_DIR / "GOLD_STANDARD_TEMPLATE.txt"
        if path_gold.exists():
            gold_text = path_gold.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Detective Warning: Could not load context files: {e}")
        
    return guide_text, gold_text

def auto_generate_prompt_from_image(image_path, expected_data):
    print(f"🕵️‍♂️ DETECTIVE (Brain): Analizando imagen con CONTEXTO MAESTRO para {len(expected_data)} campos...")

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        # Preparar descripción de objetivos (Pista para el detective)
        targets_desc = []
        for key, item in expected_data.items():
            val = str(item.get("value", ""))
            # Añadimos una pista de tipo para ayudar al detective
            hint = "text"
            if re.match(r"^\d{4}-\d{2}-\d{2}$", val): hint = "ISO Date"
            elif re.match(r"^\d+$", val.replace(" ", "")): hint = "Numeric ID/Amount"
            
            targets_desc.append(f"- Field '{key}': Target Value is '{val}'. USE TAG: '{{{{{key}:name}}}}'")

        # Cargar contexto
        guide_content, gold_content = load_context_files()

        # --- EL PROMPT DEL DETECTIVE (ALINEADO CON CERO PÉRDIDA DE DATOS) ---
        prompt_engineering_prompt = f"""
        You are the Lead Prompt Architect.
        Your goal is to write a MASTER PROMPT for a family of documents by reverse-engineering the provided image and targets.

        📚 KNOWLEDGE BASE:
        <GUIDE>{guide_content}</GUIDE>

        🏆 GOLD STANDARD TEMPLATE:
        <TEMPLATE>{gold_content}</TEMPLATE>

        INPUT TARGETS TO REVERSE-ENGINEER:
        {"\n".join(targets_desc)}

        🔴 CRITICAL RULES:
        1. **NO HARDCODING**: Generic instructions only. Never hardcode the literal target values into the extraction steps.
        2. **ANCHORING**: Use visual anchors (headers, labels, layout positions).
        3. **EXPLICIT LOGIC (CRITICAL)**: Write the extraction steps in clear, actionable pseudo-code (e.g., "1. Locate X. 2. Evaluate Y. 3. Extract Z. 4. Fallback if missing"). If you infer a relationship (e.g., computed dates or specific formatting), document it strictly as a Business Rule.
        4. **JSON STRUCTURE (MANDATORY - SPANISH SCHEMA)**: 
           The output example in the prompt MUST use this EXACT schema for every field:
           `"key": {{ "valor": "extracted_text", "confianza": 0.95, "Estado": "Aprobado" }}`
           
           - Use "valor" (not "value").
           - Use "confianza" (not "confidence").
           - Use "Estado": "Aprobado" (not "status": "approved").

        OUTPUT REQUIREMENT:
        Write the FULL extraction instructions optimized for Llama 4 Maverick.
        End with a JSON EXAMPLE using realistic dummy data and the SPANISH SCHEMA above.
        """
        
        content = [
            {"type": "text", "text": prompt_engineering_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]

        response = client_brain.chat.completions.create(
            model=MODEL_BRAIN,
            messages=[{"role": "user", "content": content}],
            temperature=0.1
        )

        generated_prompt = response.choices[0].message.content.strip()

        # Limpieza de bloques de código
        generated_prompt = re.sub(r"```.*?", "", generated_prompt).strip()

        # Censura anti-leakage
        for key, item in expected_data.items():
            val = str(item.get("value", ""))
            if len(val) >= 4 and val in generated_prompt:
                generated_prompt = generated_prompt.replace(val, f"[VALUE_ASSOCIATED_WITH_{key}]")
        
        return generated_prompt

    except Exception as e:
        print(f"      ❌ El Detective falló: {e}")
        return "TASK error: {{error:name}} Could not generate prompt due to system error."