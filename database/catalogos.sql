-- ============================================================================
--  catalogos.sql — Datos fijos del sistema.
--
--  Esto NO son datos de prueba: sin estas filas el sistema no funciona.
--  Nadie puede registrarse sin un rol, no hay grupo sanguíneo que asignar,
--  no hay franjas para agendar y el cuestionario queda sin preguntas.
--
--  schema.sql crea la estructura; este script la llena.
--
--  Cómo correrlo (pgAdmin): Query Tool sobre gestion_donantes → pegar → Ejecutar.
--
--  Se puede ejecutar más de una vez sin duplicar nada: cada bloque comprueba
--  antes de insertar.
-- ============================================================================

BEGIN;

-- ---------- Roles ----------
INSERT INTO rol (codigo, nombre) VALUES
  ('DONANTE',    'Donante'),
  ('ENFERMERIA', 'Enfermería'),
  ('JEFATURA',   'Jefatura'),
  ('ADMIN',      'Administrador')
ON CONFLICT (codigo) DO NOTHING;

-- ---------- Tipos de sangre ----------
INSERT INTO tipo_sangre (grupo, factor) VALUES
  ('O','-'), ('O','+'), ('A','-'), ('A','+'),
  ('B','-'), ('B','+'), ('AB','-'), ('AB','+')
ON CONFLICT (grupo, factor) DO NOTHING;

-- ---------- Compatibilidad donante -> receptor ----------
-- 27 pares. O- es donante universal, AB+ receptor universal.
INSERT INTO compatibilidad_abo_rh (id_tipo_donante, id_tipo_receptor)
SELECT d.id_tipo_sangre, r.id_tipo_sangre
  FROM (VALUES
     ('O-','O-'),('O-','O+'),('O-','A-'),('O-','A+'),
     ('O-','B-'),('O-','B+'),('O-','AB-'),('O-','AB+'),
     ('O+','O+'),('O+','A+'),('O+','B+'),('O+','AB+'),
     ('A-','A-'),('A-','A+'),('A-','AB-'),('A-','AB+'),
     ('A+','A+'),('A+','AB+'),
     ('B-','B-'),('B-','B+'),('B-','AB-'),('B-','AB+'),
     ('B+','B+'),('B+','AB+'),
     ('AB-','AB-'),('AB-','AB+'),
     ('AB+','AB+')
  ) AS p(donante, receptor)
  JOIN tipo_sangre d ON rtrim(d.grupo) || d.factor = p.donante
  JOIN tipo_sangre r ON rtrim(r.grupo) || r.factor = p.receptor
 WHERE NOT EXISTS (
     SELECT 1 FROM compatibilidad_abo_rh c
      WHERE c.id_tipo_donante  = d.id_tipo_sangre
        AND c.id_tipo_receptor = r.id_tipo_sangre
 );

-- ---------- Tipos de medición y umbrales de aptitud ----------
-- El trigger fn_medicion_apto usa valor_minimo y valor_maximo para calcular
-- "apto" solo: el personal carga el valor, no la conclusión (RN01).
INSERT INTO tipo_medicion (codigo, nombre, unidad, valor_minimo, valor_maximo) VALUES
  ('TEMPERATURA', 'Temperatura corporal', '°C',   35.5, 37.5),
  ('PESO',        'Peso',                 'kg',   50,   250),
  ('PAS',         'Presión sistólica',    'mmHg', 90,   160),
  ('PAD',         'Presión diastólica',   'mmHg', 60,   100),
  ('HB',          'Hemoglobina',          'g/dL', 12.5, 20)
ON CONFLICT (codigo) DO NOTHING;

-- ---------- Catálogo de diferimientos ----------
-- dias_rehabilitacion alimenta el trigger fn_registro_fecha_fin, que calcula
-- la fecha de habilitación. Los permanentes van con NULL, que es lo que pide
-- el CHECK ck_diferimiento_dias.
INSERT INTO diferimiento (nombre, tipo, dias_rehabilitacion) VALUES
  ('Cuadro febril o gripal',            'Temporal',    14),
  ('Tratamiento con antibióticos',      'Temporal',    15),
  ('Enfermedad infecciosa reciente',    'Temporal',    30),
  ('Viaje a zona endémica',             'Temporal',    90),
  ('Tatuaje, piercing o acupuntura',    'Temporal',   120),
  ('Cirugía o procedimiento invasivo',  'Temporal',   180),
  ('Transfusión recibida',              'Temporal',   365),
  ('Embarazo o lactancia',              'Temporal',   180),
  ('Hemoglobina baja',                  'Temporal',    30),
  ('Presión arterial fuera de rango',   'Temporal',     7),
  ('Peso inferior al mínimo',           'Temporal',    30),
  ('Serología reactiva',                'Permanente', NULL)
