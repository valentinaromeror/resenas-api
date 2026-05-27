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
        resenas = list(db["resenas"].find({"hotel_id": hotel_id, "estado": "publicada"}))
        return [serialize(r) for r in resenas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resenas/cliente/{cliente_id}")
def get_resenas_cliente(cliente_id: int):
    try:
        resenas = list(db["resenas"].find({"cliente_id": cliente_id}))
        return [serialize(r) for r in resenas]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resenas")
def crear_resena(datos: dict):
    try:
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
                "total_resenas": {"$sum": 1}
            }},
            {"$sort": {"calificacion_promedio": -1}},
            {"$limit": 10}
        ]))
        for r in resultado:
            r["hotel_id"] = r.pop("_id")
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resenas/rfc2/{hotel_id}")
def rfc2(hotel_id: int):
    try:
        resultado = list(db["resenas"].aggregate([
            {"$match": {"hotel_id": hotel_id, "estado": "publicada"}},
            {"$addFields": {
                "fecha_date": {
                    "$cond": {
                        "if": {"$eq": [{"$type": "$fecha_creacion"}, "string"]},
                        "then": {"$dateFromString": {"dateString": "$fecha_creacion"}},
                        "else": "$fecha_creacion"
                    }
                }
            }},
            {"$group": {
                "_id": {
                    "anio": {"$year": "$fecha_date"},
                    "mes": {"$month": "$fecha_date"}
                },
                "calificacion_promedio": {"$avg": "$calificacion"},
                "total_resenas": {"$sum": 1}
            }},
            {"$sort": {"_id.anio": 1, "_id.mes": 1}}
        ]))
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resenas/rfc3")
def rfc3(hotel_ids: str):
    try:
        ids = [int(x) for x in hotel_ids.split(",")]
        resultado = list(db["resenas"].aggregate([
            {"$match": {"hotel_id": {"$in": ids}}},
            {"$group": {
                "_id": "$hotel_id",
                "total_resenas": {"$sum": 1},
                "calificacion_promedio": {"$avg": "$calificacion"},
                "resenas_con_respuesta": {"$sum": {"$cond": [{"$ne": ["$respuesta_admin", None]}, 1, 0]}},
                "resenas_destacadas": {"$sum": {"$cond": ["$destacada", 1, 0]}}
            }},
            {"$project": {
                "_id": 1,
                "total_resenas": 1,
                "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
                "porcentaje_con_respuesta": {"$multiply": [{"$divide": ["$resenas_con_respuesta", "$total_resenas"]}, 100]},
                "porcentaje_destacadas": {"$multiply": [{"$divide": ["$resenas_destacadas", "$total_resenas"]}, 100]}
            }},
            {"$sort": {"calificacion_promedio": -1}}
        ]))
        for r in resultado:
            r["hotel_id"] = r.pop("_id")
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
