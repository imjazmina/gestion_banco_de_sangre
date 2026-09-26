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
-- Parte A: antecedentes estables, los responde el donante al agendar.
-- Parte B: condiciones del día, las carga el personal en el check-in.
-- preselecciona_exclusion = true marca las preguntas cuyo "sí" sugiere
-- diferimiento; la decisión final la toma el personal, no el sistema.
INSERT INTO pregunta (parte, enunciado, preselecciona_exclusion)
SELECT * FROM (VALUES
  ('A','¿Te encontrás en buen estado de salud general?',                                false),
  ('A','¿Pesás 50 kg o más?',                                                           false),
  ('A','¿Tuviste hepatitis B o C, VIH, sífilis o Chagas?',                              true),
  ('A','¿Recibiste una transfusión de sangre en el último año?',                        true),
  ('A','¿Te realizaron alguna cirugía o procedimiento invasivo en los últimos 6 meses?', true),
  ('A','¿Te hiciste un tatuaje, piercing o acupuntura en los últimos 4 meses?',          true),
  ('A','¿Estás embarazada o en período de lactancia?',                                   true),
  ('A','¿Viajaste a una zona endémica en los últimos 3 meses?',                          true),
  ('B','¿Desayunaste hoy?',                                                              false),
  ('B','¿Dormiste al menos 6 horas anoche?',                                             false),
  ('B','¿Consumiste alcohol en las últimas 12 horas?',                                   true),
  ('B','¿Tenés fiebre, gripe o alguna infección en este momento?',                       true),
  ('B','¿Estás tomando alguna medicación actualmente?',                                  true)
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
-- Tiene que devolver: 4, 8, 27, 5, 12, 13, 88, 3
SELECT
  (SELECT count(*) FROM rol)                   AS roles,
  (SELECT count(*) FROM tipo_sangre)           AS tipos_sangre,
  (SELECT count(*) FROM compatibilidad_abo_rh) AS compatibilidades,
  (SELECT count(*) FROM tipo_medicion)         AS mediciones,
  (SELECT count(*) FROM diferimiento)          AS diferimientos,
  (SELECT count(*) FROM pregunta)              AS preguntas,
  (SELECT count(*) FROM horario_disponible)    AS franjas,
  (SELECT count(*) FROM contenido_portal)      AS contenidos;
