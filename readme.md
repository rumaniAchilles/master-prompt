🧠 Prompt Builder Service (Auto-Orquestador)
Versión: 2.0.0
Descripción: Motor de orquestación asíncrono y optimización continua de prompts para el ecosistema document-analyzer.

Este microservicio utiliza LangGraph y Azure OpenAI (GPT-4o) para automatizar la ingeniería de prompts. Analiza documentos, genera tácticas de extracción utilizando anclajes visuales, prueba iterativamente las instrucciones contra el motor principal y consolida un Prompt Group optimizado listo para producción.

🏗️ Arquitectura y Flujo de Trabajo
El servicio opera de manera asíncrona (Fire and Forget) para soportar alto tráfico. El flujo se divide en tres fases principales:

1. Ingesta y Setup (api.py & worker.py)
La API recibe los documentos, el JSON esperado (Ground Truth) y los identificadores requeridos (family_id, id_document_type, id_user, company_id).

Se registra el inicio del trabajo en una base de datos local SQLite para trazabilidad.

El Worker en segundo plano convierte los PDFs a imágenes temporales y prepara el estado inicial para el orquestador.

2. El Grafo de Optimización (LangGraph)
El ciclo iterativo de LangGraph transita por los siguientes nodos inteligentes:

Refinería & Lógica (input_refinery_node): Limpia y estructura el prompt base si es proporcionado.

Investigador (research_node): Realiza un análisis forense visual, detecta si hay texto manuscrito (HTR) y define la estrategia de layout (fijo vs. dinámico).

Configurador (configurator_node): Convierte el Ground Truth en una matriz de validación estricta (parameters), asignando operadores lógicos (ej. containment, onlyAlphanumericEquals).

Extractor / Tester (test_analyzer_node): Cliente HTTP que ensambla el payload con {{placeholders}} y lo envía al document-analyzer para ser evaluado.

Validador (validation_node): Compara los resultados del motor contra la matriz de configuración, calcula el score y empaqueta los errores detallados.

Optimizador (optimizer_node): (Solo si hay errores). Ajusta las instrucciones de búsqueda heurística basándose en el feedback, sin generar schemas JSON manuales y respetando estrictamente la sintaxis {{key:name}}.

3. El Handoff Oficial
Una vez que el prompt alcanza un 100% de éxito (o se agotan los intentos), el Worker empaqueta el prompt final y la configuración de comparadores (comparison_config) y ejecuta un POST /api/v1/prompts/groups para guardar el grupo definitivamente en el document-analyzer.

🚀 Requisitos e Instalación
Variables de Entorno
Crea un archivo .env en la raíz del proyecto o configura las siguientes variables en tu sistema:

Fragmento de código
# Claves de la IA (El Cerebro)
AZURE_ENDPOINT="https://tu-recurso.openai.azure.com/"
AZURE_API_KEY="tu-clave"
AZURE_API_VERSION="2024-12-01-preview"
AZURE_DEPLOYMENT_NAME="gpt-4.1"

# Conexión al document-analyzer (El Músculo)
ANALYZER_BASE_URL="http://localhost:8000"
ANALYZER_API_TOKEN="tu-token-de-autorizacion"

# Entorno de Pruebas
MOCK_MODE="True" # Cambiar a "False" para conectar con el servicio real
DATABASE_URL="sqlite:///./agent_memory.db"
Levantar el Servicio
Bash
# Instalar dependencias
pip install fastapi uvicorn requests langgraph pydantic openai sqlalchemy pymupdf duckduckgo-search

# Iniciar el servidor
uvicorn api:app --host 0.0.0.0 --port 8001 --reload
🕹️ Cómo Usar el Servicio
1. Iniciar una Optimización
Puedes probar el servicio accediendo a Swagger UI en http://localhost:8001/docs e interactuando con el endpoint POST /api/v1/optimize.

Ejemplo de Payload:

family_id: cert_seguro_v1

id_document_type: bc2b9b8b...

id_user: usr-prompt-builder

company_id: comp-achilles-001

ground_truth:

JSON
{
  "dni": {"value": "46065929B"},
  "fecha_emision": {"value": "2025-01-15"}
}
original_prompt: (Dejar en blanco para que el Detective auto-genere el borrador 1).

documento: Seleccionar un PDF o Imagen de muestra.

2. Monitorear el Estado
Como el proceso es asíncrono, puedes consultar el estado en tiempo real (ideal para barras de progreso en el Frontend) usando:

GET /api/v1/optimize/status/{family_id}

Respuesta esperada:

JSON
{
  "family_id": "cert_seguro_v1",
  "status": "completed", // "in_progress", "completed", "failed"
  "score": 100.0,
  "last_update": "2026-03-31T10:00:00Z"
}
📦 Qué Esperar (El Entregable Final)
Al finalizar exitosamente, el servicio realiza dos acciones:

Guardado Remoto: Envía el payload al sistema principal mediante HTTP (save_prompt_group).

Respaldo Local: Guarda una copia física del JSON en la carpeta /prompt_groups_output/GROUP_{family_id}.json para auditoría.

El Prompt Group generado contendrá un contexto maestro enriquecido, tácticas de extracción blindadas contra variaciones visuales (incluyendo protocolos HTR si es necesario) y una matriz comparison_config limpia (sin name ni value) lista para ser inyectada dinámicamente en producción.

🔭 Próximos Pasos (Roadmap de Escalabilidad)
Aunque el servicio actual es robusto, la arquitectura permite las siguientes evoluciones orgánicas:

Prompting Secuencial Inteligente: Modificar el ensamblador para que divida el prompt en un List[str], permitiendo que el LLM del motor principal (ej. Gravity) realice un razonamiento de contexto en el paso 1, y una extracción estricta en el paso 2, reduciendo la carga cognitiva.

Ampliación del Arsenal de Operadores:
Actualizar el System Prompt del configurator_node para enseñarle a GPT-4o a inferir de forma autónoma reglas matemáticas avanzadas (ej. resolve_arithmetic, operadores de fechas v3 y linked_keys condicionales).

Selección Dinámica de Modelos:
Añadir el campo llm_model a la request inicial (api.py) para permitir que el usuario decida si el grupo se optimizará para "gravity", "mercurio", o "mercurio2_5".