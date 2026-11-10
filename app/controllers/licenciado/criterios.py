"""
Qué causas del catálogo `diferimiento` corresponden a cada paso de la atención.

El esquema no guarda el paso de una causa: se arma acá por nombre, igual que
preguntas.py completa lo que la tabla `pregunta` no tiene. Los días y el tipo
salen del catálogo; este archivo no los repite.

Solo hay causas temporales. Lo permanente lo confirma el laboratorio.
"""

# Pregunta (enunciado de la tabla) -> (respuesta que difiere, causas posibles).
# Si hay una sola causa, el modal la propone marcada; si hay varias, elige
# el personal. Las preguntas que no figuran no generan un diferimiento
# temporal en este paso.
POR_PREGUNTA = {
    "¿Tuvo en la última semana gripe, estado febril, diarrea o tratamiento odontológico?": (
        "Si", ("Cuadro febril o gripal", "Enfermedad infecciosa reciente",
               "Tratamiento odontológico simple",
               "Extracción dental, endodoncia o implante")),
    "¿Tuvo ictericia (piel amarilla), hepatitis o análisis positivo de hepatitis?": (
        "Si", ("Ictericia de causa desconocida",)),
    "¿Tuvo enfermedad de Chagas, leishmaniasis, tuberculosis, mononucleosis, paludismo, dengue o análisis positivo para las mismas?": (
        "Si", ("Dengue", "Tuberculosis tratada")),
    "¿Ha mantenido relaciones sexuales con alguna persona que haya tenido alguna enfermedad citada en la pregunta anterior?": (
        "Si", ("Contacto sexual con pareja de riesgo",)),
    "¿Ha recibido tratamiento de acupuntura, tatuaje, colocación de aros, piercing o accidente de punción?": (
        "Si", ("Tatuaje, piercing o acupuntura",
               "Accidente cortopunzante o exposición a sangre")),
    "¿Estuvo bajo tratamiento antirrábico o en exposición a un animal rabioso?": (
        "Si", ("Profilaxis antirrábica posexposición",)),
    "¿Mantuvo relaciones sexuales con personas comprendidas en los puntos anteriores?": (
        "Si", ("Contacto sexual con pareja de riesgo",)),
    "¿Estuvo bajo tratamiento médico?": (
        "Si", ("Tratamiento con antibióticos", "Corticoides orales o inyectables",
               "Isotretinoína", "Finasterida o dutasterida", "Acitretina")),
    "¿Sufrió algún tipo de cirugía?": (
        "Si", ("Cirugía o procedimiento invasivo",)),
    "¿Estuvo detenido por más de 72 horas en una comisaría o institución carcelaria?": (
        "Si", ("Detención de más de 72 horas",)),
    "¿Usted fue transfundido con algún componente sanguíneo o factor de coagulación, o recibió injerto y/o trasplante de órgano?": (
        "Si", ("Transfusión recibida",)),
    "¿Mantuvo relaciones sexuales con personas con VIH/SIDA o hepatitis, o con análisis positivo para las mismas?": (
        "Si", ("Contacto sexual con pareja de riesgo",)),
    "¿Mantuvo relaciones sexuales con personas que hayan sido transfundidas y/o hayan recibido injerto o trasplante de tejido?": (
        "Si", ("Contacto sexual con pareja de riesgo",)),
    "¿Pagó o recibió dinero y/o droga a cambio de sexo?": (
        "Si", ("Sexo a cambio de dinero o drogas",)),
    "¿Mantuvo relaciones sexuales ocasionales sin protección?": (
        "Si", ("Nueva pareja o varias parejas con relaciones anales",)),
    "¿Tuvo relaciones sexuales vía anal?": (
        "Si", ("Nueva pareja o varias parejas con relaciones anales",)),
    "¿Ha recibido vacunas o inmunización?": (
        "Si", ("Vacuna contra la hepatitis B", "Vacuna de virus vivos atenuados",
               "Vacuna contra el dengue", "Vacuna desconocida o en investigación")),
    "¿Está o estuvo embarazada o se encuentra en período de lactancia?": (
        "Si", ("Embarazo o lactancia",)),
    "Si ha estado fuera del país, ¿se ha sentido enfermo/a días previos o posteriores a su regreso?": (
        "Si", ("Viaje a zona endémica", "Enfermedad infecciosa reciente")),
    "¿Se siente Ud. bien y goza de buena salud?": (
        "No", ("Cuadro febril o gripal", "Enfermedad infecciosa reciente")),
    "¿Consumiste alcohol en las últimas 12 horas?": (
        "Si", ("Consumo de alcohol en las últimas 12 horas",)),
    "¿Estás tomando alguna medicación actualmente?": (
        "Si", ("Tratamiento con antibióticos", "Corticoides orales o inyectables",
               "Isotretinoína", "Finasterida o dutasterida", "Acitretina")),
    "¿Brazo sin lesiones de agujas?": (
        "No", ("Lesión en el brazo de punción",)),
}

# Lo que ofrece el autocompletado del cuestionario: toda causa del paso.
CUESTIONARIO = tuple(dict.fromkeys(
    causa for _, causas in POR_PREGUNTA.values() for causa in causas))

# Medición -> (causa si queda por debajo del mínimo, causa si supera el máximo).
MEDICION = {
    "TEMPERATURA": ("Temperatura fuera de rango", "Cuadro febril o gripal"),
    "PESO": ("Peso fuera de rango", "Peso fuera de rango"),
    "PAS": ("Presión arterial fuera de rango", "Presión arterial fuera de rango"),
    "PAD": ("Presión arterial fuera de rango", "Presión arterial fuera de rango"),
    "HB": ("Hemoglobina fuera de rango", "Hemoglobina fuera de rango"),
}

# Incidente de extracción (valor que guarda `extraccion.observacion`) -> causa.
EXTRACCION = {
    "Hematoma": "Hematoma en el sitio de punción",
    "Punción arterial": "Punción arterial",
    "Dolor local": "Dolor local en el sitio de punción",
    "Hormigueo": "Hormigueo o irritación nerviosa",
    "Lipotimia": "Lipotimia",
    "Vasovagal": "Reacción vasovagal",
    "Hipotensión": "Hipotensión asociada a la extracción",
    "Náuseas": "Náuseas o vómitos asociados a la extracción",
    "Alérgica": "Reacción alérgica asociada a la extracción",
}


def causa_de_medicion(codigo, valor, minimo, maximo):
    """La causa que corresponde a un valor fuera de rango, o None si está en rango."""
    bajo, alto = MEDICION.get(codigo, (None, None))
    if valor < minimo:
        return bajo
    if valor > maximo:
        return alto
    return None
