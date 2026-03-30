from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from typing import List, Optional
import json
import shutil
import tempfile
import os

# Importamos nuestro Worker
from worker import process_optimization_task
# Importamos la base de datos para el tracking de estados
from database import AgentMemory

app = FastAPI(
    title="Prompt Builder Service API",
    description="Motor de Orquestación y Optimización Continua de Prompts para Document Analyzer.",
    version="2.0.0"
)

# Instanciamos la conexión a la base de datos
db = AgentMemory()

@app.post("/api/v1/optimize")
async def trigger_optimization(
    background_tasks: BackgroundTasks,
    family_id: str = Form(..., description="ID único local de la familia de documentos (ej. tgr_v1)"),
    id_document_type: str = Form(..., description="ID del tipo de documento en la base de datos principal"),
    id_user: str = Form(..., description="ID del usuario que solicita la prueba"),
    company_id: str = Form(..., description="ID de la compañía en la base de datos principal"), # <--- NUEVO
    ground_truth: str = Form(..., description="JSON string con los datos esperados"),
    original_prompt: Optional[str] = Form(None, description="Prompt base opcional con {{placeholders}}"),
    
    # Mantenemos esto para que Swagger muestre el botón de subida
    documento: UploadFile = File(..., description="Un PDF o JPG para el lote de prueba")
):
    """
    Endpoint principal modificado para recibir company_id y registrar tracking de estados.
    """
    # 1. VALIDACIÓN DEL JSON
    try:
        gt_data = json.loads(ground_truth)
        if not isinstance(gt_data, dict):
            raise ValueError("El ground_truth debe ser un diccionario JSON válido.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en el formato del Ground Truth: {str(e)}")

    # 2. MANEJO DEL ARCHIVO ÚNICO
    temp_dir = tempfile.mkdtemp(prefix=f"prompt_builder_{family_id}_")
    saved_files = [] 

    try:
        file_path = os.path.join(temp_dir, documento.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(documento.file, buffer)
        saved_files.append(file_path)
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Error guardando archivo: {str(e)}")

    # 3. REGISTRAR INICIO EN LA BASE DE DATOS
    db.create_or_update_job(family=family_id, status="in_progress", score=0.0)

    # 4. ENCOLADO DEL TRABAJO
    background_tasks.add_task(
         process_optimization_task, 
         family_id=family_id,
         id_document_type=id_document_type,
         id_user=id_user,
         company_id=company_id, # <--- SE LO PASAMOS AL WORKER
         gt_data=gt_data, 
         original_prompt=original_prompt, 
         file_paths=saved_files,
         temp_dir=temp_dir 
    )

    # 5. RESPUESTA INMEDIATA
    return {
        "status": "accepted",
        "message": "Archivo recibido correctamente. La optimización ha comenzado en segundo plano.",
        "metadata": {
            "family_id": family_id,
            "document_received": documento.filename
        }
    }

@app.get("/api/v1/optimize/status/{family_id}")
async def get_optimization_status(family_id: str):
    """
    Permite al Frontend consultar en qué estado se encuentra la optimización y qué score lleva.
    """
    status_data = db.get_job_status(family_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="No se encontró un trabajo activo para esta familia.")
    
    return status_data

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Prompt Builder Service"}