"""
Textos fijos del portal, extraídos del prototipo.

Van acá y no en la tabla contenido_portal porque son parte del diseño de la
pantalla, no contenido que el personal edite. Lo que sí edita el personal
(requisitos, horarios, descripción del proceso) vive en contenido_portal y
se consulta desde la base.
"""

MESES = {1:'ene',2:'feb',3:'mar',4:'abr',5:'may',6:'jun',7:'jul',8:'ago',9:'sep',10:'oct',11:'nov',12:'dic'}

FAQS = [
    {'pregunta': "¿Quiénes pueden donar sangre?",
     'respuesta': "Personas de 18 a 65 años, con un peso mínimo de 50 kg, en buen estado de salud general y que cumplan el cuestionario de tamizaje el día de la donación."},
    {'pregunta': "¿Cada cuánto puedo donar?",
     'respuesta': "Los hombres pueden donar hasta cada 3 meses y las mujeres hasta cada 4 meses. El sistema calcula tu próxima fecha habilitada automáticamente en tu perfil."},
    {'pregunta': "¿Necesito estar en ayunas?",
     'respuesta': "No es necesario el ayuno. Se recomienda comer liviano, evitar comidas grasas y dormir bien la noche anterior."},
    {'pregunta': "¿Cuánto dura el proceso?",
     'respuesta': "La extracción dura entre 10 y 15 minutos. Contando registro, cuestionario y recuperación, el proceso completo toma alrededor de 45 minutos."},
    {'pregunta': "¿Qué debo llevar el día de la cita?",
     'respuesta': "Únicamente tu documento de identidad vigente. Si vas a donar por reposición, tené a mano el nombre del paciente."},
    {'pregunta': "¿Duele donar sangre?",
     'respuesta': "Se siente un pinchazo breve al inicio, similar a un análisis de sangre común. Durante la extracción no debería haber dolor."},
    {'pregunta': "¿Puedo donar si tomo medicamentos?",
     'respuesta': "Depende del medicamento. El cuestionario de salud del día de la donación evalúa esto puntualmente con el personal del banco de sangre."},
    {'pregunta': "¿Qué pasa si me siento mal después de donar?",
     'respuesta': "Es normal sentir un leve mareo. Por eso hay una zona de recuperación con refrigerio antes de retirarte. Si el malestar persiste, el personal de enfermería te asistirá de inmediato."},
    {'pregunta': "¿Cómo agendo o cambio mi cita desde el portal?",
     'respuesta': "Desde \"Donar\" podés elegir fecha, horario y tipo de donación. Ya con una cita agendada, podés reprogramarla o cancelarla desde \"Mi cita\"."},
    {'pregunta': "¿Cómo sé cuándo puedo donar de nuevo?",
     'respuesta': "En tu Perfil vas a encontrar la fecha de tu próxima donación habilitada, calculada automáticamente a partir de tu última donación."},
]

DONACIONES = [
    {'k': "antes", 'img': "donacion10.jpg", 'paso': "Donación en equipo",
     'titulo': "Un acto colectivo de solidaridad",
     'alt': "Persona registrándose para donar sangre",
     'cuerpo': "Varias personas donan sangre simultáneamente en un espacio preparado, reflejando organización y compromiso comunitario para ayudar a quienes lo necesitan."},
    {'k': "durante", 'img': "donacion8.jpeg", 'paso': "Proceso seguro de donación",
     'titulo': "Atención profesional en cada paso",
     'alt': "Persona donando sangre en el sillón de donación",
     'cuerpo': "Un profesional de salud supervisa la extracción de sangre, garantizando un procedimiento controlado, seguro y confiable para el donante."},
    {'k': "despues", 'img': "donacion5.jpeg", 'paso': "Donar es vida",
     'titulo': "Solidaridad que se siente bien",
     'alt': "Persona descansando con un refrigerio después de donar sangre",
     'cuerpo': "Dos donantes sonríen durante el proceso, transmitiendo tranquilidad, bienestar y la satisfacción de contribuir a salvar vidas."},
]

BANNERS_INICIO = [
    {'k': "antes", 'img': "donacion20.png",
     'titulo': "Donar sangre es donar vida",
     'alt': "Personas esperando para donar sangre",
     'cuerpo': "Se parte de las personas que donan altruistamente."},
    {'k': "durante", 'img': "donacion25.jpg",
     'titulo': "Acompañado en todo momento",
     'alt': "Personal de enfermería acompañando a una persona que dona sangre",
     'cuerpo': "El personal de enfermería está con vos desde el ingreso hasta la recuperación."},
    {'k': "despues", 'img': "donacion28.jpg",
     'titulo': "Tu donación ya está ayudando",
     'alt': "Persona sonriendo después de donar sangre",
     'cuerpo': "Cada bolsa donada llega a pacientes del hospital en cuestión de días."},
]

