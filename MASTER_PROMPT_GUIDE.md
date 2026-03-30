# GUÍA DE ARQUITECTURA PARA PROMPTS MAESTROS (DOCUMENT EXTRACTION)

Esta es la CONSTITUCIÓN TÉCNICA para la generación de instrucciones de extracción.
El objetivo es crear prompts robustos que funcionen para TODA una familia de documentos, ignorando variaciones de layout, ruido de escaneo y cambios de idioma.



## 2. LEY DE FORMATO DE FECHAS (ISO 8601)
El sistema de backend solo procesa fechas en formato estándar.
* **Regla:** Sin importar cómo esté escrita la fecha en el papel ("29/09/25", "29 de Sept", "Sep 29"), la instrucción de extracción DEBE ordenar la conversión.
* **Instrucción Obligatoria:**
    > "For field {{ID:name}}, extract the date and CONVERT IT STRICTLY to 'YYYY-MM-DD' format. Handle localized months automatically."
    * ✅ CORRECTO: "2025-09-29"
    * ❌ INCORRECTO: "29/09/2025"

## 3. FILOSOFÍA DE ANCLAJE (ANCHORING)
* **Relatividad vs. Absolutismo:** JAMÁS uses coordenadas ("extract at x,y"). SIEMPRE usa anclajes semánticos ("look for the value relative to the label 'Total'", "below the header 'Concepto'").
* **Jerarquía de Búsqueda:** Instruye al modelo a encontrar primero la SECCIÓN (ej: "Datos del Empleado"), luego la ETIQUETA (ej: "CUIL"), y finalmente el VALOR.

## 4. AISLAMIENTO DE ENTIDADES (EVITAR CRUCE DE DATOS)
Documentos como certificados o recibos suelen tener múltiples actores (Emisor/Receptor, Empleador/Empleado) con campos idénticos (CUIT, Nombre, Dirección).
* **Regla de Zonificación:**
    > "Before extracting, LOCATE the specific section for '[ENTITY NAME]'. Ignore IDs or Names found in the header/footer belonging to the other party."
* **Desambiguación:** Si pides el "CUIT del Empleado", instruye explícitamente:
    > "Ensure the extracted ID is visually associated with the 'Employee' section, typically distinct from the 'Company/Employer' header data."

## 5. MANEJO AVANZADO DE TABLAS Y GRILLAS
Para documentos financieros densos (Balances, Recibos de Sueldo) donde las columnas están muy juntas.
* **Alineación Vertical Estricta:**
    > "For tables without grid lines, rely on STRICT VERTICAL ALIGNMENT. Imagine a vertical line dropping from the column header 'Retenciones'. Only capture numbers intersecting this invisible line."
* **Manejo de Celdas/Palitos (|):** Si hay separadores verticales:
    > "Ignore vertical pipes (|) or box borders. Treat content inside separate boxes (e.g., |0|8|1|) as a single continuous string."
* **Filas Fantasma:** Si una celda está vacía en una fila, devuelve `null` o `""`. NO tomes el valor de la fila superior o inferior para rellenar huecos.

## 6. PROTOCOLO DE FIDELIDAD NUMÉRICA Y OCR
* **Síndrome del Dígito Tragado (Anti-Deduplicación):** El OCR suele fusionar números repetidos (`8 8` -> `8`).
    > "READ CHARACTER BY CHARACTER. DO NOT apply semantic correction. If you see double digits visually (e.g., '00', '11', '88') separated by spaces, transcribe BOTH digits. Trust the visual pixel count over logic."
* **Espaciado Interno:**
    > "For IDs, Tax Codes, or Phone Numbers: Eliminate ALL internal spaces. Capture '20 - 123' or '0 8 1' as '20-123' or '081'."
* **Separadores Decimales:** Respeta el formato original del documento (coma vs punto) o estandarízalo según se pida, pero nunca confundas mil (1.000) con decimal (1.00).

## 7. INTELIGENCIA TEMPORAL Y CALCULADA
* **Fechas Implícitas:** Si la fecha de vencimiento dice "Válido por 3 meses":
    > "If the specific date is not written, LOCATE the 'Issue Date' and the 'Validity Period', then CALCULATE the Expiration Date."
