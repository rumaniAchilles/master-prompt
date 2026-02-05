import os
import fitz  # PyMuPDF
import shutil
from pathlib import Path
from app import app
from database import AgentMemory
# Importamos las herramientas para el modo "Detective"
from detective import auto_generate_prompt_from_image 
from nodes import configurator_node 

# --- CONFIGURACIÓN ---
BASE_DIR = Path(os.getcwd())
DOCS_DIR = BASE_DIR / "casos_docs"
PROMPTS_DIR = BASE_DIR / "prompt_textos"

# Si supera este límite, activa el Smart Pruning
MAX_PAGES_BEFORE_PRUNING = 5 

db = AgentMemory()

def smart_page_selector(doc, keywords=None, max_pages=6):
    """
    OPTIMIZACIÓN DE RENDIMIENTO:
    Escanea rápidamente el texto del PDF (capa OCR) para encontrar dónde están los datos.
    Retorna los índices de las páginas relevantes.
    """
    total_pages = len(doc)
    if total_pages <= max_pages:
        return range(total_pages)
    
    selected_indices = set()
    
    # 1. Siempre incluir Inicio y Fin (suelen tener cabeceras y totales)
    selected_indices.add(0)
    selected_indices.add(total_pages - 1)
    
    # 2. Búsqueda por Palabras Clave (si las tenemos)
    if keywords:
        print(f"      🔎 Escaneando {total_pages} páginas buscando pistas de datos...")
        # Convertimos keys a minúsculas para búsqueda rápida
        search_terms = [str(k).lower() for k in keywords]
        
        for i in range(total_pages):
            # No re-escanear si ya la seleccionamos
            if i in selected_indices: continue
            
            try:
                text = doc[i].get_text().lower()
                # Si encontramos al menos 2 coincidencias de campos, es una página valiosa
                matches = sum(1 for term in search_terms if term in text)
                if matches >= 2:
                    selected_indices.add(i)
                    # Si ya llenamos el cupo, paramos
                    if len(selected_indices) >= max_pages: break
            except:
                continue
    
    # 3. Relleno de seguridad (si no encontramos nada, agregamos la pág 2)
    if len(selected_indices) < 3 and total_pages > 2:
        selected_indices.add(1)
        
    return sorted(list(selected_indices))

