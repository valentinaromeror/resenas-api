from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId, errors as bson_errors
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(os.environ["MONGO_URI"])
db = client["ISIS2304H24202610"]

def serialize(doc):
    doc["_id"] = str(doc["_id"])
    return doc

def valid_object_id(id_str):
    try:
        return ObjectId(id_str)
    except (bson_errors.InvalidId, Exception):
        raise HTTPException(status_code=400, detail="ID inválido")

@app.get("/")
def inicio():
    return {"estado": "API Dann Alpes - Reseñas funcionando"}

@app.get("/resenas/hotel/{hotel_id}")
def get_resenas_hotel(hotel_id: int):
    try:
        resenas = list(db["resenas"].find({
            "hotel_id": {"$in": [hotel_id, str(hotel_id)]},
            "estado": "publicada"
        }))
        return [serialize(r) for r in resenas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resenas/cliente/{cliente_id}")
def get_resenas_cliente(cliente_id: int):
    try:
        resenas = list(db["resenas"].find({
            "cliente_id": {"$in": [cliente_id, str(cliente_id)]},
            "estado": {"$ne": "eliminada"}
        }))
        return [serialize(r) for r in resenas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resenas")
def crear_resena(datos: dict):
    try:
        if "cliente_id" in datos:
            datos["cliente_id"] = int(datos["cliente_id"])
        if "hotel_id" in datos:
            datos["hotel_id"] = int(datos["hotel_id"])
        if "reserva_id" in datos:
            datos["reserva_id"] = int(datos["reserva_id"])
        if "calificacion" in datos:
            datos["calificacion"] = int(datos["calificacion"])
        if "comentario" in datos and "texto" not in datos:
            datos["texto"] = datos.pop("comentario")
        datos["fecha_creacion"] = datetime.now().isoformat()
        datos["estado"] = "publicada"
        datos["destacada"] = False
        datos["votos"] = []
        datos["respuesta_admin"] = None
        result = db["resenas"].insert_one(datos)
        return {"mensaje": "Reseña creada", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/resenas/{resena_id}")
def editar_resena(resena_id: str, datos: dict):
    try:
        oid = valid_object_id(resena_id)
        campos = {}
        if "texto" in datos:
            campos["texto"] = datos["texto"]
        if "comentario" in datos:
            campos["texto"] = datos["comentario"]
        if "calificacion" in datos:
            campos["calificacion"] = int(datos["calificacion"])
        if not campos:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")
        result = db["resenas"].update_one({"_id": oid}, {"$set": campos})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        return {"mensaje": "Reseña actualizada", "modificados": result.modified_count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/resenas/{resena_id}")
def eliminar_resena(resena_id: str):
    try:
        oid = valid_object_id(resena_id)
        result = db["resenas"].update_one({"_id": oid}, {"$set": {"estado": "eliminada"}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        return {"mensaje": "Reseña eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resenas/{resena_id}/votos")
def votar_resena(resena_id: str, datos: dict):
    try:
        oid = valid_object_id(resena_id)
        db["resenas"].update_one({"_id": oid}, {"$push": {"votos": {"usuario_id": datos["usuario_id"]}}})
        return {"mensaje": "Voto registrado"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/resenas/{resena_id}/respuesta")
def responder_resena(resena_id: str, datos: dict):
    try:
        oid = valid_object_id(resena_id)
        db["resenas"].update_one(
            {"_id": oid},
            {"$set": {
                "respuesta_admin": {
                    "admin_id": datos["admin_id"],
                    "texto": datos["texto"],
                    "fecha_respuesta": datetime.now().isoformat()
                }
            }}
        )
        return {"mensaje": "Respuesta guardada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/resenas/{resena_id}/admin")
def eliminar_resena_admin(resena_id: str):
    try:
        oid = valid_object_id(resena_id)
        result = db["resenas"].update_one({"_id": oid}, {"$set": {"estado": "eliminada"}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Reseña no encontrada")
        return {"mensaje": "Reseña eliminada por administrador"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/resenas/{resena_id}/destacar")
def destacar_resena(resena_id: str):
    try:
        oid = valid_object_id(resena_id)
        db["resenas"].update_one({"_id": oid}, {"$set": {"destacada": True}})
        return {"mensaje": "Reseña destacada"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resenas/rfc1")
def rfc1():
    try:
        resultado = list(db["resenas"].aggregate([
            {"$match": {"estado": "publicada"}},
            {"$group": {
                "_id": "$hotel_id",
                "calificacion_promedio": {"$avg": "$calificacion"},
