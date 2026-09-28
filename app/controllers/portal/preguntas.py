"""
El cuestionario oficial del banco de sangre: las 36 preguntas de la Parte A.

Por qué está acá y no en la base: la tabla `pregunta` guarda el enunciado,
la parte (A o B) y si un "sí" sugiere diferimiento. No tiene dónde guardar
el bloque del formulario, el número de orden, la aclaración que piden
algunas preguntas ni cuál de las dos respuestas es la que el personal
revisa. Como el esquema no se toca, eso vive en este archivo y se empareja
con las filas de la base por el enunciado, que es único.

El texto de los enunciados es el mismo que carga database/catalogos.sql. Si
se cambia uno, hay que cambiarlo en los dos lados o la pregunta queda sin
su bloque; database/verificar_preguntas.py lo comprueba.

Sobre `alerta`: dice cuál de las dos respuestas tiene que mirar el
personal, y no siempre es el "sí" —en «¿Se siente bien?» lo preocupante es
el "no"—. El sistema marca, no decide: la aptitud la determina el personal
de salud.
"""
from collections import namedtuple

P = namedtuple("P", "orden seccion enunciado alerta detalle nota")
P.__new__.__defaults__ = (None, None, None)

# Los tres bloques, en el orden del formulario en papel.
SECCIONES = ["En la actualidad",
             "Antecedentes personales",
             "En los ultimos 12 meses"]

PREGUNTAS = [
    P(1, "En la actualidad", "¿Se siente Ud. bien y goza de buena salud?",
      alerta="No"),
    P(2, "En la actualidad", "¿Padece de presión alta o baja?",
      alerta="Si"),
    P(3, "En la actualidad", "¿Está tomando alguna medicación?",
      alerta="Si", detalle="¿Cuál y por qué?"),
    P(4, "En la actualidad", "¿Ha descansado o comido bien las últimas 24 horas?",
      alerta="No"),
    P(5, "En la actualidad", "¿Ha tomado aspirina los últimos 5 días?",
      alerta="Si", nota="Se toma en cuenta solo para la donación de plaquetas."),
    P(6, "En la actualidad", "¿Tuvo en la última semana gripe, estado febril, diarrea o tratamiento odontológico?",
      alerta="Si"),
    P(7, "En la actualidad", "¿Recibió dinero para realizar esta donación?",
      alerta="Si"),
    P(8, "En la actualidad", "¿Sabe que el portador del virus VIH/SIDA puede contagiar estando aparentemente sano?",
      alerta="No"),
    P(9, "En la actualidad", "¿Usted dona solamente para que le realicen los análisis del VIH/SIDA?",
      alerta="Si"),
    P(10, "Antecedentes personales", "¿Alguna vez ha donado sangre, plaquetas o plasma?",
      alerta=None, detalle="¿Dónde y cuándo?"),
    P(11, "Antecedentes personales", "¿Alguna vez ha sido rechazado como donante?",
      alerta="Si"),
    P(12, "Antecedentes personales", "¿Fue llamado después de una donación con respecto a resultados de sus análisis?",
      alerta="Si"),
    P(13, "Antecedentes personales", "¿Tuvo angina (dolor) de pecho, infarto, enfermedades del corazón o pulmón?",
      alerta="Si"),
    P(14, "Antecedentes personales", "¿Tuvo cáncer, enfermedades autoinmunes, hipertiroidismo, úlcera, psoriasis, convulsiones, desmayos, trastornos neurológicos o diabetes?",
      alerta="Si"),
    P(15, "Antecedentes personales", "¿Tuvo enfermedades de la sangre o hemorragias?",
      alerta="Si"),
    P(16, "Antecedentes personales", "¿Tuvo ictericia (piel amarilla), hepatitis o análisis positivo de hepatitis?",
      alerta="Si"),
    P(17, "Antecedentes personales", "¿Tuvo enfermedad de Chagas, leishmaniasis, tuberculosis, mononucleosis, paludismo, dengue o análisis positivo para las mismas?",
      alerta="Si"),
    P(18, "Antecedentes personales", "¿Ha recibido hormonas de crecimiento de origen humano?",
      alerta="Si"),
    P(19, "Antecedentes personales", "¿Ha tenido sífilis, gonorrea, tratamiento o análisis positivo para alguna enfermedad de transmisión sexual (VDRL)?",
      alerta="Si"),
    P(20, "Antecedentes personales", "¿Ha mantenido relaciones sexuales con alguna persona que haya tenido alguna enfermedad citada en la pregunta anterior?",
      alerta="Si"),
    P(21, "En los ultimos 12 meses", "¿Ha recibido tratamiento de acupuntura, tatuaje, colocación de aros, piercing o accidente de punción?",
      alerta="Si"),
    P(22, "En los ultimos 12 meses", "¿Estuvo bajo tratamiento antirrábico o en exposición a un animal rabioso?",
      alerta="Si"),
    P(23, "En los ultimos 12 meses", "¿Estuvo bajo tratamiento médico?",
      alerta="Si"),
    P(24, "En los ultimos 12 meses", "¿Sufrió algún tipo de cirugía?",
      alerta="Si"),
    P(25, "En los ultimos 12 meses", "¿Estuvo detenido por más de 72 horas en una comisaría o institución carcelaria?",
      alerta="Si"),
    P(26, "En los ultimos 12 meses", "¿Usted fue transfundido con algún componente sanguíneo o factor de coagulación, o recibió injerto y/o trasplante de órgano?",
      alerta="Si"),
    P(27, "En los ultimos 12 meses", "¿Mantuvo relaciones sexuales con personas con VIH/SIDA o hepatitis, o con análisis positivo para las mismas?",
      alerta="Si"),
    P(28, "En los ultimos 12 meses", "¿Mantuvo relaciones sexuales con personas que hayan sido transfundidas y/o hayan recibido injerto o trasplante de tejido?",
      alerta="Si"),
    P(29, "En los ultimos 12 meses", "¿Pagó o recibió dinero y/o droga a cambio de sexo?",
      alerta="Si"),
    P(30, "En los ultimos 12 meses", "¿Mantuvo relaciones sexuales con personas comprendidas en los puntos 21 y 22?",
      alerta="Si"),
    P(31, "En los ultimos 12 meses", "¿Mantuvo relaciones sexuales ocasionales sin protección?",
      alerta="Si"),
    P(32, "En los ultimos 12 meses", "¿Tuvo relaciones sexuales vía anal?",
      alerta="Si"),
    P(33, "En los ultimos 12 meses", "¿Ha recibido vacunas o inmunización?",
      alerta="Si", detalle="¿Cuáles?"),
    P(34, "En los ultimos 12 meses", "¿Está o estuvo embarazada o se encuentra en período de lactancia?",
      alerta="Si"),
    P(35, "En los ultimos 12 meses", "Si ha estado fuera del país, ¿se ha sentido enfermo/a días previos o posteriores a su regreso?",
      alerta="Si"),
    P(36, "En los ultimos 12 meses", "¿Ud. ha leído y comprendido este cuestionario y fueron aclaradas todas sus dudas?",
      alerta="No"),
]

# Por enunciado, que es como se empareja con las filas de la tabla.
POR_ENUNCIADO = {p.enunciado: p for p in PREGUNTAS}


def de_seccion(seccion):
    return [p for p in PREGUNTAS if p.seccion == seccion]


def datos_de(enunciado):
    """Los datos de formulario de esa pregunta, o None si no es de la Parte A."""
    return POR_ENUNCIADO.get(enunciado)
