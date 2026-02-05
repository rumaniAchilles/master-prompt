from langgraph.graph import StateGraph, END
from state import AgentState
# Importamos los nodos. Nota: Ya no necesitamos configurator_node dentro del grafo
from nodes import extraction_node, validation_node, optimizer_node

# Definimos el flujo
workflow = StateGraph(AgentState)

# 1. Definir Nodos
# Eliminamos "configurar" porque main.py ya hace la pre-configuración del lote
workflow.add_node("extraer", extraction_node)
workflow.add_node("validar", validation_node)
workflow.add_node("optimizar", optimizer_node)

# 2. Definir el Flujo (CAMBIO CLAVE)
# En Batch Mode, los datos ya entran limpios. Empezamos directo extrayendo.
workflow.set_entry_point("extraer")

# Flujo normal...
workflow.add_edge("extraer", "validar")

def decide_next(state):
    # Si ya terminamos (is_final) o pasamos los intentos máximos, paramos.
    if state["is_final"] or state["attempts"] >= 5: 
        return "fin"
    return "reintentar"

workflow.add_conditional_edges(
    "validar",
    decide_next,
    {"reintentar": "optimizar", "fin": END}
)

# Si optimizamos, volvemos a extraer para probar la nueva táctica
workflow.add_edge("optimizar", "extraer")

app = workflow.compile()