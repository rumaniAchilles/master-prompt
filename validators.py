import re, unicodedata, difflib
from datetime import datetime
import string

def normalize_string(text):
    """
    Normalización base: Mayúsculas, unificación de comillas y limpieza de puntuación.
    IMPORTANTE: Mantiene espacios simples para permitir tokenización (comparar palabras).
    """
    if not text: return ""
    # Convertimos a mayúsculas
    text = str(text).upper()
    
    # 1. TRUCO DE COMILLAS: Unificar curvas y rectas
    text = text.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
    
    # 2. TRUCO DE MESES (Ayuda a fechas escritas)
    replacements = {"AGOSTO": "08", "JULIO": "07", "SETTEMBRE": "09", "SEPTIEMBRE": "09"} 
    for mes, num in replacements.items():
        text = text.replace(mes, num)
        
    # Eliminamos todos los signos de puntuación (.,-;: etc)
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Normalizamos espacios: Elimina dobles espacios y deja solo uno entre palabras
    return " ".join(text.split())

class InfocontrolValidators:
    @staticmethod
    def normalize_text(text):
        return str(text).strip().lower()

    @staticmethod
    def script_equals(extracted, expected, **kwargs):
        """Igualdad estricta (pero agnóstica de mayúsculas/espacios extra)."""
        # Para IDs, a veces conviene ignorar espacios internos, aquí confiamos en normalize_string
        # Si quieres ser muy estricto con IDs espaciados, podrías comparar .replace(" ", "") aquí dentro.
        return normalize_string(extracted) == normalize_string(expected)

    @staticmethod
    def script_strict_equals(extracted, expected, **kwargs):
        return str(extracted).strip() == str(expected).strip()

    @staticmethod
    def script_percentage_match(extracted, expected, threshold=0.4, **kwargs):
        s1, s2 = str(extracted).upper(), str(expected).upper()
        return difflib.SequenceMatcher(None, s1, s2).ratio() >= float(threshold)

    @staticmethod
    def script_contains(extracted, expected, **kwargs):
        """Verifica si el valor esperado está contenido dentro del extraído."""
        e1, e2 = normalize_string(extracted), normalize_string(expected)
        return e2 in e1

    @staticmethod
    def script_contains_fuzzy(extracted, expected, **kwargs):
        """
        Verifica si TODAS las palabras del esperado están en el extraído, 
        sin importar el orden. (Ideal para Nombres Invertidos: 'Kevin Javier' == 'Javier Kevin')
        """
        # Creamos sets de palabras únicas
        e1_tokens = set(normalize_string(extracted).split())
        e2_tokens = set(normalize_string(expected).split())
        
        # ¿Están todos los tokens de la expectativa dentro de lo extraído?
        # (O viceversa, por si el extraído es parcial)
        return e2_tokens.issubset(e1_tokens) or e1_tokens.issubset(e2_tokens)

    @staticmethod
    def script_comparison_dates(extracted, expected, **kwargs):
        try:
            # Intenta normalizar formatos de fecha para que coincidan (ISO format)
            d1 = datetime.strptime(str(extracted).strip(), "%Y-%m-%d")
            d2 = datetime.strptime(str(expected).strip(), "%Y-%m-%d")
            return d1 == d2
        except:
            # Fallback a igualdad de texto si falla el parseo de fecha
            return InfocontrolValidators.script_equals(extracted, expected)

def validate_result(actual, expected, rules):
    # Validación de estructura básica
    if not actual or not isinstance(actual, dict): 
        return ["ERROR: Formato de salida inválido"], 0.0
    
    mismatches, correct = [], 0
    validator = InfocontrolValidators()

    for field, exp_obj in expected.items():
        # 1. Extracción segura del valor REAL
        act_obj = actual.get(field, {})
        val_act = str(act_obj.get('value', act_obj)) if isinstance(act_obj, dict) else str(act_obj)
        
        # 2. Extracción segura del valor ESPERADO
        val_exp = str(exp_obj.get('value', ''))
        
        # 3. Determinación de la REGLA
        rule_cfg = rules.get(field, "equals")
        rule_name = rule_cfg.get("rule", "equals") if isinstance(rule_cfg, dict) else rule_cfg
        
        # --- MAPEO INTELIGENTE DE REGLAS DEL JUEZ ---
        # Si el Optimizador sugiere reglas nuevas, las redirigimos a los métodos que sí existen
        if rule_name == "contains_full": rule_name = "contains_fuzzy" # Redirección clave para nombres
        if rule_name == "contains_related": rule_name = "contains"
        
        is_match = False

        try:
            # Intentamos ejecutar el método correspondiente dinámicamente
            method_name = f"script_{rule_name}"
            
            if hasattr(validator, method_name):
                method = getattr(validator, method_name)
                if method(val_act, val_exp):
                    is_match = True
            else:
                # Fallback a equals si la regla no existe
                if validator.script_equals(val_act, val_exp):
                    is_match = True
                    
        except Exception as e:
            print(f"Error validando {field}: {e}")

        # --- CÁLCULO DE SCORE ---
        if is_match:
            correct += 1
        else:
            # LOG DETALLADO
            mismatches.append(f"ID {field}: Esperado '{val_exp}' vs Real '{val_act}' ({rule_name})")
            
    return mismatches, (correct / len(expected)) * 100