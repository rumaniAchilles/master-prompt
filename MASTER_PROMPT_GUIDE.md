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

## 10. FORMATO DE SALIDA (JSON PURO)
* **Salida Limpia:** Devuelve SOLAMENTE el objeto JSON. Sin bloques de markdown (` ```json `), sin introducciones ("Here is the data...").
* **Null Safety:** Si un campo es ilegible o no existe, usa `null`. JAMÁS inventes ni alucines datos.

## 11. PROTOCOLO DE SEGURIDAD "ANTI-LEAKAGE" (ZERO CHEATING)
* **Prohibición Absoluta de Valores Reales:** JAMÁS incluyas el valor esperado ("Ground Truth") dentro de las instrucciones del prompt.
* **Generalización Obligatoria:** Si el modelo falló al extraer "ABC-123", no escribas una regla para "ABC-123". Escribe una regla para "el patrón alfanumérico de 3 letras y 3 dígitos".