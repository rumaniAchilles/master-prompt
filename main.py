import os
import fitz  # PyMuPDF
import shutil
from pathlib import Path
from app import app
from database import AgentMemory
# Importamos las herramientas para el modo "Detective"
from detective import auto_generate_prompt_from_image 
from nodes import configurator_node 
import sys
import config  # <--- NUEVO: Importamos la configuración para validarla

# Detectar si la app corre como ejecutable o como script
if getattr(sys, 'frozen', False):
    # Si es un .exe, BASE_DIR es la carpeta donde está el ejecutable
    BASE_DIR = Path(sys.executable).parent
else:
    # Si es un script .py, BASE_DIR es la carpeta donde está este archivo
    BASE_DIR = Path(__file__).resolve().parent

DOCS_DIR = BASE_DIR / "casos_docs"
PROMPTS_DIR = BASE_DIR / "prompt_textos"

# Si supera este límite, activa el Smart Pruning
MAX_PAGES_BEFORE_PRUNING = 5 

db = AgentMemory()

def sanitize_family_id(family_id):
    # Elimina espacios al inicio/final y convierte a minúsculas para evitar 
    # que "8797esp" y "8797ESP" se traten como familias distintas.
    return str(family_id).strip().lower()

def smart_page_selector(doc, expected_data=None, max_pages=10):
    """
    OPTIMIZACIÓN DE RENDIMIENTO (Búsqueda Dual):
    Escanea el texto del PDF buscando tanto las LLAVES (IDs) como los VALORES reales.
    """
    total_pages = len(doc)
    # Si el documento es corto, lo procesamos todo sin riesgos
    if total_pages <= MAX_PAGES_BEFORE_PRUNING:
        return range(total_pages)
    
    selected_indices = set()
    selected_indices.add(0) # Siempre incluimos la primera página (carátula/cabecera)
    
    if expected_data:
        print(f"      🔎 Escaneando {total_pages} páginas buscando pistas (Semántica Dual)...")
        search_terms = []
        
        # 1. Extraemos LLAVES y VALORES para usarlos como linterna
        if isinstance(expected_data, dict):
            for key, item in expected_data.items():
                search_terms.append(str(key).lower()) # La etiqueta (ej: 21428)
                val = str(item.get("value", "")).lower()
                if len(val) > 3: # Solo buscamos valores que no sean ruido (ej: fechas, CUITs)
                    search_terms.append(val)
        
        # Limpieza de términos de búsqueda
        search_terms = list(set(search_terms))
        
        # 2. Escaneo de alta velocidad por página
        for i in range(total_pages):
            if i in selected_indices: continue
            try:
                text = doc[i].get_text().lower()
                # Bajamos el umbral a 1 match para maximizar la cobertura en documentos largos
                if any(term in text for term in search_terms):
                    selected_indices.add(i)
                    # Límite de seguridad para no saturar la memoria de la IA
                    if len(selected_indices) >= max_pages: break
            except: continue
    
    # Siempre intentamos incluir la última página si hay cupo (suele tener totales/firmas)
    if len(selected_indices) < max_pages:
        selected_indices.add(total_pages - 1)
        
    return sorted(list(selected_indices))

def prepare_input_images(file_path, expected_data=None):
    """
    Prepara las imágenes necesarias. Ahora recibe el contexto completo 
    de datos para ayudar al selector de páginas.
    """
    image_paths = []
    suffix = file_path.suffix.lower()

    if suffix in [".jpg", ".jpeg", ".png", ".bmp"]:
        temp_path = f"temp_{file_path.name}"
        shutil.copy(file_path, temp_path)
        return [temp_path]

    elif suffix == ".pdf":
        try:
            doc = fitz.open(file_path)
            # PASO CLAVE: Pasamos los datos esperados para encontrar las hojas correctas
            pages_to_process = smart_page_selector(doc, expected_data=expected_data)
            print(f"      📄 PDF Optimizado ({file_path.name}): Procesando pág {pages_to_process} de {len(doc)}")
            
            for i in pages_to_process:
                page = doc[i]
                pix = page.get_pixmap(dpi=300) 
                output_path = f"temp_{file_path.stem}_p{i}.jpg"
                pix.save(output_path)
                image_paths.append(output_path)
            doc.close()
            return image_paths
        except Exception as e:
            print(f"❌ Error leyendo PDF {file_path.name}: {e}")
            return []
    else: return []