def prepare_input_images(file_path, expected_keys=None):
    """
    Convierte Documento a Imágenes optimizadas.
    - expected_keys: Lista de IDs o nombres de campos para guiar el recorte inteligente.
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
            
            # Usamos el selector inteligente
            pages_to_process = smart_page_selector(doc, keywords=expected_keys)
            
            print(f"      📄 PDF Optimizado ({file_path.name}): Procesando pág {pages_to_process} de {len(doc)}")
            
            for i in pages_to_process:
                page = doc[i]
                # DPI 150 es suficiente para GPT-4o/LlamaVision (balance velocidad/calidad)
                pix = page.get_pixmap(dpi=150) 
                output_path = f"temp_{file_path.stem}_p{i}.jpg"
                pix.save(output_path)
                image_paths.append(output_path)
                
            doc.close()
            return image_paths
        except Exception as e:
            print(f"❌ Error leyendo PDF {file_path.name}: {e}")
            return []
    
    else:
        print(f"❌ Formato no soportado: {suffix}")
        return []

def run_family_batch(family_name):
    """
    EJECUTOR DE LOTES (BATCH RUNNER):
    1. Busca pares (PDF + TXT) en la carpeta.
    2. FILTRA solo los que coincidan con el nombre de la familia.
    3. Ejecuta el entrenamiento.
    """
    print(f"\n{'='*60}")
    print(f"🚀 INICIANDO ENTRENAMIENTO DE FAMILIA: {family_name.upper()}")
    print(f"{'='*60}")

    # --- 1. IDENTIFICACIÓN DE ACTIVOS ---
    all_files = list(DOCS_DIR.glob(f"expected_*.txt"))
    
    batch_queue = []
    
    print(f"📂 Escaneando directorio en busca de casos para '{family_name}'...")
    
    for truth_file in all_files:
        # Extraer ID: expected_7501_01.txt -> 7501_01
        case_id = truth_file.stem.replace("expected_", "")
        
        # --- 🛑 FILTRO DE SEGURIDAD (NUEVO) ---
        # Solo procesamos si el ID del caso contiene el nombre de la familia
        if family_name not in case_id:
            continue 
            
        # Buscar el documento visual correspondiente
        doc_candidates = list(DOCS_DIR.glob(f"{case_id}.*"))
        doc_path = next((c for c in doc_candidates if c.suffix.lower() in [".pdf", ".jpg", ".png"]), None)
        
        if doc_path:
            batch_queue.append({
                "case_id": case_id,
                "doc_path": doc_path,
                "truth_path": truth_file
            })
    
    if not batch_queue:
        print(f"❌ No se encontraron casos que contengan '{family_name}' en el nombre.")
        print("   Asegúrate de que tus archivos se llamen tipo: '7501_archivo1.pdf' y 'expected_7501_archivo1.txt'")
        return None

    print(f"✅ Se encontraron {len(batch_queue)} casos válidos para el lote de '{family_name}'.")

    # --- 2. GESTIÓN DEL PROMPT MAESTRO ---
    prompt_path = PROMPTS_DIR / f"MASTER_{family_name}.txt"
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
        print("⚡ Prompt Maestro NO detectado. Generando SEMILLA con el primer caso...")
        seed_case = batch_queue[0]
        
        raw_truth = seed_case["truth_path"].read_text(encoding="utf-8")
        seed_conf = configurator_node({"raw_ground_truth": raw_truth, "case_id": seed_case["case_id"]})
        seed_expected = seed_conf.get('expected_data', {})
        
        if not seed_expected:
            print("❌ Error crítico: No se pudieron leer datos del caso semilla.")
            return

        seed_imgs = prepare_input_images(seed_case["doc_path"])
        original_prompt = auto_generate_prompt_from_image(seed_imgs[0], seed_expected)
        
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(original_prompt)
        print("      ✅ Prompt Maestro Semilla creado.")
        
        for img in seed_imgs:
            if os.path.exists(img): os.remove(img)

    # --- 3. PREPARACIÓN DE DATOS DEL LOTE ---
    print(f"\n⚙️ Pre-procesando imágenes y datos para {len(batch_queue)} casos...")
    final_batch_data = []
    
    for item in batch_queue:
        raw_truth = item["truth_path"].read_text(encoding="utf-8")
        conf_res = configurator_node({"raw_ground_truth": raw_truth, "case_id": item["case_id"]})
        expected_data = conf_res.get('expected_data', {})
        rules = conf_res.get('rules', {})
        expected_keys = list(expected_data.keys())
        
        imgs = prepare_input_images(item["doc_path"], expected_keys=expected_keys)
        
        final_batch_data.append({
            "case_id": item["case_id"],
            "images": imgs,
            "raw_truth": raw_truth,
            "expected_data": expected_data,
            "rules": rules
        })

    # --- 4. INICIALIZACIÓN DEL ESTADO ---
    initial_state = {
        "family": family_name,
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

    # --- 5. EJECUCIÓN DEL FLUJO ---
    print(f"\n🔥 EJECUTANDO GRAFO DE OPTIMIZACIÓN...")
    try:
        final_output = app.invoke(initial_state)
        print(f"\n🏁 ENTRENAMIENTO FINALIZADO.")
        if final_output:
            print(f"      🏆 Score Promedio Final: {final_output.get('best_avg_score', 0):.1f}%")
    except Exception as e:
        print(f"❌ Error fatal durante la ejecución: {e}")
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
    # Define un nombre para tu familia (esto creará "MASTER_7883arg.txt")
    NOMBRE_FAMILIA = "7883arg" 
    
    print(f"🔧 Modo Consola: Iniciando batch para '{NOMBRE_FAMILIA}'...")
    
    # Ejecutamos la función maestra
    run_family_batch(NOMBRE_FAMILIA)