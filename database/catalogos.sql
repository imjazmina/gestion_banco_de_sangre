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
-- Parte A: el cuestionario oficial del banco de sangre, 36 preguntas en tres
-- bloques. Lo responde el donante antes de presentarse; el portal se lo
-- manda por correo unas horas antes de su cita.
--
-- Parte B: condiciones del día, las carga el personal en el check-in.
--
-- alerta_si dice cuál de las dos respuestas tiene que mirar el personal.
-- No siempre es el "sí": en "¿Se siente bien?" lo que preocupa es el "no".
-- El sistema marca, no decide: la aptitud la determina el personal de salud.
--
-- Las columnas seccion, orden, alerta_si, pide_detalle, etiqueta_detalle,
-- nota y activa las agrega la migración 004. Si este archivo falla diciendo
-- que no existe alguna de ellas, falta correr:  python database/migrar.py

INSERT INTO pregunta (parte, orden, seccion, enunciado, alerta_si,
                      preselecciona_exclusion, pide_detalle, etiqueta_detalle, nota)
SELECT * FROM (VALUES
  ('A', 1, 'En la actualidad', '¿Se siente Ud. bien y goza de buena salud?', 'No', false, false, NULL, NULL),
  ('A', 2, 'En la actualidad', '¿Padece de presión alta o baja?', 'Si', true, false, NULL, NULL),
  ('A', 3, 'En la actualidad', '¿Está tomando alguna medicación?', 'Si', true, true, '¿Cuál y por qué?', NULL),
  ('A', 4, 'En la actualidad', '¿Ha descansado o comido bien las últimas 24 horas?', 'No', false, false, NULL, NULL),
  ('A', 5, 'En la actualidad', '¿Ha tomado aspirina los últimos 5 días?', 'Si', true, false, NULL, 'Se toma en cuenta solo para la donación de plaquetas.'),
  ('A', 6, 'En la actualidad', '¿Tuvo en la última semana gripe, estado febril, diarrea o tratamiento odontológico?', 'Si', true, false, NULL, NULL),
  ('A', 7, 'En la actualidad', '¿Recibió dinero para realizar esta donación?', 'Si', true, false, NULL, NULL),
  ('A', 8, 'En la actualidad', '¿Sabe que el portador del virus VIH/SIDA puede contagiar estando aparentemente sano?', 'No', false, false, NULL, NULL),
  ('A', 9, 'En la actualidad', '¿Usted dona solamente para que le realicen los análisis del VIH/SIDA?', 'Si', true, false, NULL, NULL),
  ('A', 10, 'Antecedentes personales', '¿Alguna vez ha donado sangre, plaquetas o plasma?', NULL, false, true, '¿Dónde y cuándo?', NULL),
  ('A', 11, 'Antecedentes personales', '¿Alguna vez ha sido rechazado como donante?', 'Si', true, false, NULL, NULL),
  ('A', 12, 'Antecedentes personales', '¿Fue llamado después de una donación con respecto a resultados de sus análisis?', 'Si', true, false, NULL, NULL),
  ('A', 13, 'Antecedentes personales', '¿Tuvo angina (dolor) de pecho, infarto, enfermedades del corazón o pulmón?', 'Si', true, false, NULL, NULL),
  ('A', 14, 'Antecedentes personales', '¿Tuvo cáncer, enfermedades autoinmunes, hipertiroidismo, úlcera, psoriasis, convulsiones, desmayos, trastornos neurológicos o diabetes?', 'Si', true, false, NULL, NULL),
  ('A', 15, 'Antecedentes personales', '¿Tuvo enfermedades de la sangre o hemorragias?', 'Si', true, false, NULL, NULL),
  ('A', 16, 'Antecedentes personales', '¿Tuvo ictericia (piel amarilla), hepatitis o análisis positivo de hepatitis?', 'Si', true, false, NULL, NULL),
  ('A', 17, 'Antecedentes personales', '¿Tuvo enfermedad de Chagas, leishmaniasis, tuberculosis, mononucleosis, paludismo, dengue o análisis positivo para las mismas?', 'Si', true, false, NULL, NULL),
  ('A', 18, 'Antecedentes personales', '¿Ha recibido hormonas de crecimiento de origen humano?', 'Si', true, false, NULL, NULL),
  ('A', 19, 'Antecedentes personales', '¿Ha tenido sífilis, gonorrea, tratamiento o análisis positivo para alguna enfermedad de transmisión sexual (VDRL)?', 'Si', true, false, NULL, NULL),
  ('A', 20, 'Antecedentes personales', '¿Ha mantenido relaciones sexuales con alguna persona que haya tenido alguna enfermedad citada en la pregunta anterior?', 'Si', true, false, NULL, NULL),
  ('A', 21, 'En los ultimos 12 meses', '¿Ha recibido tratamiento de acupuntura, tatuaje, colocación de aros, piercing o accidente de punción?', 'Si', true, false, NULL, NULL),
  ('A', 22, 'En los ultimos 12 meses', '¿Estuvo bajo tratamiento antirrábico o en exposición a un animal rabioso?', 'Si', true, false, NULL, NULL),
  ('A', 23, 'En los ultimos 12 meses', '¿Estuvo bajo tratamiento médico?', 'Si', true, false, NULL, NULL),
  ('A', 24, 'En los ultimos 12 meses', '¿Sufrió algún tipo de cirugía?', 'Si', true, false, NULL, NULL),
  ('A', 25, 'En los ultimos 12 meses', '¿Estuvo detenido por más de 72 horas en una comisaría o institución carcelaria?', 'Si', true, false, NULL, NULL),
  ('A', 26, 'En los ultimos 12 meses', '¿Usted fue transfundido con algún componente sanguíneo o factor de coagulación, o recibió injerto y/o trasplante de órgano?', 'Si', true, false, NULL, NULL),
  ('A', 27, 'En los ultimos 12 meses', '¿Mantuvo relaciones sexuales con personas con VIH/SIDA o hepatitis, o con análisis positivo para las mismas?', 'Si', true, false, NULL, NULL),
  ('A', 28, 'En los ultimos 12 meses', '¿Mantuvo relaciones sexuales con personas que hayan sido transfundidas y/o hayan recibido injerto o trasplante de tejido?', 'Si', true, false, NULL, NULL),
  ('A', 29, 'En los ultimos 12 meses', '¿Pagó o recibió dinero y/o droga a cambio de sexo?', 'Si', true, false, NULL, NULL),
  ('A', 30, 'En los ultimos 12 meses', '¿Mantuvo relaciones sexuales con personas comprendidas en los puntos 21 y 22?', 'Si', true, false, NULL, NULL),
  ('A', 31, 'En los ultimos 12 meses', '¿Mantuvo relaciones sexuales ocasionales sin protección?', 'Si', true, false, NULL, NULL),
  ('A', 32, 'En los ultimos 12 meses', '¿Tuvo relaciones sexuales vía anal?', 'Si', true, false, NULL, NULL),
  ('A', 33, 'En los ultimos 12 meses', '¿Ha recibido vacunas o inmunización?', 'Si', true, true, '¿Cuáles?', NULL),
  ('A', 34, 'En los ultimos 12 meses', '¿Está o estuvo embarazada o se encuentra en período de lactancia?', 'Si', true, false, NULL, NULL),
  ('A', 35, 'En los ultimos 12 meses', 'Si ha estado fuera del país, ¿se ha sentido enfermo/a días previos o posteriores a su regreso?', 'Si', true, false, NULL, NULL),
  ('A', 36, 'En los ultimos 12 meses', '¿Ud. ha leído y comprendido este cuestionario y fueron aclaradas todas sus dudas?', 'No', false, false, NULL, NULL)
) AS p(parte, orden, seccion, enunciado, alerta_si, excluye, pide_detalle, etiqueta_detalle, nota)
WHERE NOT EXISTS (SELECT 1 FROM pregunta q WHERE q.enunciado = p.enunciado);