ON CONFLICT (nombre) DO NOTHING;

-- ---------- Cuestionario ----------
-- Parte A: el cuestionario oficial del banco de sangre, las 36 preguntas
-- que responde el donante antes de presentarse. El portal se lo manda por
-- correo unas horas antes de su cita.
--
-- Parte B: condiciones del día, las carga el personal en el check-in.
--
-- preselecciona_exclusion marca las preguntas cuyo "sí" sugiere no apto,
-- que es lo único de esto que el esquema guarda. El bloque del formulario,
-- el número de orden y la aclaración que piden algunas están en
-- app/controllers/portal/preguntas.py, emparejados por el enunciado.
-- Si se edita un enunciado acá, hay que editarlo también allá:
-- database/verificar_preguntas.py comprueba que los dos coincidan.

INSERT INTO pregunta (parte, enunciado, preselecciona_exclusion)
SELECT * FROM (VALUES
  ('A', '¿Se siente Ud. bien y goza de buena salud?', false),
  ('A', '¿Padece de presión alta o baja?', true),
  ('A', '¿Está tomando alguna medicación?', true),
  ('A', '¿Ha descansado o comido bien las últimas 24 horas?', false),
  ('A', '¿Ha tomado aspirina los últimos 5 días?', true),
  ('A', '¿Tuvo en la última semana gripe, estado febril, diarrea o tratamiento odontológico?', true),
  ('A', '¿Recibió dinero para realizar esta donación?', true),
  ('A', '¿Sabe que el portador del virus VIH/SIDA puede contagiar estando aparentemente sano?', false),
  ('A', '¿Usted dona solamente para que le realicen los análisis del VIH/SIDA?', true),
  ('A', '¿Alguna vez ha donado sangre, plaquetas o plasma?', false),
  ('A', '¿Alguna vez ha sido rechazado como donante?', true),
  ('A', '¿Fue llamado después de una donación con respecto a resultados de sus análisis?', true),
  ('A', '¿Tuvo angina (dolor) de pecho, infarto, enfermedades del corazón o pulmón?', true),
  ('A', '¿Tuvo cáncer, enfermedades autoinmunes, hipertiroidismo, úlcera, psoriasis, convulsiones, desmayos, trastornos neurológicos o diabetes?', true),
  ('A', '¿Tuvo enfermedades de la sangre o hemorragias?', true),
  ('A', '¿Tuvo ictericia (piel amarilla), hepatitis o análisis positivo de hepatitis?', true),
  ('A', '¿Tuvo enfermedad de Chagas, leishmaniasis, tuberculosis, mononucleosis, paludismo, dengue o análisis positivo para las mismas?', true),
  ('A', '¿Ha recibido hormonas de crecimiento de origen humano?', true),
  ('A', '¿Ha tenido sífilis, gonorrea, tratamiento o análisis positivo para alguna enfermedad de transmisión sexual (VDRL)?', true),
  ('A', '¿Ha mantenido relaciones sexuales con alguna persona que haya tenido alguna enfermedad citada en la pregunta anterior?', true),
  ('A', '¿Ha recibido tratamiento de acupuntura, tatuaje, colocación de aros, piercing o accidente de punción?', true),
  ('A', '¿Estuvo bajo tratamiento antirrábico o en exposición a un animal rabioso?', true),
  ('A', '¿Estuvo bajo tratamiento médico?', true),
  ('A', '¿Sufrió algún tipo de cirugía?', true),
  ('A', '¿Estuvo detenido por más de 72 horas en una comisaría o institución carcelaria?', true),
  ('A', '¿Usted fue transfundido con algún componente sanguíneo o factor de coagulación, o recibió injerto y/o trasplante de órgano?', true),
  ('A', '¿Mantuvo relaciones sexuales con personas con VIH/SIDA o hepatitis, o con análisis positivo para las mismas?', true),
  ('A', '¿Mantuvo relaciones sexuales con personas que hayan sido transfundidas y/o hayan recibido injerto o trasplante de tejido?', true),
  ('A', '¿Pagó o recibió dinero y/o droga a cambio de sexo?', true),
  ('A', '¿Mantuvo relaciones sexuales con personas comprendidas en los puntos 21 y 22?', true),
  ('A', '¿Mantuvo relaciones sexuales ocasionales sin protección?', true),
  ('A', '¿Tuvo relaciones sexuales vía anal?', true),
  ('A', '¿Ha recibido vacunas o inmunización?', true),
  ('A', '¿Está o estuvo embarazada o se encuentra en período de lactancia?', true),
  ('A', 'Si ha estado fuera del país, ¿se ha sentido enfermo/a días previos o posteriores a su regreso?', true),
  ('A', '¿Ud. ha leído y comprendido este cuestionario y fueron aclaradas todas sus dudas?', false),
  ('B','¿Desayunaste hoy?',                                        false),
  ('B','¿Dormiste al menos 6 horas anoche?',                       false),
  ('B','¿Consumiste alcohol en las últimas 12 horas?',             true),
  ('B','¿Tenés fiebre, gripe o alguna infección en este momento?', true),
  ('B','¿Estás tomando alguna medicación actualmente?',            true)
) AS p(parte, enunciado, excluye)
WHERE NOT EXISTS (SELECT 1 FROM pregunta q WHERE q.enunciado = p.enunciado);