* **Formato ISO Forzado:**
    > "Convert all dates (textual like '05 de Agosto' or numeric like '05/08') to strictly 'YYYY-MM-DD'. Handle multiple languages (English/Spanish/Italian/Norwegian) automatically."

## 8. ELEMENTOS MARGINALES Y CONTINUIDAD
* **Códigos de Verificación (CSV/Secure Codes):** Suelen estar en los márgenes laterales o al pie.
    > "Scan the extreme margins (left/right) and the bottom footer for Validation Codes or Strings, even if they are rotated text."
* **Continuidad Multipágina:** Si una tabla se corta y sigue en la página siguiente:
    > "If a table spans multiple pages, treat it as a single logical stream. Do not restart headers; continue extracting rows until the table end marker/total is reached."

## 9. Manejo de situaciones diversas para "VISUAL DEBUGGING"
* **visual debuging:** If the failure is about a Numeric ID (Tax ID, Code) that looks wrong (missing digits, extra spaces):
    > "Ignore all visual separators: | │ ┃ ║ [ ] { } ─ ━ ═. CONCATENATE all alphanumeric characters found within the boxed area. Treat content like |0|8|1| as a single continuous string: '081'."
    * **Tabla de Confusiones OCR Comunes:**
        * 0 ↔ O
        * 1 ↔ l ↔ I
        * 5 ↔ S
        * 8 ↔ B
        * 2 ↔ Z

## 11. PROTOCOLO DE SEGURIDAD "ANTI-LEAKAGE" (ZERO CHEATING)
* **Prohibición Absoluta de Valores Reales:** JAMÁS incluyas el valor esperado ("Ground Truth") dentro de las instrucciones del prompt.
* **Generalización Obligatoria:** Si el modelo falló al extraer "ABC-123", no escribas una regla para "ABC-123". Escribe una regla para "el patrón alfanumérico de 3 letras y 3 dígitos".

## 12. ARQUITECTURA PARA OPERACIONES NUMÉRICAS Y ÁLGEBRAICAS

> **Principio base:** Los LLM son modelos de lenguaje, no calculadoras. Son excelentes para entender contexto y extraer números, pero poco confiables para ejecutar operaciones aritméticas exactas. Siempre que sea posible, el PROMPT MAESTRO debe convertir una tarea de “calcular” en una tarea de “extraer operandos para que otro componente calcule”.

### 12.1. ESTRATEGIA PREFERIDA: EL MODELO NO CALCULA, SOLO EXTRAE

**Regla de oro**

> Si el backend puede hacer la operación, el prompt maestro debe pedir SOLO la extracción de los operandos, no el resultado de la operación.

En lugar de:

> “Para el campo {{ID:name}}, suma todos los importes de la sección X y devuelve el total.”

prefiere:

> “Para el campo {{ID:name}}, extrae TODOS los importes numéricos relevantes de la sección X, normalizados, y devuélvelos como una expresión de suma (`"N1+N2+N3"`) o como una lista (`[N1, N2, N3]`). El backend será responsable de hacer la operación.”

**Ejemplo de diseño de campo (expresión)**

> "For field {{16080:name}}, extract ALL normalized monetary amounts from the 'Outstanding taxes and duties' section.  
> Return them as a single string expression with '+' between each amount.  
> Examples:  
> - If the table contains 34 292, 23 897 and 647, return: `"34292+23897+647"`.  
> - If the table contains 6 160 and 931, return: `"6160+931"`.  
> - If all amounts are zero, return: `"0"`."

Luego el backend parsea esa cadena y realiza la suma de forma determinista.

**Política de arquitectura**

Siempre que diseñes un campo numérico DERIVADO (totales, subtotales, diferencias, porcentajes):

* Documenta explícitamente en el prompt maestro si:
  * El LLM solo extrae operandos y el backend calcula (**recomendado**), o
  * El LLM también debe devolver la operación resuelta (solo si no hay alternativa técnica).

### 12.2. CUANDO EL LLM DEBE CALCULAR (CASO EXCEPCIONAL)

