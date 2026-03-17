# ==============================================================================
# 🧠 EL CEREBRO: AZURE OPENAI (GPT-4o)
# Uso: Planificación, Auditoría, Visión "Detective", Optimización Lógica.
# ==============================================================================
AZURE_ENDPOINT = ""
AZURE_API_KEY = ""
# IMPORTANTE: Este es el nombre del despliegue en Azure AI Studio, no el nombre del modelo base.
AZURE_DEPLOYMENT_NAME = ""
AZURE_API_VERSION = ""

# ==============================================================================
# 💪 EL MÚSCULO: FIREWORKS AI (Llama 4 Maverick)
# Uso: Extracción Masiva, Simulación de Entorno de Producción.
# ==============================================================================
# Nota: He movido aquí tu key actual de nodes.py
FIREWORKS_API_KEY = "" 
FIREWORKS_MODEL_ID = ""

def validate_config():
    """Verifica que las credenciales críticas existan antes de arrancar."""
    missing = []
    if "TU-RECURSO" in AZURE_ENDPOINT: missing.append("AZURE_ENDPOINT (Falta configurar)")
    if "PEGAR_TU_CLAVE" in AZURE_API_KEY: missing.append("AZURE_API_KEY (Falta configurar)")
    if not FIREWORKS_API_KEY: missing.append("FIREWORKS_API_KEY")
    
    if missing:
        print("\n" + "!"*60)
        print("❌ ERROR DE CONFIGURACIÓN CRÍTICO")
        print("Faltan las siguientes credenciales en config.py o .env:")
        for m in missing:
            print(f"   - {m}")
        print("!"*60 + "\n")
        return False
    return True