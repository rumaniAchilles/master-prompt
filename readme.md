🛡️ Achilles | Batch Optimizer Commander
Achilles es una plataforma de Ingeniería de Prompts Autónoma diseñada para perfeccionar la extracción de datos de documentos complejos (PDFs, Imágenes). Utiliza una arquitectura de agentes cognitivos (basada en LangGraph) que iteran, validan y optimizan instrucciones automáticamente hasta alcanzar la máxima precisión.

🌟 Características Principales
🧠 Core de Inteligencia Artificial
Ciclo de Auto-Mejora (Hill Climbing): El sistema extrae, valida contra una "verdad" (Ground Truth) y, si falla, un agente "Arquitecto" reescribe el prompt basándose en el error específico.

Memoria Histórica Persistente: Utiliza SQLite (agent_memory.db) para recordar estrategias que fallaron en el pasado y evitar bucles infinitos.

Modo Detective (Cold Start): Si no existe un prompt base, el sistema analiza visualmente el documento y genera uno desde cero automáticamente.

Validación Robusto: Comparación inteligente de fechas (ISO 8601), coincidencia difusa (Fuzzy Matching) y normalización de textos.

🖥️ Interfaz de Usuario (GUI)
Gestión por Lotes (Batch): Procesa familias enteras de documentos para asegurar que el prompt funcione en todos los casos, no solo en uno.

Editor Integrado: Permite ver, editar y cargar "Datos Esperados" y "Prompts Base" directamente desde la app.

Seguridad de Sintaxis: Un agente finalizador ("Syntax Enforcer") asegura que el output tenga siempre el formato {{ID:name}} requerido por aplicaciones externas.

Limpieza de Sesión: Botón de pánico para purgar archivos temporales y reiniciar el entorno de trabajo.

🏗️ Arquitectura del Sistema
El flujo de trabajo sigue un grafo de estados (app.py):

Configurator Node: Analiza el archivo de texto de "Respuesta Esperada" (aunque sea una tabla copiada de Excel) y lo convierte a JSON estructurado.

Detective (Opcional): Si es una familia nueva, crea el primer prompt.

Extraction Node: El modelo (Llama 3/4 Vision) extrae los datos del documento usando la táctica actual.

Validation Node: Compara la extracción con lo esperado. Calcula el Score %.

Optimizer Node: Si el score es bajo, analiza los errores, consulta la Base de Datos de Fallos y genera una nueva táctica.

Syntax Enforcer: Al finalizar, limpia "basura" conversacional del LLM y formatea las variables.

🚀 Instalación y Configuración
1. Requisitos Previos
Python 3.10 o superior.

Una API Key de Fireworks AI.

(Recomendado) Entorno virtual (venv).

2. Instalación de Dependencias
Bash
pip install -r requirements.txt
Dependencias clave: langgraph, langchain, fireworks-ai, customtkinter, tkinterdnd2, pymupdf (fitz), python-dotenv.

3. Configuración de Entorno (.env)
Crea un archivo .env en la raíz con tu clave:

Fragmento de código
FIREWORKS_API_KEY=tu_api_key_aqui
# FIREWORKS_MODEL=accounts/achilles/deployedModels/llama4... (Opcional, hardcoded por seguridad)
📖 Guía de Uso
Paso 1: Iniciar la Aplicación
IMPORTANTE: Ejecuta siempre desde una terminal, fuera de carpetas sincronizadas por OneDrive para evitar bloqueos de archivos.

Bash
python gui.py
Paso 2: Cargar Datos
API Key & Familia: Ingresa tu clave (si no está en .env) y el ID de Familia (ej: 7546ita).

Nota: El ID de familia actúa como filtro. Solo procesará archivos que empiecen con ese nombre.

Cargar Documento: Arrastra o selecciona el PDF/Imagen del caso.

Cargar Datos Esperados: Sube el .txt o .json con los valores que el modelo debería encontrar.

Formato soportado: JSON puro o tablas de texto (Label Value).

Agregar al Lote: Presiona ⬇️ AGREGAR AL LOTE. Puedes repetir esto con varios documentos de la misma familia.

Paso 3: Ejecución
(Opcional) Carga un Prompt Base si ya tienes uno avanzado. Si no, déjalo vacío y el "Detective" creará uno.

Presiona ▶️ EJECUTAR OPTIMIZACIÓN.

Observa los logs en tiempo real. El sistema iterará hasta lograr 100% de precisión o agotar intentos.

Paso 4: Finalización
Si el resultado es satisfactorio, la app te preguntará si deseas Sobrescribir el Prompt Maestro.

El archivo final quedará guardado en la carpeta prompt_textos/MASTER_{familia}.txt, listo para producción con las etiquetas {{key}} correctas.

📂 Estructura del Proyecto
Plaintext
/
├── gui.py                 # Interfaz Gráfica (Controlador principal)
├── main.py                # Lógica de Batch y Procesamiento de Archivos
├── app.py                 # Definición del Grafo (LangGraph)
├── nodes.py               # Cerebro: Nodos de Extracción, Validación y Optimización
├── detective.py           # Generador de prompts iniciales (Vision Analysis)
├── validators.py          # Lógica matemática y difusa de comparación
├── database.py            # Gestión de Memoria (SQLite)
├── state.py               # Definición del Estado del Agente
├── MASTER_PROMPT_GUIDE.md # "Constitución" técnica para el LLM
├── agent_memory.db        # Base de datos local (auto-generada)
├── casos_docs/            # Carpeta temporal de documentos cargados
└── prompt_textos/         # Destino de los Prompts Maestros generados
🔧 Solución de Problemas Comunes
🔴 Error: [Errno 13] Permission denied o WinError 5
Causa: Windows o OneDrive tienen bloqueado el archivo .exe o la carpeta casos_docs.

Solución:

Mueve el proyecto a una carpeta local (ej: C:\Proyectos\Achilles) fuera de OneDrive.

Ejecuta con python gui.py en lugar de usar el ejecutable compilado.

Usa el botón "🗑️ NUEVA SESIÓN" en la GUI para forzar el desbloqueo de archivos.

🔴 Error: ZeroDivisionError
Causa: El archivo de "Datos Esperados" está vacío o ilegible, por lo que el validador intenta dividir aciertos sobre cero.

Solución: Verifica que tu .txt de expected tenga datos. El sistema ahora tiene protección contra esto, pero revisa tus inputs.

🔴 Error: "No se pudieron leer datos del caso semilla"
Causa: Estás probando una familia nueva sin prompt base y el formato del archivo expected es muy extraño.

Solución: Asegúrate de que tu archivo expected tenga una estructura clara (clave-valor o tabla con encabezados). El nodes.py actual incluye un "Arquitecto Robusto" para mitigar esto.