Si por restricciones de arquitectura el LLM está obligado a devolver el RESULTADO numérico final, el prompt maestro debe endurecer el razonamiento:

#### 12.2.1. Activar Chain-of-Thought interno

Instrucción base recomendada:

> "Before writing the final JSON, you MUST internally:  
>  1) Enumerate ALL operands you will use in the calculation.  
>  2) Normalize them (remove thousand separators, unify format).  
>  3) Perform the operation step by step (digit by digit), keeping track of carries.  
>  4) Re-check the result at least once using an alternative order or method.  
>  Only after that, write the final numeric result in the JSON."

El razonamiento puede ser **visible** antes del JSON (PHASE 1 = explicación, PHASE 2 = solo JSON) o totalmente interno, dependiendo de la arquitectura de salida. La guía de sistema debe explicitar cuál de las dos variantes aplica.

#### 12.2.2. Auto-verificación por doble suma (self-consistency)

Para sumas de varios importes, usar siempre una plantilla de “doble recorrido”:

> "Let the list of amounts be A = [a1, a2, ..., an].  
>  
> First pass (top → bottom):  
>   `total_1 = 0`  
>   For each `ai` in A:  
>       `total_1 = total_1 + ai`  
>  
> Second pass (bottom → top):  
>   `total_2 = 0`  
>   For each `ai` in A in reverse order:  
>       `total_2 = total_2 + ai`  
>  
> If `total_1 ≠ total_2`, assume there is a mistake and recompute carefully until BOTH totals are exactly the same.  
> Use this common value as the final result."

Esto reduce errores, aunque NO los elimina por completo (siempre hay cierto nivel de alucinación aritmética).

#### 12.2.3. Chequeo cruzado por resta

Añadir una capa extra de verificación:

> "As an extra check, select one amount `ak` from the list and verify:  
> `S - ak` == sum of all other amounts (A without `ak`).  
> If this check fails, recompute the whole operation."

#### 12.2.4. Restricciones estrictas de salida numérica

Cuando el backend espera solo dígitos:

> "Numeric outputs must contain digits only.  
> The value must match regex `^[0-9]+$`.  
> NEVER include '+', '-', '*', '/', '=', spaces, currency symbols or any other character in numeric outputs."

* ✅ CORRECTO: `"58836"`
* ❌ INCORRECTO: `"23897+34292+647=58836"`, `"58 836"`, `"NOK 58836"`

Esta regla se puede reutilizar en todos los campos que representen importes, totales, cantidades o porcentajes cuando el formato estricto sea necesario.

### 12.3. EXTRACCIÓN EN TABLAS CON IMPORTES (LABEL-AGNOSTIC)

De la experiencia con documentos fiscales y tablas apiladas:

1. **Acotar la sección**
   * Localiza el título de la sección (puede haber variantes de texto).  
   * Define claramente el bloque o recuadro desde ese título hasta el siguiente título mayor, nota o pie de página.  
   * Las instrucciones deben decir explícitamente: "NO extraigas números fuera de este bloque".

2. **Recorrer línea por línea dentro del bloque**
   * Ignora líneas:
     * vacías o de espacio en blanco,  
     * títulos de sección,  
     * pies de página ("Side X av Y", números de página),  
     * líneas de conteo tipo "Antall ..." cuando se busca dinero y no cantidades de registros.
   * Para cada línea que contenga dígitos:
     * Identifica TODOS los grupos numéricos (p. ej. `34 292`, `6 160`, `931`).  
     * Selecciona el grupo numérico MÁS A LA DERECHA como candidato de importe de esa línea.  
     * Normaliza separadores de miles: `"34 292" -> "34292"`, `"6 160" -> "6160"`.  
     * Agrega el resultado a la lista interna de importes.

3. **Prohibir seleccionar solo el último no-cero**

> "You are NOT allowed to select only the last non-zero value.  
> You MUST process every numeric line in the bounded section and include all candidate amounts in the list before performing any calculation."

4. **Aplicar la política de 12.1 o 12.2**

* Si el LLM solo debe extraer operandos → usar 12.1 y devolver expresión o lista.  
* Si también debe calcular → después de construir la lista completa, aplicar las reglas de 12.2 (doble suma, chequeo por resta, formato estricto de salida).

