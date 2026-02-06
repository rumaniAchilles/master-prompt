import base64
import json
import re
from fireworks.client import Fireworks
from dotenv import load_dotenv
import os

load_dotenv()

client = Fireworks(api_key=os.getenv("FIREWORKS_API_KEY")) 
# MODELO HARDCODED PARA EVITAR ERRORES DE ENTORNO
MODEL = ""

def auto_generate_prompt_from_image(image_path, expected_data):
    print(f"🕵️‍♂️ DETECTIVE: Generando prompt analizando {len(expected_data)} campos...")

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        targets_desc = []
        for key, item in expected_data.items():
            val = str(item.get("value", ""))
            targets_desc.append(f"- ID '{key}': Target Value is '{val}'")
        
        prompt_engineering_prompt = f"""
        You are a Senior Template Architect.
        Write extraction instructions for the provided document.
        
        🔴 CRITICAL SYNTAX RULE (NON-NEGOTIABLE):
        Every single task MUST start with the keyword 'TASK', followed by the ID, a colon, and the variable tag inside double curly braces.
        
        Format:
        TASK [ID]: {{{{[ID]:name}}}} [Precise extraction instruction]
        
        ✅ CORRECT EXAMPLES:
        TASK 347: {{{{347:name}}}} Extract the tax ID found in the top right corner.
        TASK date_issue: {{{{date_issue:name}}}} Locate the issuance date and extract it.
        
        ❌ WRONG EXAMPLES (DO NOT DO THIS):
        TASK 347: Extract the tax ID... (Missing curly braces tag)
        347: {{{{347:name}}}} Extract... (Missing keyword TASK)

        TARGETS TO EXTRACT:
        {"\n".join(targets_desc)}
        
        OUTPUT REQUIREMENT:
        Return ONLY the list of tasks. Do not include introductory text, markdown headers, or explanations.
        """

        content = [
            {"type": "text", "text": prompt_engineering_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]

        response = client.chat.completions.create(
            model=MODEL, 
            messages=[{"role": "user", "content": content}], 
            temperature=0.0
        )
        
        generated_prompt = response.choices[0].message.content
        
        # Censura básica
        for key, item in expected_data.items():
            val = str(item.get("value", ""))
            if len(val) >= 3 and val in generated_prompt:
                generated_prompt = generated_prompt.replace(val, "[THE_VALUE_ON_PAPER]")
        
        return generated_prompt

    except Exception as e:
        print(f"      ❌ El Detective falló: {e}")
        return "TASK error: {{error:name}} Could not generate prompt."