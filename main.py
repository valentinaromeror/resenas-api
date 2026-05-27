from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://iacademy2.oracle.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(os.environ["MONGO_URI"])
db = client["ISIS2304H24202610"]

@app.get("/")
def inicio():
    return {"estado": "API Dann Alpes - Reseñas funcionando"}

@app.get("/resenas/hotel/{hotel_id}")
def get_resenas_hotel(hotel_id: int):
    resenas = list(db["resenas"].find(
        {"hotel_id": hotel_id, "estado": "publicada"},
        {"_id": 0}
    ))
    return resenas

@app.post("/resenas")
def crear_resena(datos: dict):
    datos["fecha_creacion"] = datetime.now().isoformat()
    datos["estado"] = "publicada"
    datos["destacada"] = False
    datos["votos"] = []
    datos["respuesta_admin"] = None
    result = db["resenas"].insert_one(datos)
    datos.pop("_id", None)
    return {"mensaje": "Reseña creada", "id": str(result.inserted_id)}

@app.put("/resenas/{resena_id}")
def editar_resena(resena_id: str, datos: dict):
    campos = {}
    if "texto" in datos:
        campos["texto"] = datos["texto"]
    if "calificacion" in datos:
        campos["calificacion"] = datos["calificacion"]
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": campos}
    )
    return {"mensaje": "Reseña actualizada"}

@app.delete("/resenas/{resena_id}")
def eliminar_resena(resena_id: str):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"estado": "eliminada"}}
    )
    return {"mensaje": "Reseña eliminada"}

@app.post("/resenas/{resena_id}/votos")
def votar_resena(resena_id: str, datos: dict):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$push": {"votos": {"usuario_id": datos["usuario_id"]}}}
    )
    return {"mensaje": "Voto registrado"}

@app.get("/resenas/cliente/{cliente_id}")
def get_resenas_cliente(cliente_id: int):
    resenas = list(db["resenas"].find(
        {"cliente_id": cliente_id},
        {"_id": 0}
    ))
    return resenas

@app.put("/resenas/{resena_id}/respuesta")
def responder_resena(resena_id: str, datos: dict):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {
            "respuesta_admin": {
                "admin_id": datos["admin_id"],
                "texto": datos["texto"],
                "fecha_respuesta": datetime.now().isoformat()
            }
        }}
    )
    return {"mensaje": "Respuesta guardada"}

@app.delete("/resenas/{resena_id}/admin")
def eliminar_resena_admin(resena_id: str):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"estado": "eliminada"}}
    )
    return {"mensaje": "Reseña eliminada por administrador"}

@app.put("/resenas/{resena_id}/destacar")
def destacar_resena(resena_id: str):
    db["resenas"].update_one(
        {"_id": ObjectId(resena_id)},
        {"$set": {"destacada": True}}
    )
    return {"mensaje": "Reseña destacada"}

@app.get("/resenas/rfc1")
def rfc1():
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

@app.get("/resenas/rfc2/{hotel_id}")
def rfc2(hotel_id: int):
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

@app.get("/resenas/rfc3")
def rfc3(hotel_ids: str):
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
