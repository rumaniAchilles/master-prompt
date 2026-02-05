import base64
import json
import re
from fireworks.client import Fireworks

# --- CONFIGURACIÓN ---
client = Fireworks(api_key="") 
MODEL = "accounts/achilles/deployedModels/llama4-maverick-instruct-basic-qmpsmspl" 

def auto_generate_prompt_from_image(image_path, expected_data):
    """
    DETECTIVE VISUAL (ESTANDARIZADO {{ID:NAME}}):
    Genera instrucciones usando anclajes visuales y variables estrictas.
    """
    print(f"🕵️‍♂️ DETECTIVE: Analizando Layout Visual para {len(expected_data)} campos...")

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        # Preparamos la lista de objetivos para el prompt
        targets_desc = []
        for key, item in expected_data.items():
            # Intentamos deducir un nombre legible (ej: "378" -> "Invoice Number" si existiera metadata, sino "Field_378")
            # Como no tenemos metadata extra, usaremos el ID como nombre base, pero pedimos al LLM que infiera el nombre visual.
            val = str(item.get("value", ""))
            targets_desc.append(f"- ID '{key}': Target Value to find is '{val}'")
        
        targets_block = "\n".join(targets_desc)

        prompt_engineering_prompt = f"""
        You are a Senior Template Architect.
        I will provide an image of a document and a list of TARGET VALUES (Ground Truth).
        
        YOUR GOAL:
        Create a precise "Master Layout Description" to extract these fields.
        
        CRITICAL FORMATTING RULE (STRICT ENFORCEMENT):
        You MUST define extraction targets using ONLY this syntax:
        {{{{ID:name}}}}
        
        - ID: The exact numeric/string ID from the list provided.
        - name: You MUST use the literal word "name" as the suffix. Do NOT use descriptive labels like "CUIT" or "Date".
        
        EXAMPLES:
        - ✅ RIGHT: "Locate the CUIT value. Capture as {{{{347:name}}}}."
        - ✅ RIGHT: "Find the total amount. Capture as {{{{102:name}}}}."
        
        - ❌ WRONG: "{{{{347:CUIT}}}}" (Do not change 'name')
        - ❌ WRONG: "{{{{347}}}}" (Missing suffix)

        TARGETS TO MAP:
        {targets_block}
        
        OUTPUT STRUCTURE (Markdown):
        
        ### LAYOUT ANALYSIS
        (Briefly describe document structure).
        
        ### EXTRACTION INSTRUCTIONS
        1. **Region Identification**: (Instructions to find main sections).
        2. **Field Mapping**:
           - Look for [Visual Anchor]... capture {{{{ID:name}}}}.
           (Repeat for ALL targets using 'name' suffix).
        """

        content = [
            {"type": "text", "text": prompt_engineering_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]

        response = client.chat.completions.create(
            model=MODEL, 
            messages=[{"role": "user", "content": content}], 
            temperature=0.1
        )
        
        generated_prompt = response.choices[0].message.content
        
        # --- 🛡️ PROTOCOLO DE CENSURA (ANTI-LEAKAGE) 🛡️ ---
        print("      🛡️ Aplicando censura y validación de formato...")
        
        for key, item in expected_data.items():
            val = str(item.get("value", ""))
            # 1. Censura: Borrar el valor real si se filtró
            if len(val) >= 3 and val in generated_prompt:
                generated_prompt = generated_prompt.replace(val, "[VALUE_MASKED]")
        
        # Validación extra: ¿Usó las llaves?
        if "{{" not in generated_prompt:
            print("      ⚠️ Advertencia: El Detective no usó formato {{}}. Forzando post-proceso simple.")
            # (Aquí podrías agregar lógica para forzarlo, pero Llama 4 suele obedecer bien)

        return generated_prompt

    except Exception as e:
        print(f"      ❌ El Detective falló: {e}")
        return "ERROR: Could not generate prompt."