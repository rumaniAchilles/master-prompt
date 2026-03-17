# 🏛️ Achilles | Master Prompt Engine

**Achilles** es un motor avanzado de Ingeniería de Prompts automatizada (Data-Driven Prompt Optimization) diseñado específicamente para la extracción de datos en documentos oficiales complejos, formularios y archivos con texto manuscrito (HTR).

En lugar de requerir que un humano escriba y pruebe prompts iterativamente, Achilles utiliza un **Sistema Híbrido de IA (Brain + Muscle)** orquestado mediante grafos (`LangGraph`) para evaluar, detectar fallos y reescribir sus propias instrucciones hasta alcanzar la máxima precisión de extracción posible.

---

## ✨ Características Principales

* 🧠 **Arquitectura Híbrida (Azure + Fireworks):** Utiliza GPT-4o ("The Brain") para el razonamiento, detección visual y redacción de estrategias, y Llama 4 Maverick ("The Muscle") para simular la extracción masiva de datos en producción.
* 🔄 **Bucle de Auto-Optimización (LangGraph):** El sistema extrae, valida contra una verdad fundamental (Ground Truth), analiza los errores y optimiza el prompt en un ciclo iterativo hasta alcanzar un umbral de éxito (ej. 98%) o un límite de intentos.
* ✍️ **Detección Automática de Manuscritos (HTR Protocol):** El nodo de investigación detecta si el documento contiene tinta manuscrita o firmas, activando excepciones en el prompt final para prohibir la auto-corrección ortográfica y habilitar el razonamiento visual profundo.
* 🛡️ **Zero Data Loss Protocol:** La Refinería y el Optimizador están programados para limpiar y estructurar el prompt *sin borrar jamás* las reglas de negocio específicas, condicionales o casos límite (edge cases) del usuario.
* 🔍 **Búsqueda Semántica Dual (Smart Paging):** Escanea PDFs largos buscando coincidencias de "Llaves" y "Valores" para extraer solo las páginas relevantes y enviarlas a la IA, ahorrando tokens y previniendo alucinaciones.

---

## ⚙️ Arquitectura del Sistema (El Grafo)

Achilles funciona como un flujo de estados secuenciales e iterativos definido en `app.py`.

1.  **Refinería (`input_refinery_node`):** Recibe un prompt inicial (si existe) y lo compila. Limpia la estructura pero blinda las reglas de negocio en un formato de pseudocódigo accionable.
2.  **Investigador (`research_node`):** GPT-4o analiza visualmente una muestra de los documentos. Identifica anclajes universales, detecta la presencia de manuscritos (`has_handwriting`) y busca contexto legal en la web mediante DuckDuckGo.
3.  **Extracción (`extraction_node`):** Llama 4 toma el prompt actual y las imágenes, y extrae los datos devolviendo un esquema JSON estricto (`valor`, `confianza`, `Estado`).
4.  **Validación (`validation_node`):** Un motor lógico puro compara el JSON extraído con el Ground Truth usando reglas de negocio (coincidencia exacta, difusa, o parseo inteligente multilingüe de fechas).
5.  **Optimización (`optimizer_node`):** "El Arquitecto". Si la extracción falla, GPT-4o analiza los errores (mismatches) y reescribe la táctica de extracción solucionando el problema, pero preservando el ADN del negocio.
6.  *Fallback:* Si no hay prompt inicial, el **Detective** (`detective.py`) realiza un "Arranque en Frío" haciendo ingeniería inversa para crear un prompt desde cero basándose en la imagen y los datos esperados.
7.  **Agente de Sintaxis (`syntax_enforcer_agent`):** El "Policía". Una vez finalizado el entrenamiento, compila el Prompt de Producción final, eliminando burocracia, traduciendo instrucciones al inglés (manteniendo variables en español) y forzando un único esquema JSON de ejemplo.

---

## 🚀 Requisitos e Instalación

1. **Dependencias de Python:**
   Asegúrate de tener instalado Python 3.9+ e instala los requerimientos:
   ```bash
   pip install -r requirements.txt
Configuración de Entorno (.env o config.py):
El sistema requiere las credenciales de los modelos híbridos. Configura las siguientes variables:

AZURE_ENDPOINT, AZURE_API_KEY, AZURE_API_VERSION, AZURE_DEPLOYMENT_NAME (Para GPT-4o / The Brain)

FIREWORKS_API_KEY, FIREWORKS_MODEL_ID (Para Llama 4 / The Muscle)

🛠️ Uso Básico (Modo Interfaz Gráfica)
Achilles incluye una interfaz de usuario construida con CustomTkinter (gui.py) diseñada para un flujo de trabajo ágil.

Ejecutar la Interfaz:

Bash
python gui.py
Identidad: Define un ID de Familia (ej. tgr_certificados_v1). Todos los documentos y prompts generados se asociarán a este ID.

Cargar Documento: Sube un PDF o JPG representativo del lote.

Cargar Datos Esperados: Sube un archivo .txt o .json con la "Verdad Fundamental" (Ground Truth) que esperas que el modelo extraiga.

Formato aceptado: JSON plano o texto con estructura ID: Valor.

Prompt Base (Opcional): Si tienes instrucciones previas o reglas de negocio crudas, súbelas en un archivo .txt.

Ejecutar: Haz clic en "Añadir al Lote" y luego en "Iniciar Optimización Maestra".

Resultado: Observa el registro de auditoría. Al finalizar, Achilles te preguntará si deseas guardar el Prompt Maestro generado en la carpeta prompt_textos/.

📂 Estructura del Proyecto
app.py: Definición del Grafo de LangGraph y las rutas condicionales.

nodes.py: Contiene la lógica profunda de cada nodo (Refinería, IA Forense, Llama, Arquitecto).

gui.py: Frontend interactivo y orquestador del paso final de Sintaxis.

main.py: Ejecutor de lotes, pre-procesamiento de PDFs a JPG (300 DPI) e inicializador del estado general.

detective.py: Agente especializado en "Arranque en Frío" mediante ingeniería inversa.

validators.py: Funciones matemáticas y de texto para comparar el dato extraído vs. el esperado (Fechas, Levenshtein, Normalización).

database.py: Memoria SQLite (AgentMemory) para evitar repetir errores pasados.

MASTER_PROMPT_GUIDE.md: La "Constitución" que guía al Arquitecto sobre cómo escribir buenos prompts, incluyendo el protocolo HTR para manuscritos.