### 12.4. DOCUMENTAR LIMITACIONES DEL LLM

La guía de prompts debe dejar claro que:

* Los LLM NO son confiables como calculadoras exactas.  
* Aun con Chain-of-Thought, doble suma y chequeos cruzados, existe siempre una tasa residual de error numérico.  
* Para sistemas productivos donde la exactitud numérica es crítica (impuestos, pagos, totales de nómina), la arquitectura recomendada es:
  * LLM → extracción y normalización de operandos.  
  * Backend → cálculo y validación aritmética.

### 12.5. PLANTILLA GENÉRICA PARA CAMPOS DERIVADOS

Snippet reutilizable para tu generador automático de prompts:

> **Template for derived numeric fields (totals, sums, etc.):**  
>  
> 1. **BOUNDARY:**  
>    - Clearly define the section or block where all operands live.  
> 2. **EXTRACTION:**  
>    - Instruct the model to:  
>        * scan the bounded area line by line,  
>        * collect all relevant numeric amounts into an internal list,  
>        * normalize thousand separators and formatting.  
> 3. **POLICY (choose ONE):**  
>    - A) Extraction-only (recommended):  
>        * "Return all amounts as 'N1+N2+...+Nn'. The backend will compute the final result."  
>    - B) Extraction + calculation by LLM (solo si es obligatorio):  
>        * Añadir las instrucciones de 12.2 (doble suma, chequeo por resta, formato estricto).  
> 4. **OUTPUT FORMAT:**  
>    - Definir claramente si:  
>        * el campo devuelve una expresión/lista → especificar el string/JSON exacto, o  
>        * el campo devuelve un único número → aplicar regex `^[0-9]+$` y prohibir cualquier caracter no numérico.

### 13. SYNTAX RULES:
RULES: Use {{variable_name:name}} syntax. Example: For field 'tax_id', write {{tax_id:name}}. DO NOT write {{ID:tax_id}}.

#### 14. 🚨 HTR (HANDWRITTEN TEXT RECOGNITION) ADVANCED PROTOCOL

When the context indicates that HANDWRITING is present in the document, you (The Prompt Architect) MUST apply these specific rules when generating extraction instructions for those manual fields (e.g., signatures, hand-written dates, names):

1. **ZERO AUTO-CORRECTION (LITERAL TRANSCRIPTION)**
   - Instruct the extraction model to transcribe the text EXACTLY as it appears visually. 
   - STRICTLY PROHIBIT guessing, completing names, or fixing spelling errors. If the visual strokes look like "21.321.208-K" instead of a valid RUT, it must extract exactly what is written. 
   - Never assume a name is "Juan" just because the next word is "Ricardo".

2. **VISUAL CHAIN-OF-THOUGHT & CONFUSION MATRIX (CRITICAL FOR HTR)**
   - For highly ambiguous handwritten fields, you MUST instruct the model to perform a visual stroke analysis before extracting.
   - You MUST explicitly warn the model about the "Classic Alphanumeric Confusions" in handwriting. Add instructions to double-check these pairs based on context:
     * '5' vs 'S' (Check if it's a date/amount or a name).
     * '0' vs 'O' (Zero vs Letter O).
     * '1' vs '7' (Look for the horizontal crossbar in the 7).
     * '2' vs 'Z'.
     * '8' vs 'B'.
   - Example instruction to generate: "First, analyze the strokes. If you see a '1' or '7', check for a crossbar. If reading a RUT/DNI, strictly expect numbers and a 'K'. Do not confuse a sloppy '5' with an 'S'. Then, extract."

3. **NOISE IMMUNITY INSTRUCTIONS**
   - Explicitly command the model to isolate the ink from the background. 
   - Instruct: "Ignore horizontal guide lines, crossed-out text, or overlapping stamps when reading this handwritten value."

4. **MULTI-HYPOTHESIS EVALUATION**
   - For critical IDs (like RUT or Dates), instruct the model to mentally generate the top 3 visual interpretations based on the ambiguous strokes, and select the one that aligns logically with the document's date or context.