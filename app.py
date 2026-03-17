from langgraph.graph import StateGraph, END
from state import AgentState
# 1. Importamos el nuevo nodo
from nodes import extraction_node, validation_node, optimizer_node, research_node, input_refinery_node

workflow = StateGraph(AgentState)

# 2. Definir Nodos
workflow.add_node("refinar", input_refinery_node) # <--- NUEVO PORTERO
workflow.add_node("investigar", research_node)
workflow.add_node("extraer", extraction_node)
workflow.add_node("validar", validation_node)
workflow.add_node("optimizar", optimizer_node)

# 3. Definir el Flujo (RE-CABLEADO)
# El sistema ahora entra por la Refinería
workflow.set_entry_point("refinar")

# La Refinería pasa al Investigador (que agrega contexto web si hace falta)
workflow.add_edge("refinar", "investigar")

# El Investigador pasa a la Extracción (como antes)
workflow.add_edge("investigar", "extraer")

# El resto del ciclo de optimización se mantiene igual
workflow.add_edge("extraer", "validar")

def decide_next(state):
    if state["is_final"] or state["attempts"] >= 5: 
        return "fin"
    return "reintentar"

workflow.add_conditional_edges(
    "validar",
    decide_next,
    {"reintentar": "optimizar", "fin": END}
)

# El optimizador vuelve a extraer (Bucle cerrado)
# IMPORTANTE: No vuelve a 'refinar' ni a 'investigar', ahorrando tokens.
workflow.add_edge("optimizar", "extraer")

app = workflow.compile()