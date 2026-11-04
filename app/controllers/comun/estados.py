"""
Pares de estado que el DER admite.

La base los exige en los triggers. Estas mismas tuplas las usa el backend
antes de escribir, para devolver un mensaje claro.
"""
from datetime import timedelta

DIAS_VIGENCIA_SOLICITUD = 7

CITA = frozenset({
    ("Pendiente", "Confirmada"),
    ("Pendiente", "Cancelada"),
    ("Confirmada", "Ausente"),
    ("Confirmada", "Completada"),
    ("Confirmada", "No apto"),
})

CITACION = frozenset({
    ("Pendiente", "Confirmada"),
    ("Pendiente", "Cancelada"),
    ("Pendiente", "Realizada"),
    ("Pendiente", "Ausente"),
    ("Confirmada", "Realizada"),
    ("Confirmada", "Ausente"),
    ("Cancelada", "Pendiente"),
})

UNIDAD = frozenset({
    ("Registrada", "En laboratorio"),
    ("En laboratorio", "En stock"),
    ("En laboratorio", "Descartada"),
    ("En stock", "Asignada"),
    ("En stock", "Vencida"),
    ("Asignada", "Utilizada"),
    ("Asignada", "En stock"),
    ("Asignada", "Vencida"),
})


def transicion_valida(pares, origen, destino):
    return (origen, destino) in pares


def solicitud_vencida(fecha_publicacion, hoy, dias=DIAS_VIGENCIA_SOLICITUD):
    """True cuando ya se cumplieron los días desde la publicación."""
    return fecha_publicacion + timedelta(days=dias) <= hoy
