from langgraph.graph import StateGraph, END
from state import AgentState
# 1. Agregamos el configurator_node a la importación
from nodes import test_analyzer_node, validation_node, optimizer_node, research_node, input_refinery_node, configurator_node

workflow = StateGraph(AgentState)

# 2. Definir Nodos
workflow.add_node("refinar", input_refinery_node)
workflow.add_node("investigar", research_node)
workflow.add_node("configurar", configurator_node) # <--- AÑADIMOS EL NODO
workflow.add_node("extraer", test_analyzer_node)
workflow.add_node("validar", validation_node)
workflow.add_node("optimizar", optimizer_node)

# 3. Definir el Flujo (RE-CABLEADO)
workflow.set_entry_point("refinar")

workflow.add_edge("refinar", "investigar")

# Del investigador, pasa al configurador para armar los parámetros
workflow.add_edge("investigar", "configurar")

# Del configurador, ahora sí pasa a la prueba HTTP
workflow.add_edge("configurar", "extraer")

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

# El optimizador vuelve directo a probar
workflow.add_edge("optimizar", "extraer")

app = workflow.compile()