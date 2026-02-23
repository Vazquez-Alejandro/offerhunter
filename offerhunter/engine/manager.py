import json
import os

DB_FILE = "vistos.json"

def cargar_vistos():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(json.load(f))
    return set()

def guardar_vistos(vistos):
    with open(DB_FILE, "w") as f:
        json.dump(list(vistos), f)

def filtrar_nuevos(ofertas):
    vistos = cargar_vistos()
    nuevos = []
    
    for o in ofertas:
        # Usamos el link como ID único
        if o['link'] not in vistos:
            nuevos.append(o)
            vistos.add(o['link'])
            
    guardar_vistos(vistos)
    return nuevos