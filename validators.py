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
    
    # 2. TRUCO DE MESES (Ayuda a fechas escritas en validaciones de texto plano)
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
        """
        Igualdad flexible: 
        1. Compara normalizado (respetando palabras).
        2. Si falla, compara SIN ESPACIOS (ideal para IDs '947 449' vs '947449').
        """
        norm_ext = normalize_string(extracted)
        norm_exp = normalize_string(expected)
        
        # 1. Intento Directo (Juan Perez == JUAN PEREZ)
        if norm_ext == norm_exp: 
            return True
        
        # 2. Intento Sin Espacios (947 449 842 == 947449842)
        if norm_ext.replace(" ", "") == norm_exp.replace(" ", ""):
            return True
            
        return False

    @staticmethod
    def script_strict_equals(extracted, expected, **kwargs):
        """Igualdad exacta caracter por caracter."""
        return str(extracted).strip() == str(expected).strip()

    @staticmethod
    def script_percentage_match(extracted, expected, threshold=0.4, **kwargs):
        """Comparación difusa por porcentaje de similitud (Levenshtein)."""
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
        e1_tokens = set(normalize_string(extracted).split())
        e2_tokens = set(normalize_string(expected).split())
        return e2_tokens.issubset(e1_tokens) or e1_tokens.issubset(e2_tokens)

    @staticmethod
    def script_date_match(extracted, expected, **kwargs):
        """
        COMPARADOR UNIVERSAL DE FECHAS
        Entiende: '2025-10-22' == '22 de octubre de 2025' == '22/10/25'
        Soporta: Español, Inglés, Italiano, Portugués.
        """
        def parse_smart_date(val):
            if not val: return None
            val_clean = str(val).upper().strip()
            
            # 1. Mapa de Meses Multilingüe
            months = {
                "JANUARY": "01", "ENERO": "01", "GENNAIO": "01", "JANEIRO": "01",
                "FEBRUARY": "02", "FEBRERO": "02", "FEBBRAIO": "02", "FEVEREIRO": "02",
                "MARCH": "03", "MARZO": "03", "MARCO": "03",
                "APRIL": "04", "ABRIL": "04", "APRILE": "04",
                "MAY": "05", "MAYO": "05", "MAGGIO": "05", "MAIO": "05",
                "JUNE": "06", "JUNIO": "06", "GIUGNO": "06", "JUNHO": "06",
                "JULY": "07", "JULIO": "07", "LUGLIO": "07", "JULHO": "07",
                "AUGUST": "08", "AGOSTO": "08", "AGO": "08",
                "SEPTEMBER": "09", "SEPTIEMBRE": "09", "SETTEMBRE": "09", "SETEMBRO": "09", "SEP": "09", "SET": "09",
                "OCTOBER": "10", "OCTUBRE": "10", "OTTOBRE": "10", "OUTUBRO": "10", "OCT": "10",
                "NOVEMBER": "11", "NOVIEMBRE": "11", "NOVEMBRE": "11", "NOV": "11",
                "DECEMBER": "12", "DICIEMBRE": "12", "DICEMBRE": "12", "DEZEMBRO": "12", "DIC": "12"
            }
            
            # Reemplazo de palabras por números
            for name, num in months.items():
                if name in val_clean:
                    val_clean = val_clean.replace(name, num)
            
            # Limpieza de conectores ("DE", "DEL", "OF")
            val_clean = re.sub(r'\b(DE|DEL|OF|THE)\b', ' ', val_clean)
            # Limpieza de símbolos (deja solo números y espacios)
            val_clean = re.sub(r'[^0-9]', ' ', val_clean)
            
            # Normalización de espacios
            parts = val_clean.split()
            
            if len(parts) == 3:
                # Intentamos adivinar formato: YMD, DMY, MDY
                try:
                    p1, p2, p3 = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    # Caso ISO: 2025 10 22
                    if p1 > 1900: 
                        return datetime(p1, p2, p3)
                    # Caso Invertido: 22 10 2025
                    if p3 > 1900:
                        return datetime(p3, p2, p1)
                except: pass
            return None

        # Intentamos parsear ambas fechas como objetos datetime
        d1 = parse_smart_date(extracted)
        d2 = parse_smart_date(expected)

        # Si ambas son fechas válidas, comparamos los objetos (ignora formato texto)
        if d1 and d2:
            return d1 == d2
        
        # Si falla el parseo, fallback a comparación de texto normalizada
        return normalize_string(extracted) == normalize_string(expected)

def validate_result(actual, expected, rules):
    # --- CORRECCIÓN CRÍTICA: ANTI-CRASH /0 ---
    # Si no hay datos esperados, devolvemos 0.0 inmediatamente y un error claro
    if not expected:
        return ["ERROR CRÍTICO: No se encontraron datos esperados contra los cuales validar."], 0.0

    # Validación de estructura básica
    if not actual or not isinstance(actual, dict): 
        return ["ERROR: La IA no devolvió un formato JSON válido (Formato de salida inválido)"], 0.0
    
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
        
        # --- MAPEO INTELIGENTE DE REGLAS DEL JUEZ (ALIASES) ---
        if rule_name == "contains_full": rule_name = "contains_fuzzy"
        if rule_name == "contains_related": rule_name = "contains"
        if "date" in rule_name.lower() or "iso" in rule_name.lower(): 
            rule_name = "date_match"
        
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
            
    # --- CÁLCULO SEGURO ---
    total = len(expected)
    if total > 0:
        return mismatches, (correct / total) * 100
    else:
        return ["ERROR: Archivo de expected vacío"], 0.0