def run_family_batch(family_name):
    """
    EJECUTOR DE LOTES (BATCH RUNNER):
    Filtra estrictamente los archivos que pertenecen a la familia actual.
    """
    # --- VALIDACIÓN DE SEGURIDAD AL INICIO DEL PROCESO ---
    if not config.validate_config():
        print("❌ DETENIENDO EJECUCIÓN POR FALTA DE CREDENCIALES.")
        return None

    family_id = sanitize_family_id(family_name)

    print(f"\n{'='*60}")
    print(f"🚀 INICIANDO ENTRENAMIENTO DE FAMILIA: {family_id.upper()}")
    print(f"{'='*60}")

    search_pattern = f"expected_{family_id}_*.txt"
    all_truth_files = list(DOCS_DIR.glob(search_pattern))
    batch_queue = []
    
    print(f"📂 Escaneando directorio en busca de casos para '{family_id}'...")

    for truth_file in all_truth_files:
        case_id = truth_file.stem.replace("expected_", "")
        doc_candidates = list(DOCS_DIR.glob(f"{case_id}.*"))
        doc_path = next((c for c in doc_candidates if c.suffix.lower() in [".pdf", ".jpg", ".png", ".jpeg"]), None)
        
        if doc_path:
            batch_queue.append({
                "case_id": case_id,
                "doc_path": doc_path,
                "truth_path": truth_file
            })
    
    if not batch_queue:
        print(f"❌ No se encontraron casos válidos para la familia '{family_id}'.")
        return None

    print(f"✅ Se encontraron {len(batch_queue)} casos válidos para el lote de '{family_id}'.")

    prompt_path = PROMPTS_DIR / f"MASTER_{family_id}.txt"
    original_prompt = ""
    loaded_tactic = ""

    if prompt_path.exists():
        print(f"📘 Prompt Maestro detectado: {prompt_path.name}")
        content = prompt_path.read_text(encoding="utf-8")
        if "=== ORIGINAL PROMPT ===" in content:
            parts = content.split("=== ORIGINAL PROMPT ===")
            loaded_tactic = parts[0].replace("=== OPTIMIZED TACTIC (Family Version) ===", "").strip()
            original_prompt = parts[1].strip()
            print(f"      🧠 Táctica previa cargada ({len(loaded_tactic)} chars).")
        else:
            original_prompt = content
    else:
        # ARRANQUE EN FRÍO (Modo Detective)
        print("⚡ Prompt Maestro NO detectado. Generando SEMILLA con el primer caso...")
        seed_case = batch_queue[0]
        raw_truth = seed_case["truth_path"].read_text(encoding="utf-8")
        
        seed_conf = configurator_node({"raw_ground_truth": raw_truth, "case_id": seed_case["case_id"]})
        seed_expected = seed_conf.get('expected_data')
        
        if seed_expected is None or len(seed_expected) == 0:
            print("\n❌ ABORTANDO: El Arquitecto AI no pudo parsear los datos esperados.")
            return None 

        print(f"      ✅ Datos semilla parseados: {len(seed_expected)} campos encontrados.")
        
        # MEJORA: Pasamos seed_expected para que el selector encuentre las páginas del caso semilla
        seed_imgs = prepare_input_images(seed_case["doc_path"], expected_data=seed_expected)
        if not seed_imgs:
            print("❌ ERROR: No se pudieron generar imágenes del documento semilla.")
            return None

        original_prompt = auto_generate_prompt_from_image(seed_imgs[0], seed_expected)
        
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(original_prompt)
        print("      ✅ Prompt Maestro Semilla creado.")
        
        for img in seed_imgs:
            if os.path.exists(img): os.remove(img)

    # --- PREPARACIÓN DEL LOTE COMPLETO ---
    print(f"\n⚙️ Pre-procesando imágenes y datos para {len(batch_queue)} casos...")
    final_batch_data = []
    
    for item in batch_queue:
        raw_truth = item["truth_path"].read_text(encoding="utf-8")
        conf_res = configurator_node({"raw_ground_truth": raw_truth, "case_id": item["case_id"]})
        expected_data = conf_res.get('expected_data', {})
        rules = conf_res.get('rules', {})
        
        # MEJORA: Pasamos el diccionario completo para que el selector busque LLAVES y VALORES
        imgs = prepare_input_images(item["doc_path"], expected_data=expected_data)
        
        final_batch_data.append({
            "case_id": item["case_id"],
            "images": imgs,
            "raw_truth": raw_truth,
            "expected_data": expected_data,
            "rules": rules
        })

    initial_state = {
        "family": family_id,
        "batch_queue": final_batch_data,
        "original_prompt": original_prompt,
        "current_tactic": loaded_tactic,
        "batch_results": {},
        "avg_score": 0.0,
        "attempts": 0,
        "is_final": False,
        "best_avg_score": 0.0,
        "best_tactic": None,
        "mismatches": [],
        "tried_tactics": []
    }

    print(f"\n🔥 EJECUTANDO GRAFO DE OPTIMIZACIÓN...")
    try:
        final_output = app.invoke(initial_state)
        print(f"\n🏁 ENTRENAMIENTO FINALIZADO.")
        if final_output:
            print(f"      🏆 Score Promedio Final: {final_output.get('best_avg_score', 0):.1f}%")
    except Exception as e:
        print(f"❌ Error fatal en la ejecución del grafo: {e}")
        import traceback; traceback.print_exc()
        final_output = None

    print("🧹 Eliminando imágenes temporales...")
    for item in final_batch_data:
        for img in item["images"]:
            try:
                if os.path.exists(img): os.remove(img)
            except: pass

    return final_output

if __name__ == "__main__":
    # --- VALIDACIÓN INICIAL AL ARRANCAR ---
    if not config.validate_config():
        print("❌ Error de configuración. Revisa config.py o tu archivo .env")
        sys.exit(1)

    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    print("✅ Entorno de Achilles listo (Modo Híbrido: Azure + Fireworks). Usa la GUI para iniciar un proceso.")