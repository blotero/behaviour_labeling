from typing import Any

BEHAVIOR_DATA = {
    "Individuales": {
        "Comportamientos en fondo": "EVENT",
        "Respiración": "EVENT",
        "Respiración con desprendimiento de lodo": "EVENT",
        "Respiración con expulsión de agua": "EVENT",
        "Buceo exponiendo la cola": "EVENT",
        "Buceo sin exponer la cola": "EVENT",
        "Desplazamiento": "STATE",
        "Alejarse": "EVENT",
        "Acercarse": "EVENT",
        "Persecución": "EVENT",
        "Nado formando espejo de agua": "EVENT",
    },
    "Sociales": {
        "Comportamientos en fondo": "EVENT",
        "Interacción en fondo (Indefinido)": "EVENT",
        "Respiración sincronizada": "EVENT",
        "Romping": "EVENT",
        "Grouping": "EVENT",
        "Desplazamiento sincronizado": "STATE",
        "Nado uno sobre otro": "STATE",
        "Desplazamiento en fila": "STATE",
        "Arqueo de cuerpo para cambio de dirección": "EVENT",
        "Persecución": "EVENT",
    },
    "Reproductivo": {
        "Comportamientos en fondo": "EVENT",
        "Reposo en fondo": "EVENT",
        "Respiración": "EVENT",
        "Respiración sincronizada": "EVENT",
        "Respiración con expulsión de agua": "EVENT",
        "Desplazamiento en fila": "STATE",
        "Aproximación": "EVENT",
        "Aproximación rápida": "EVENT",
        "Alejarse": "EVENT",
        "Posicionamiento sobre dorso de la hembra (alineado)": "EVENT",
        "Posicionamiento sobre dorso de la hembra (de lado)": "EVENT",
        "Montaje en cruz sobre dorso o pedúnculo": "EVENT",
        "Sujeción": "EVENT",
        "Sujeción de pedúnculo": "EVENT",
        "Sujeción ventral (o vientre- vientre)": "EVENT",
        "Sujeción dorsal": "EVENT",
        "Sujeción lateral o de costado": "EVENT",
        "Giros de liberación": "EVENT",
        "Movimientos de liberación": "EVENT",
        "Golpeteo caudal": "EVENT",
        "Cabezazo": "EVENT",
        "Empuje de rotación": "EVENT",
        "Liberación": "EVENT",
    },
    "Madre-cria": {
        "Comportamientos en fondo": "EVENT",
        "Interacción en fondo (Indefinido)": "EVENT",
        "Respiración sincronizada": "EVENT",
        "Buceo exponiendo la cola": "EVENT",
        "Buceo sin exponer la cola": "EVENT",
        "Aproximación": "EVENT",
        "Alejarse": "EVENT",
        "Nado uno sobre otro": "EVENT",
        "Contacto aleta- aleta": "EVENT",
        "Contacto hocico- hocico": "EVENT",
        "Contacto hocico- cabeza": "EVENT",
        "Contacto hocico- dorso": "EVENT",
        "Giro de 360° sobre el propio eje": "EVENT",
        "Giro en ángulo agudo (cambio dirección)": "EVENT",
        "Giro 90° para cambio de dirección": "EVENT",
        "Arqueo de cuerpo para cambio de dirección": "EVENT",
        "Desplazamiento": "STATE",
    },
    "Embarcaciones": {
        "Respiración": "EVENT",
        "Aproximación": "EVENT",
        "Huida": "EVENT",
        "Cambio de dirección": "EVENT",
        "Arqueo de cuerpo para cambio de dirección": "EVENT",
        "Buceo": "EVENT",
        "Comportamientos de fondo": "EVENT",
        "Parar comportamiento de fondo": "EVENT",
        "Reagrupación": "EVENT",
    },
    "Interespecíficas": {
        "Interacción con peces": "EVENT",
    },
}


def get_recursive_parents(
    target: str, data: dict[str, Any], parents: list[str] | None = None
) -> list[str]:
    if parents is None:
        parents = []

    for key, value in data.items():
        if isinstance(value, dict):
            if target in value:
                return [key] + parents
            result = get_recursive_parents(target, value, [key] + parents)
            if result:
                return result

    return []