-- ---------- Personal de turno ----------
-- `cita.id_personal` es NOT NULL: toda cita nombra a quien atiende. Cuando
-- el donante reserva desde el portal todavía no se sabe quién va a ser, así
-- que queda esta cuenta de servicio y el panel la reemplaza por la persona
-- real en el mostrador.
--
-- No puede iniciar sesión: no tiene contraseña ni correo cargado. Los
-- campos personales son de relleno porque el esquema los exige; no
-- describen a nadie.
INSERT INTO usuario (documento, nombre, apellido, fecha_nacimiento, genero,
                     contrasena, consentimiento_privacidad, estado,
                     cuenta_suprimida, fecha_alta)
SELECT '00000000', 'Personal', 'de turno', DATE '2000-01-01', 'Femenino',
       NULL, true, true, false, now()
WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE documento = '00000000');

INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
  FROM usuario u, rol r
 WHERE u.documento = '00000000'
   AND r.codigo = 'ENFERMERIA'
   AND NOT EXISTS (
       SELECT 1 FROM usuario_rol ur
        WHERE ur.id_usuario = u.id_usuario AND ur.id_rol = r.id_rol);

-- ---------- Franjas horarias ----------
-- Lunes a viernes 07:00-15:00 y sábados 07:00-11:00, en bloques de 30 minutos.
-- cupo_atencion = 4 donantes por franja, cupo_consejeria = 2.
INSERT INTO horario_disponible (dia_semana, hora_inicio, hora_fin,
                                cupo_atencion, cupo_consejeria, disponible)
SELECT d.dia,
       (time '07:00' + (n * interval '30 minutes'))::time,
       (time '07:30' + (n * interval '30 minutes'))::time,
       4, 2, true
  FROM (VALUES ('Lunes',16),('Martes',16),('Miercoles',16),
               ('Jueves',16),('Viernes',16),('Sabado',8)) AS d(dia, bloques),
       LATERAL generate_series(0, d.bloques - 1) AS n
 WHERE NOT EXISTS (
     SELECT 1 FROM horario_disponible h
      WHERE h.dia_semana  = d.dia
        AND h.hora_inicio = (time '07:00' + (n * interval '30 minutes'))::time
 );

-- ---------- Contenido del portal ----------
INSERT INTO contenido_portal (titulo, cuerpo, vigente)
SELECT * FROM (VALUES
  ('Requisitos para donar',
   'Tener entre 18 y 65 años, pesar 50 kg o más, encontrarse en buen estado de salud y presentar documento de identidad vigente.',
   true),
  ('Horarios de atención',
   'Lunes a viernes de 07:00 a 15:00. Sábados de 07:00 a 11:00. Domingos y feriados cerrado.',
   true),
  ('Cómo es el proceso',
   'Registro y control de signos vitales, cuestionario de salud, extracción de 10 a 15 minutos y una zona de recuperación con refrigerio.',
   true)
) AS c(titulo, cuerpo, vigente)
WHERE NOT EXISTS (SELECT 1 FROM contenido_portal p WHERE p.titulo = c.titulo);

COMMIT;

-- ---------- Verificación ----------
-- Tiene que devolver: 4, 8, 27, 5, 12, 41, 88, 3
SELECT
  (SELECT count(*) FROM rol)                   AS roles,
  (SELECT count(*) FROM tipo_sangre)           AS tipos_sangre,
  (SELECT count(*) FROM compatibilidad_abo_rh) AS compatibilidades,
  (SELECT count(*) FROM tipo_medicion)         AS mediciones,
  (SELECT count(*) FROM diferimiento)          AS diferimientos,
  (SELECT count(*) FROM pregunta)              AS preguntas,
  (SELECT count(*) FROM horario_disponible)    AS franjas,
  (SELECT count(*) FROM contenido_portal)      AS contenidos;
