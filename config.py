# ==============================================================================
# 🧠 EL CEREBRO: AZURE OPENAI (GPT-4o)
# Uso: Planificación, Auditoría, Visión "Detective", Optimización Lógica.
# ==============================================================================
AZURE_ENDPOINT = "https://checkformsopenai.openai.azure.com/"
AZURE_API_KEY = "8bdc1d4d7d8e4751b02b3200ea7a3714"
# IMPORTANTE: Este es el nombre del despliegue en Azure AI Studio, no el nombre del modelo base.
AZURE_DEPLOYMENT_NAME = "gpt-4.1"
AZURE_API_VERSION = "2024-12-01-preview"

# ==============================================================================
# 💪 EL MÚSCULO: FIREWORKS AI (Llama 4 Maverick)
# Uso: Extracción Masiva, Simulación de Entorno de Producción.
# ==============================================================================

def validate_config():
    """Verifica que las credenciales críticas existan antes de arrancar."""
    missing = []
    if "TU-RECURSO" in AZURE_ENDPOINT: missing.append("AZURE_ENDPOINT (Falta configurar)")
    if "PEGAR_TU_CLAVE" in AZURE_API_KEY: missing.append("AZURE_API_KEY (Falta configurar)")    
    
    if missing:
        print("\n" + "!"*60)
        print("❌ ERROR DE CONFIGURACIÓN CRÍTICO")
        print("Faltan las siguientes credenciales en config.py o .env:")
        for m in missing:
            print(f"   - {m}")
        print("!"*60 + "\n")
        return False
    return True