PRIVACIDAD = [
    {'titulo': "1. Objeto",
     'cuerpo': "La presente Política describe las medidas técnicas y organizativas implementadas por el Sistema Web de Gestión de Donantes de Sangre del Hospital Regional de Luque para garantizar la protección, confidencialidad, integridad y trazabilidad de los datos personales y clínicos tratados."},
    {'titulo': "2. Principios de tratamiento de datos",
     'cuerpo': "El sistema opera conforme a los siguientes principios:\n\n • Licitud: los datos son recopilados únicamente con el consentimiento expreso y registrado del titular.\n\n • Finalidad: los datos se utilizan exclusivamente para los fines declarados al momento de su recopilación.\n\n • Minimización: cada vista o módulo del sistema expone únicamente los datos estrictamente necesarios para la función que cumple, limitando la visibilidad de información sensible al mínimo requerido.\n\n • Exactitud: el usuario puede consultar y actualizar sus datos de contacto en cualquier momento desde su perfil.\n\n • Seguridad: se aplican medidas técnicas activas para proteger los datos frente a accesos no autorizados, pérdida o alteración.\n\n • Trazabilidad: las transiciones de estado y los registros de auditoría son permanentes y no pueden ser eliminados ni sobrescritos."},
    {'titulo': "3. Control de acceso y roles",
     'cuerpo': "El sistema exige autenticación para acceder a toda información interna. El acceso a funcionalidades y datos está restringido según el rol asignado a cada usuario, de modo que ningún usuario puede realizar operaciones fuera del alcance de su perfil. La asignación y administración de roles es gestionada por el administrador del sistema, y cada acción queda registrada con identificación del responsable, fecha y hora."},
    {'titulo': "4. Medidas de seguridad técnica",
     'cuerpo': "El sistema implementa las siguientes medidas de seguridad conforme a las directrices OWASP (Open Web Application Security Project):\n\n • Cifrado en tránsito: toda la comunicación entre el navegador del usuario y el servidor se realiza mediante protocolo HTTPS con certificado TLS vigente.\n\n • Cifrado en reposo: los atributos de datos sensibles almacenados en la base de datos son cifrados para proteger su confidencialidad ante accesos no autorizados a nivel de infraestructura.\n\n • Almacenamiento seguro de contraseñas: las contraseñas de los usuarios son almacenadas mediante funciones de hash con sal (bcrypt u equivalente), impidiendo su recuperación en texto plano.\n\n • Copias de seguridad: el sistema realiza copias de seguridad periódicas de la base de datos para garantizar la disponibilidad y recuperación de la información ante fallos.\n\n • Registro de auditoría: el sistema registra las principales acciones y modificaciones efectuadas por los usuarios, incluyendo accesos, cambios de datos, gestión de solicitudes y modificaciones de roles, con identificación del responsable, fecha y hora. Estos registros no pueden ser eliminados ni sobrescritos.\n\n • Verificación de identidad: el registro de nuevos usuarios requiere la verificación de la dirección de correo electrónico mediante un código de un solo uso antes de habilitar el acceso al sistema.\n\n • Recuperación de acceso: el sistema ofrece un mecanismo seguro de recuperación y restablecimiento de contraseña. El personal autorizado puede brindar soporte adicional de desbloqueo, quedando registrada cada acción realizada."},
    {'titulo': "5. Pseudonimización y conservación de registros clínicos",
     'cuerpo': "Ante la solicitud de supresión de una cuenta, los datos de contacto e identificatorios del usuario serán eliminados. Sin embargo, el registro histórico de donaciones será conservado de forma pseudonimizada, desvinculado de cualquier dato identificatorio directo, en cumplimiento del deber de conservación sanitaria establecido por la normativa vigente. Estos registros no podrán ser eliminados ni sobrescritos, garantizando la trazabilidad clínica."},
    {'titulo': "6. Accesibilidad y compatibilidad",
     'cuerpo': "El sistema ha sido desarrollado considerando criterios de accesibilidad conforme a las pautas WCAG 2.1 nivel AA, con el objetivo de garantizar su uso por personas de distintos rangos etarios y niveles de experiencia tecnológica. El diseño es adaptable (responsive) para su uso desde dispositivos móviles y navegadores actuales."},
    {'titulo': "7. Contacto",
     'cuerpo': "Para consultas sobre privacidad, ejercicio de derechos o soporte relacionado con los datos personales, el usuario podrá dirigirse al Banco de sangre del Hospital Regional de Luque a través de los canales de contacto institucionales disponibles en el sistema."},
]