-- Parte B, del check-in presencial.
INSERT INTO pregunta (parte, enunciado, preselecciona_exclusion)
SELECT * FROM (VALUES
  ('B','¿Desayunaste hoy?',                                       false),
  ('B','¿Dormiste al menos 6 horas anoche?',                      false),
  ('B','¿Consumiste alcohol en las últimas 12 horas?',            true),
  ('B','¿Tenés fiebre, gripe o alguna infección en este momento?', true),
  ('B','¿Estás tomando alguna medicación actualmente?',            true)
) AS p(parte, enunciado, excluye)
WHERE NOT EXISTS (SELECT 1 FROM pregunta q WHERE q.enunciado = p.enunciado);

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
-- Tiene que devolver: 4, 8, 27, 5, 12, 49, 88, 3
SELECT
  (SELECT count(*) FROM rol)                   AS roles,
  (SELECT count(*) FROM tipo_sangre)           AS tipos_sangre,
  (SELECT count(*) FROM compatibilidad_abo_rh) AS compatibilidades,
  (SELECT count(*) FROM tipo_medicion)         AS mediciones,
  (SELECT count(*) FROM diferimiento)          AS diferimientos,
  (SELECT count(*) FROM pregunta)              AS preguntas,
  (SELECT count(*) FROM horario_disponible)    AS franjas,
  (SELECT count(*) FROM contenido_portal)      AS contenidos;