TERMINOS = [
    {'titulo': "1. Aceptación",
     'cuerpo': "Al registrarse en este sistema y marcar la casilla de aceptación, el usuario declara haber leído, comprendido y aceptado los presentes Términos y Condiciones en su totalidad. El sistema registrará automáticamente la fecha y hora exacta de esta aceptación, constituyendo un consentimiento informado digital válido conforme a la Ley N.º 1682/01 de Protección de Datos Personales de la República del Paraguay y su modificatoria Ley N.º 1969/02."},
    {'titulo': "2. Datos personales recopilados",
     'cuerpo': "Al completar el registro, el sistema recopilará los siguientes datos:\n\n • Nombre completo\n\n • Documento de identidad\n\n • Fecha de nacimiento\n\n • Sexo\n\n • Grupo sanguíneo\n\n • Número de teléfono de contacto\n\n • Dirección de correo electrónico\n\n • Historial de donaciones registradas en el sistema\n\nLa dirección de correo electrónico será verificada mediante un código de un solo uso enviado al momento del registro, conforme a los mecanismos de seguridad del sistema."},
    {'titulo': "3. Finalidad del tratamiento",
     'cuerpo': "Los datos recopilados serán utilizados exclusivamente para:\n\n • Gestión interna del Banco de sangre del Hospital Regional de Luque.\n\n • Registro, seguimiento y trazabilidad del historial de donaciones del usuario.\n\n • Contacto con el usuario a través del canal de notificación que él mismo elija al momento del registro o desde la configuración de su cuenta.\n\n • Elaboración de estadísticas internas de carácter anónimo y agregado para fines de gestión hospitalaria e investigación institucional.\n\nEn todo momento, el sistema limitará la exposición de datos personales al mínimo necesario según la función que cada vista o módulo requiera."},
    {'titulo': "4. Canal de notificación y preferencias de comunicación",
     'cuerpo': "Al registrarse, el usuario podrá seleccionar su canal de notificación preferido (correo electrónico, SMS u otro disponible en el sistema) y gestionar sus preferencias de comunicación desde la configuración de su cuenta. El usuario podrá darse de baja de las notificaciones en cualquier momento, sin que ello afecte el acceso al sistema ni la validez del consentimiento otorgado previamente. El sistema registrará cada cambio de preferencia."},
    {'titulo': "5. Confidencialidad y no divulgación a terceros",
     'cuerpo': "Los datos personales del usuario no serán compartidos, vendidos ni cedidos a terceros bajo ninguna circunstancia, salvo que medie una obligación legal expresa o una orden judicial. El acceso estará restringido al personal autorizado del Banco de sangre, conforme al esquema de roles y permisos del sistema."},
    {'titulo': "6. Derechos del titular",
     'cuerpo': "Conforme a la Ley N.º 1682/01, el usuario tiene derecho a:\n\n • Acceso: consultar en cualquier momento sus datos de contacto, su historial de donaciones, la fecha estimada de habilitación para una próxima donación y sus citas programadas, directamente desde su perfil en el sistema.\n\n • Rectificación: actualizar sus datos de contacto cuando lo considere necesario.\n\n • Cancelación y supresión: solicitar la eliminación de su cuenta y de sus datos de contacto. En cumplimiento del deber de conservación sanitaria, el registro histórico de donaciones será conservado de forma pseudonimizada, desvinculado de cualquier dato identificatorio directo, conforme a la política de datos del sistema.\n\n • Oposición: oponerse al tratamiento de sus datos para finalidades específicas, en particular respecto a las comunicaciones y notificaciones."},
    {'titulo': "7. Conservación de los datos",
     'cuerpo': "Los datos de contacto e identificatorios serán conservados mientras el usuario mantenga su cuenta activa. Ante una solicitud de supresión, dichos datos serán eliminados en un plazo no mayor a 30 días. Los registros de donación serán conservados de forma pseudonimizada por el tiempo que establezca la normativa sanitaria vigente, sin posibilidad de ser eliminados ni sobrescritos, garantizando la trazabilidad del historial clínico."},
    {'titulo': "8. Modificaciones",
     'cuerpo': "El Hospital Regional de Luque se reserva el derecho de modificar los presentes Términos y Condiciones. Cualquier cambio relevante será notificado al usuario a través del canal de notificación registrado con una anticipación mínima de 15 días."},
]


MESES_LARGO = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
DIAS_LARGO = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def fecha_larga(d, con_dia=True):
    """date -> 'sábado 26 de septiembre de 2026'. El locale del sistema no
    tiene por qué estar en español, así que se arma a mano."""
    if not d:
        return ""
    texto = f"{d.day} de {MESES_LARGO[d.month - 1]} de {d.year}"
    return f"{DIAS_LARGO[d.weekday()]} {texto}" if con_dia else texto


def hora_corta(h):
    """time -> '07:30'."""
    return h.strftime("%H:%M") if h else ""
