-- ============================================================================
--  catalogos.sql — Catálogos fijos y datos de la maqueta HRL.
--
--  schema.sql crea la estructura; este script la llena.
--  Idempotente: documento, códigos de unidad y enunciados evitan duplicados.
--
--  Cómo correrlo (pgAdmin): Query Tool sobre gestion_donantes → pegar → Ejecutar.
--
--  Decisiones de la maqueta (2026-09-10):
--  * Diagnóstico se guarda como Reposicion.
--  * Totales históricos de donantes se completan con citas sintéticas.
--  * Causa «Otro» de diferimientos no se carga.
--  * Pacientes con CI repetido: 80000001 Pedro, 80000002 Rosa, 80000003 Fulgencio.
--  * Permanente (p. ej. VIH 1/2): dias_rehabilitacion y fecha_fin nulos.
--    No existe la causa «Criterio permanente de exclusión».
--  * Temporal: fecha_fin la calcula el trigger (fecha_inicio + días del catálogo).
--  * Diferimiento externo: solo institución, sin cita (no se puede continuar).
--  * Extracción de compatibilidad: donante del padrón, no el paciente.
--  * Próximo a vencer: fecha_vencimiento entre 2026-09-11 y 2026-10-10.
-- ============================================================================

BEGIN;

-- ---------- Roles ----------
INSERT INTO rol (codigo, nombre) VALUES
  ('DONANTE',    'Donante'),
  ('ENFERMERIA', 'Enfermería'),
  ('JEFATURA',   'Jefatura')
ON CONFLICT (codigo) DO NOTHING;

-- ---------- Tipos de sangre ----------
INSERT INTO tipo_sangre (grupo, factor) VALUES
  ('O','-'), ('O','+'), ('A','-'), ('A','+'),
  ('B','-'), ('B','+'), ('AB','-'), ('AB','+')
ON CONFLICT (grupo, factor) DO NOTHING;

-- ---------- Compatibilidad donante -> receptor ----------
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

-- ---------- Tipos de medición ----------
INSERT INTO tipo_medicion (codigo, nombre, unidad, valor_minimo, valor_maximo) VALUES
  ('TEMPERATURA', 'Temperatura corporal', '°C',   35.5, 37.5),
  ('PESO',        'Peso',                 'kg',   50,   250),
  ('PAS',         'Presión sistólica',    'mmHg', 90,   160),
  ('PAD',         'Presión diastólica',   'mmHg', 60,   100),
  ('HB',          'Hemoglobina',          'g/dL', 12.5, 20)
ON CONFLICT (codigo) DO NOTHING;

-- ---------- Catálogo de diferimientos ----------
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
  ('VIH 1/2',                           'Permanente',  NULL),
  ('HBsAg (Hepatitis B)',               'Permanente',  NULL),
  ('Anti-HCV (Hepatitis C)',            'Permanente',  NULL),
  ('VDRL (Sífilis)',                    'Permanente',  NULL),
  ('Chagas (T. cruzi)',                  'Permanente',  NULL),
  ('HTLV I/II',                          'Permanente',  NULL),
  ('Anti-HBc (Hepatitis B)',            'Permanente',  NULL),
  ('HBsAg(Hepatitis B)',                 'Permanente',  NULL),
  ('CMV',                                'Permanente',  NULL),
  ('Anti-HCV(Hepatitis C)',              'Permanente',  NULL)
ON CONFLICT (nombre) DO NOTHING;

-- ---------- Cuestionario ----------
INSERT INTO pregunta (parte, enunciado, preselecciona_exclusion)
SELECT * FROM (VALUES
  ('A', '¿Padece de presión alta o baja?', true),
  ('A', '¿Tuvo en la última semana gripe, estado febril, diarrea o tratamiento odontológico?', true),
  ('A', '¿Sabe que el portador del virus VIH/SIDA puede contagiar estando aparentemente sano?', true),
  ('A', '¿Usted dona solamente para que le realicen los análisis del VIH/SIDA?', true),

  ('A', '¿Alguna vez ha donado sangre, plaquetas o plasma?', true), 
  ('A', '¿Donde y cuando?', true),
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
  ('A', '¿Mantuvo relaciones sexuales con personas comprendidas en los puntos anteriores?', true),
  ('A', '¿Estuvo bajo tratamiento médico?', true),
  ('A', '¿Sufrió algún tipo de cirugía?', true),
  ('A', '¿Estuvo detenido por más de 72 horas en una comisaría o institución carcelaria?', true),
  ('A', '¿Usted fue transfundido con algún componente sanguíneo o factor de coagulación, o recibió injerto y/o trasplante de órgano?', true),
  ('A', '¿Mantuvo relaciones sexuales con personas con VIH/SIDA o hepatitis, o con análisis positivo para las mismas?', true),
  ('A', '¿Mantuvo relaciones sexuales con personas que hayan sido transfundidas y/o hayan recibido injerto o trasplante de tejido?', true),
  ('A', '¿Pagó o recibió dinero y/o droga a cambio de sexo?', true),
  ('A', '¿Mantuvo relaciones sexuales ocasionales sin protección?', true),
  ('A', '¿Tuvo relaciones sexuales vía anal?', true),
  ('A', '¿Ha recibido vacunas o inmunización?', true),
  ('A', '¿Cuales?', true),
  ('A', '¿Está o estuvo embarazada o se encuentra en período de lactancia?', true),
  ('A', 'Si ha estado fuera del país, ¿se ha sentido enfermo/a días previos o posteriores a su regreso?', true),
  ('A', '¿Ud. ha leído y comprendido este cuestionario y fueron aclaradas todas sus dudas?', true),
  ('B', '¿Se siente Ud. bien y goza de buena salud?', true),
  ('B','¿Desayunaste hoy?',                                        true),
  ('B','¿Ha descansado o comido bien las últimas 24 horas?',       true),
  ('B','¿Consumiste alcohol en las últimas 12 horas?',             true),
  ('B','¿Estás tomando alguna medicación actualmente?',            true),
  ('B', '¿Por que?', true),
  ('B','¿Ha tomado aspirina los últimos 5 días?',                 true),
  ('B', '¿Recibió dinero para realizar esta donación?', true)
) AS p(parte, enunciado, excluye)
WHERE NOT EXISTS (SELECT 1 FROM pregunta q WHERE q.enunciado = p.enunciado);

-- ---------- Personal de turno ----------
INSERT INTO usuario (documento, nombre, apellido, fecha_nacimiento, genero,
                     contrasena, consentimiento_privacidad, estado,
                     cuenta_suprimida, fecha_alta)
SELECT '00000000', 'Personal', 'de turno', DATE '2000-01-01', 'Femenino',
       NULL, true, true, false, timestamp '2020-01-01 08:00'
WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE documento = '00000000');

INSERT INTO perfil_personal (id_usuario, registro_profesional,
                             correo_institucional, fecha_alta_servicio)
SELECT u.id_usuario, 'TURNO-00000000', 'turno@hrl.local', DATE '2000-01-01'
  FROM usuario u
 WHERE u.documento = '00000000'
   AND NOT EXISTS (
       SELECT 1 FROM perfil_personal p WHERE p.id_usuario = u.id_usuario);

INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
  FROM usuario u, rol r
 WHERE u.documento = '00000000'
   AND r.codigo = 'ENFERMERIA'
   AND NOT EXISTS (
       SELECT 1 FROM usuario_rol ur
        WHERE ur.id_usuario = u.id_usuario AND ur.id_rol = r.id_rol);

-- ---------- Enfermería y jefatura ----------
INSERT INTO usuario (documento, nombre, apellido, fecha_nacimiento, genero,
                     contrasena, consentimiento_privacidad, estado,
                     cuenta_suprimida, fecha_alta)
SELECT '10000001', 'María', 'Recalde', DATE '1988-04-12', 'Femenino',
       '$2b$12$tywo9SOoAO7h2RdyK549pOQG91A7HbPik7i28IllrBfFOhNf2S25u',
       true, true, false, timestamp '2020-03-01 08:00'
WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE documento = '10000001');

INSERT INTO usuario (documento, nombre, apellido, fecha_nacimiento, genero,
                     contrasena, consentimiento_privacidad, estado,
                     cuenta_suprimida, fecha_alta)
SELECT '10000002', 'Jorge', 'Fernández', DATE '1976-11-03', 'Masculino',
       '$2b$12$tywo9SOoAO7h2RdyK549pOQG91A7HbPik7i28IllrBfFOhNf2S25u',
       true, true, false, timestamp '2018-06-01 08:00'
WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE documento = '10000002');

INSERT INTO perfil_personal (id_usuario, registro_profesional,
                             correo_institucional, fecha_alta_servicio)
SELECT u.id_usuario, 'ENF-10000001', 'lic@hrl.gov.com', DATE '2020-03-01'
  FROM usuario u
 WHERE u.documento = '10000001'
   AND NOT EXISTS (
       SELECT 1 FROM perfil_personal p WHERE p.id_usuario = u.id_usuario);

INSERT INTO perfil_personal (id_usuario, registro_profesional,
                             correo_institucional, fecha_alta_servicio)
SELECT u.id_usuario, 'JEF-10000002', 'jef@hrl.gov.com', DATE '2018-06-01'
  FROM usuario u
 WHERE u.documento = '10000002'
   AND NOT EXISTS (
       SELECT 1 FROM perfil_personal p WHERE p.id_usuario = u.id_usuario);

INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
  FROM usuario u, rol r
 WHERE u.documento = '10000001' AND r.codigo = 'ENFERMERIA'
   AND NOT EXISTS (
       SELECT 1 FROM usuario_rol ur
        WHERE ur.id_usuario = u.id_usuario AND ur.id_rol = r.id_rol);

INSERT INTO usuario_rol (id_usuario, id_rol)
SELECT u.id_usuario, r.id_rol
  FROM usuario u, rol r
 WHERE u.documento = '10000002' AND r.codigo = 'JEFATURA'
   AND NOT EXISTS (
       SELECT 1 FROM usuario_rol ur
        WHERE ur.id_usuario = u.id_usuario AND ur.id_rol = r.id_rol);

-- ---------- Franjas horarias (lunes a viernes) ----------
INSERT INTO horario_disponible (dia_semana, hora_inicio, hora_fin,
                                cupo_atencion, cupo_consejeria, disponible)
SELECT d.dia,
       (time '07:00' + (n * interval '30 minutes'))::time,
       (time '07:30' + (n * interval '30 minutes'))::time,
       4, 2, true
  FROM (VALUES ('Lunes',16),('Martes',16),('Miercoles',16),
               ('Jueves',16),('Viernes',16)) AS d(dia, bloques),
       LATERAL generate_series(0, d.bloques - 1) AS n
 WHERE NOT EXISTS (
     SELECT 1 FROM horario_disponible h
      WHERE h.dia_semana  = d.dia
        AND h.hora_inicio = (time '07:00' + (n * interval '30 minutes'))::time
 );

-- Fin de semana: no se ofrece en la agenda (disponible = false).
-- Ancla citas históricas de la maqueta que caen sábado o domingo.
INSERT INTO horario_disponible (dia_semana, hora_inicio, hora_fin,
                                cupo_atencion, cupo_consejeria, disponible)
SELECT d.dia,
       (time '07:00' + (n * interval '30 minutes'))::time,
       (time '07:30' + (n * interval '30 minutes'))::time,
       4, 2, false
  FROM (VALUES ('Sabado',16),('Domingo',16)) AS d(dia, bloques),
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

-- ---------- Funciones auxiliares de la maqueta (se eliminan al final) ----------
CREATE OR REPLACE FUNCTION maqueta_id_tipo(p_etiqueta text)
RETURNS integer
LANGUAGE sql
STABLE
AS $$
  SELECT id_tipo_sangre FROM tipo_sangre
   WHERE rtrim(grupo) || factor = p_etiqueta
   LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION maqueta_id_horario(p_fecha date, p_hora time)
RETURNS integer
LANGUAGE sql
STABLE
AS $$
  SELECT h.id_horario
    FROM horario_disponible h
   WHERE h.dia_semana = (ARRAY['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo'])
                          [EXTRACT(ISODOW FROM p_fecha)::int]
     AND h.hora_inicio = p_hora
   LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION maqueta_reserva(p_fecha date)
RETURNS timestamp
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT (p_fecha - 1)::timestamp + time '08:00';
$$;

CREATE OR REPLACE FUNCTION maqueta_usuario(
  p_doc varchar, p_nom varchar, p_ape varchar, p_nac date, p_gen varchar,
  p_tel varchar, p_mail varchar, p_grupo varchar
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_id integer;
BEGIN
  SELECT id_usuario INTO v_id FROM usuario WHERE documento = p_doc;
  IF v_id IS NULL THEN
    INSERT INTO usuario (documento, nombre, apellido, fecha_nacimiento, genero,
                         contrasena, consentimiento_privacidad, estado,
                         cuenta_suprimida, fecha_alta, id_tipo_sangre)
    VALUES (p_doc, p_nom, p_ape, p_nac, p_gen, NULL, true, true, false,
            timestamp '2023-01-01 08:00', maqueta_id_tipo(p_grupo))
    RETURNING id_usuario INTO v_id;
  END IF;
  IF p_tel IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM telefono t WHERE t.id_usuario = v_id AND t.numero = p_tel) THEN
    INSERT INTO telefono (id_usuario, numero, es_principal)
    SELECT v_id, p_tel, NOT EXISTS (
      SELECT 1 FROM telefono t WHERE t.id_usuario = v_id AND t.es_principal);
  END IF;
  IF p_mail IS NOT NULL AND NOT EXISTS (SELECT 1 FROM correo c WHERE c.direccion = p_mail) THEN
    INSERT INTO correo (id_usuario, direccion, es_principal)
    SELECT v_id, p_mail, NOT EXISTS (
      SELECT 1 FROM correo c WHERE c.id_usuario = v_id AND c.es_principal);
  END IF;
  INSERT INTO usuario_rol (id_usuario, id_rol)
  SELECT v_id, r.id_rol FROM rol r
   WHERE r.codigo = 'DONANTE'
     AND NOT EXISTS (
       SELECT 1 FROM usuario_rol ur WHERE ur.id_usuario = v_id AND ur.id_rol = r.id_rol);
  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION maqueta_cita(
  p_doc varchar, p_tipo varchar, p_fecha date, p_hora time, p_estado varchar,
  p_sol_doc varchar, p_personal varchar
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_id integer;
  v_user integer;
  v_pers integer;
  v_hor integer;
  v_sol integer;
  v_res timestamp;
BEGIN
  SELECT id_usuario INTO v_user FROM usuario WHERE documento = p_doc;
  SELECT id_usuario INTO v_pers FROM usuario WHERE documento = COALESCE(p_personal, '00000000');
  v_hor := maqueta_id_horario(p_fecha, p_hora);
  v_res := maqueta_reserva(p_fecha);
  IF v_user IS NULL OR v_pers IS NULL OR v_hor IS NULL THEN
    RAISE EXCEPTION 'cita: faltan usuario/personal/horario % % %', p_doc, p_fecha, p_hora;
  END IF;
  IF p_sol_doc IS NOT NULL THEN
    SELECT s.id_solicitud INTO v_sol
      FROM solicitud s
      JOIN usuario u ON u.id_usuario = s.id_solicitante
     WHERE u.documento = p_sol_doc
     ORDER BY s.id_solicitud
     LIMIT 1;
  END IF;
  SELECT c.id_cita INTO v_id
    FROM cita c
   WHERE c.id_usuario = v_user
     AND c.fecha_hora_creacion = v_res
     AND c.id_horario = v_hor
   LIMIT 1;
  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;
  INSERT INTO cita (tipo_cita, id_usuario, id_solicitud, id_personal, id_horario,
                    fecha_hora_creacion, estado)
  VALUES (p_tipo, v_user, v_sol, v_pers, v_hor, v_res, p_estado)
  RETURNING id_cita INTO v_id;
  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION maqueta_medicion(
  p_cita integer, p_codigo varchar, p_valor numeric, p_fecha timestamp
) RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_pers integer;
  v_tipo integer;
BEGIN
  IF EXISTS (SELECT 1 FROM medicion m JOIN tipo_medicion t ON t.id_tipo_medicion = m.id_tipo_medicion
              WHERE m.id_cita = p_cita AND t.codigo = p_codigo) THEN
    RETURN;
  END IF;
  SELECT id_usuario INTO v_pers FROM usuario WHERE documento = '10000001';
  SELECT id_tipo_medicion INTO v_tipo FROM tipo_medicion WHERE codigo = p_codigo;
  INSERT INTO medicion (id_cita, id_personal, id_tipo_medicion, valor, apto, fecha)
  VALUES (p_cita, v_pers, v_tipo, p_valor, true, p_fecha);
END;
$$;

CREATE OR REPLACE FUNCTION maqueta_diferimiento(
  p_doc varchar, p_causa varchar, p_cita integer, p_origen varchar,
  p_institucion varchar, p_inicio date, p_fin date
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_id integer;
  v_don integer;
  v_dif integer;
  v_pers integer;
BEGIN
  SELECT id_usuario INTO v_don FROM usuario WHERE documento = p_doc;
  SELECT id_diferimiento INTO v_dif FROM diferimiento WHERE nombre = p_causa;
  SELECT id_usuario INTO v_pers FROM usuario WHERE documento = '10000001';
  SELECT r.id_registro INTO v_id
    FROM registro_diferimiento r
   WHERE r.id_donante = v_don
     AND r.id_diferimiento = v_dif
     AND r.fecha_inicio = p_inicio
   LIMIT 1;
  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;
  INSERT INTO registro_diferimiento (
      id_donante, id_diferimiento, id_cita, id_personal, origen,
      institucion_diagnostico, fecha_inicio, fecha_fin)
  VALUES (v_don, v_dif, p_cita, v_pers, p_origen, p_institucion, p_inicio, p_fin)
  RETURNING id_registro INTO v_id;
  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION maqueta_donacion(
  p_doc varchar, p_tipo varchar, p_fecha date, p_hora time,
  p_codigo varchar, p_grupo varchar, p_resultado varchar,
  p_estado varchar, p_vto date, p_obs text, p_sol_doc varchar
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_cita integer;
  v_ext integer;
  v_uni integer;
  v_pers integer;
  v_don integer;
  v_tipo integer;
  v_sol integer;
  v_momento timestamp;
BEGIN
  IF EXISTS (SELECT 1 FROM unidad WHERE codigo = p_codigo) THEN
    SELECT id_unidad INTO v_uni FROM unidad WHERE codigo = p_codigo;
    RETURN v_uni;
  END IF;
  v_cita := maqueta_cita(p_doc, p_tipo, p_fecha, p_hora, 'Completada', p_sol_doc, '10000001');
  SELECT id_usuario INTO v_pers FROM usuario WHERE documento = '10000001';
  SELECT id_usuario INTO v_don FROM usuario WHERE documento = p_doc;
  v_tipo := maqueta_id_tipo(p_grupo);
  v_momento := p_fecha::timestamp + p_hora;
  IF p_sol_doc IS NOT NULL THEN
    SELECT s.id_solicitud INTO v_sol
      FROM solicitud s JOIN usuario u ON u.id_usuario = s.id_solicitante
     WHERE u.documento = p_sol_doc
     ORDER BY s.id_solicitud LIMIT 1;
  END IF;
  INSERT INTO extraccion (id_cita, id_personal, codigo_unico, fecha, observacion)
  VALUES (v_cita, v_pers, 'EX-' || p_codigo, v_momento, COALESCE(p_obs, 'Extracción sin incidentes.'))
  RETURNING id_extraccion INTO v_ext;
  INSERT INTO unidad (id_extraccion, id_donante, id_solicitud, codigo, id_tipo_sangre,
                      componente, estado, fecha_vencimiento)
  VALUES (v_ext, v_don, v_sol, p_codigo, v_tipo, 'sangre_total', 'Registrada', p_vto)
  RETURNING id_unidad INTO v_uni;
  INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
  VALUES (v_uni, v_pers, 'Registrada', 'En laboratorio', v_momento + interval '20 minutes');
  UPDATE unidad SET estado = 'En laboratorio' WHERE id_unidad = v_uni;
  INSERT INTO resultado_laboratorio (id_unidad, id_tipo_sangre, resultado, fecha)
  VALUES (v_uni, v_tipo, p_resultado, v_momento + interval '1 day');
  IF p_resultado = 'Reactivo' THEN
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, motivo, fecha)
    VALUES (v_uni, v_pers, 'En laboratorio', 'Descartada', 'Resultado reactivo', v_momento + interval '1 day');
    UPDATE unidad SET estado = 'Descartada' WHERE id_unidad = v_uni;
  ELSIF p_estado = 'Utilizada' AND v_sol IS NOT NULL THEN
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
    VALUES (v_uni, v_pers, 'En laboratorio', 'En stock', v_momento + interval '1 day');
    UPDATE unidad SET estado = 'En stock' WHERE id_unidad = v_uni;
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
    VALUES (v_uni, v_pers, 'En stock', 'Asignada', v_momento + interval '2 days');
    UPDATE unidad SET estado = 'Asignada', id_solicitud = v_sol WHERE id_unidad = v_uni;
    INSERT INTO asignacion (id_unidad, id_solicitud, fecha)
    SELECT v_uni, v_sol, v_momento + interval '2 days'
     WHERE NOT EXISTS (SELECT 1 FROM asignacion a WHERE a.id_unidad = v_uni);
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, motivo, fecha)
    VALUES (v_uni, v_pers, 'Asignada', 'Utilizada', 'Urgenci', v_momento + interval '3 days');
    UPDATE unidad SET estado = 'Utilizada' WHERE id_unidad = v_uni;
  ELSIF p_estado = 'Asignada' AND v_sol IS NOT NULL THEN
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
    VALUES (v_uni, v_pers, 'En laboratorio', 'En stock', v_momento + interval '1 day');
    UPDATE unidad SET estado = 'En stock' WHERE id_unidad = v_uni;
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
    VALUES (v_uni, v_pers, 'En stock', 'Asignada', v_momento + interval '2 days');
    UPDATE unidad SET estado = 'Asignada', id_solicitud = v_sol WHERE id_unidad = v_uni;
    INSERT INTO asignacion (id_unidad, id_solicitud, fecha)
    SELECT v_uni, v_sol, v_momento + interval '2 days'
     WHERE NOT EXISTS (SELECT 1 FROM asignacion a WHERE a.id_unidad = v_uni);
  ELSE
    INSERT INTO transicion_estado (id_unidad, id_personal, estado_origen, estado_destino, fecha)
    VALUES (v_uni, v_pers, 'En laboratorio', 'En stock', v_momento + interval '1 day');
    UPDATE unidad SET estado = 'En stock' WHERE id_unidad = v_uni;
  END IF;
  RETURN v_uni;
END;
$$;

CREATE OR REPLACE FUNCTION maqueta_solicitud(
  p_doc varchar, p_medico varchar, p_grupo varchar, p_req integer,
  p_asig integer, p_estado varchar, p_creacion timestamp
) RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  v_id integer;
  v_user integer;
BEGIN
  SELECT id_usuario INTO v_user FROM usuario WHERE documento = p_doc;
  SELECT s.id_solicitud INTO v_id
    FROM solicitud s
   WHERE s.id_solicitante = v_user AND s.fecha_creacion = p_creacion
   LIMIT 1;
  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;
  INSERT INTO solicitud (id_solicitante, medico_tratante, id_tipo_sangre,
                         unidades_requeridas, unidades_asignadas,
                         consentimiento_publicacion, estado, fecha_creacion)
  VALUES (v_user, p_medico, maqueta_id_tipo(p_grupo), p_req, p_asig,
          true, p_estado, p_creacion)
  RETURNING id_solicitud INTO v_id;
  RETURN v_id;
END;
$$;


-- ========== Usuarios nominales y Julieta ==========

SELECT maqueta_usuario('3456789', 'Carlos', 'Benítez Ortiz', DATE '1985-03-15', 'Masculino', '0981456789', 'cbenitez@gmail.com', 'O+');
SELECT maqueta_usuario('4123456', 'María Fernanda', 'Acosta', DATE '1992-07-22', 'Femenino', '0991234567', 'mfacosta@outlook.com', NULL);
SELECT maqueta_usuario('2987654', 'Jorge Luis', 'Gómez Díaz', DATE '1978-11-08', 'Masculino', '0972345678', 'jlgomez@hotmail.com', 'A+');
SELECT maqueta_usuario('5234567', 'Ana Patricia', 'Ríos', DATE '1990-05-30', 'Femenino', '0983567890', 'aprios@gmail.com', NULL);
SELECT maqueta_usuario('3789012', 'Roberto', 'Solís Ramírez', DATE '1982-01-20', 'Masculino', '0994678901', 'rsolisram@gmail.com', NULL);
SELECT maqueta_usuario('4567890', 'Lucía', 'Giménez Paredes', DATE '1995-09-14', 'Femenino', '0985789012', 'lgparedes@gmail.com', NULL);
SELECT maqueta_usuario('2345678', 'Diego', 'Cabrera Núñez', DATE '1988-04-03', 'Masculino', '0971890123', 'dcabrera@yahoo.com', 'B-');
SELECT maqueta_usuario('6123456', 'Valeria', 'Morínigo Flores', DATE '2000-12-25', 'Femenino', '0992901234', 'vmorinigo@gmail.com', NULL);
SELECT maqueta_usuario('1876543', 'Hugo Ramón', 'Aquino', DATE '1975-06-12', 'Masculino', '0981012345', 'hraquino@outlook.com', 'AB+');
SELECT maqueta_usuario('5678901', 'Sandra Beatriz', 'Villalba', DATE '1993-03-08', 'Femenino', '0993123456', 'sbvillalba@gmail.com', NULL);
SELECT maqueta_usuario('7111111', 'Elena', 'Rojas Medina', DATE '1991-02-18', 'Femenino', '0981111111', 'erojas@gmail.com', NULL);
SELECT maqueta_usuario('7222222', 'Pablo', 'Estigarribia López', DATE '1986-10-09', 'Masculino', '0991222222', 'pestigarribia@outlook.com', NULL);
SELECT maqueta_usuario('7333333', 'Silvia', 'Duarte Caballero', DATE '1994-05-27', 'Femenino', '0972333333', 'sduarte@gmail.com', NULL);
SELECT maqueta_usuario('7444444', 'Ramón', 'Ortiz Franco', DATE '1979-08-04', 'Masculino', '0983444444', 'rortiz@hotmail.com', NULL);
SELECT maqueta_usuario('7555555', 'Natalia', 'Pereira Soto', DATE '1989-11-21', 'Femenino', '0994555555', 'npereira@gmail.com', NULL);
SELECT maqueta_usuario('5485567', 'Julieta', 'Rojas', DATE '1996-04-15', 'Femenino', '0985485567', 'jrojas.maqueta@gmail.com', NULL);
SELECT maqueta_usuario('1234567', 'Mirta Elisa', 'Vera de González', DATE '1968-05-02', 'Femenino', '0981234567', 'mvera@gmail.com', 'O+');
SELECT maqueta_usuario('80000001', 'Pedro Antonio', 'Ruiz', DATE '1972-08-19', 'Masculino', '0988000001', 'pruiz.paciente@gmail.com', 'A+');
SELECT maqueta_usuario('80000002', 'Rosa María', 'Duarte', DATE '1975-01-11', 'Femenino', '0988000002', 'rduarte.paciente@gmail.com', 'O+');
SELECT maqueta_usuario('80000003', 'Fulgencio', 'Adorno Benítez', DATE '1969-10-30', 'Masculino', '0988000003', 'fadorno.paciente@gmail.com', 'B+');

-- Pacientes sintéticos de solicitudes de informe

SELECT maqueta_usuario('80000010', 'Paciente', 'Solicitud 01', DATE '1970-01-01', 'Femenino', '097800010', 'paciente10@maqueta.local', 'O+');
SELECT maqueta_usuario('80000011', 'Paciente', 'Solicitud 02', DATE '1970-01-02', 'Masculino', '097800011', 'paciente11@maqueta.local', 'A+');
SELECT maqueta_usuario('80000012', 'Paciente', 'Solicitud 03', DATE '1970-01-03', 'Femenino', '097800012', 'paciente12@maqueta.local', 'B+');
SELECT maqueta_usuario('80000013', 'Paciente', 'Solicitud 04', DATE '1970-01-04', 'Masculino', '097800013', 'paciente13@maqueta.local', 'AB+');
SELECT maqueta_usuario('80000014', 'Paciente', 'Solicitud 05', DATE '1970-01-05', 'Femenino', '097800014', 'paciente14@maqueta.local', 'O-');
SELECT maqueta_usuario('80000015', 'Paciente', 'Solicitud 06', DATE '1970-01-06', 'Masculino', '097800015', 'paciente15@maqueta.local', 'O+');
SELECT maqueta_usuario('80000016', 'Paciente', 'Solicitud 07', DATE '1970-01-07', 'Femenino', '097800016', 'paciente16@maqueta.local', 'A+');
SELECT maqueta_usuario('80000017', 'Paciente', 'Solicitud 08', DATE '1970-01-08', 'Masculino', '097800017', 'paciente17@maqueta.local', 'B+');
SELECT maqueta_usuario('80000018', 'Paciente', 'Solicitud 09', DATE '1970-01-09', 'Femenino', '097800018', 'paciente18@maqueta.local', 'AB+');
SELECT maqueta_usuario('80000019', 'Paciente', 'Solicitud 10', DATE '1970-01-10', 'Masculino', '097800019', 'paciente19@maqueta.local', 'O-');
SELECT maqueta_usuario('80000020', 'Paciente', 'Solicitud 11', DATE '1970-01-11', 'Femenino', '097800020', 'paciente20@maqueta.local', 'O+');
SELECT maqueta_usuario('80000021', 'Paciente', 'Solicitud 12', DATE '1970-01-12', 'Masculino', '097800021', 'paciente21@maqueta.local', 'A+');
SELECT maqueta_usuario('80000022', 'Paciente', 'Solicitud 13', DATE '1970-01-13', 'Femenino', '097800022', 'paciente22@maqueta.local', 'B+');
SELECT maqueta_usuario('80000023', 'Paciente', 'Solicitud 14', DATE '1970-01-14', 'Masculino', '097800023', 'paciente23@maqueta.local', 'AB+');
SELECT maqueta_usuario('80000024', 'Paciente', 'Solicitud 15', DATE '1970-01-15', 'Femenino', '097800024', 'paciente24@maqueta.local', 'O-');
SELECT maqueta_usuario('80000025', 'Paciente', 'Solicitud 16', DATE '1970-01-16', 'Masculino', '097800025', 'paciente25@maqueta.local', 'O+');
SELECT maqueta_usuario('80000026', 'Paciente', 'Solicitud 17', DATE '1970-01-17', 'Femenino', '097800026', 'paciente26@maqueta.local', 'A+');
SELECT maqueta_usuario('80000027', 'Paciente', 'Solicitud 18', DATE '1970-01-18', 'Masculino', '097800027', 'paciente27@maqueta.local', 'B+');
SELECT maqueta_usuario('80000028', 'Paciente', 'Solicitud 19', DATE '1970-01-19', 'Femenino', '097800028', 'paciente28@maqueta.local', 'AB+');
SELECT maqueta_usuario('80000029', 'Paciente', 'Solicitud 20', DATE '1970-01-20', 'Masculino', '097800029', 'paciente29@maqueta.local', 'O-');
SELECT maqueta_usuario('80000030', 'Paciente', 'Solicitud 21', DATE '1970-01-21', 'Femenino', '097800030', 'paciente30@maqueta.local', 'O+');
SELECT maqueta_usuario('80000031', 'Paciente', 'Solicitud 22', DATE '1970-01-22', 'Masculino', '097800031', 'paciente31@maqueta.local', 'A+');
SELECT maqueta_usuario('80000032', 'Paciente', 'Solicitud 23', DATE '1970-01-23', 'Femenino', '097800032', 'paciente32@maqueta.local', 'B+');
SELECT maqueta_usuario('80000033', 'Paciente', 'Solicitud 24', DATE '1970-01-24', 'Masculino', '097800033', 'paciente33@maqueta.local', 'AB+');
SELECT maqueta_usuario('80000034', 'Paciente', 'Solicitud 25', DATE '1970-01-25', 'Femenino', '097800034', 'paciente34@maqueta.local', 'O-');
SELECT maqueta_usuario('80000035', 'Paciente', 'Solicitud 26', DATE '1970-01-26', 'Masculino', '097800035', 'paciente35@maqueta.local', 'O+');
SELECT maqueta_usuario('80000036', 'Paciente', 'Solicitud 27', DATE '1970-01-27', 'Femenino', '097800036', 'paciente36@maqueta.local', 'A+');
SELECT maqueta_usuario('80000037', 'Paciente', 'Solicitud 28', DATE '1970-01-28', 'Masculino', '097800037', 'paciente37@maqueta.local', 'B+');
SELECT maqueta_usuario('80000038', 'Paciente', 'Solicitud 29', DATE '1970-01-01', 'Femenino', '097800038', 'paciente38@maqueta.local', 'AB+');

-- Donantes sintéticos del período y diferimientos

SELECT maqueta_usuario('90000001', 'Donante', 'Periodo 001', DATE '2004-03-01', 'Femenino', '0990000001', 'periodo90000001@maqueta.local', 'O+');
SELECT maqueta_usuario('90000002', 'Donante', 'Periodo 002', DATE '2004-03-02', 'Femenino', '0990000002', 'periodo90000002@maqueta.local', 'O+');
SELECT maqueta_usuario('90000003', 'Donante', 'Periodo 003', DATE '2004-03-03', 'Femenino', '0990000003', 'periodo90000003@maqueta.local', 'O+');
SELECT maqueta_usuario('90000004', 'Donante', 'Periodo 004', DATE '2004-03-04', 'Femenino', '0990000004', 'periodo90000004@maqueta.local', 'O+');
SELECT maqueta_usuario('90000005', 'Donante', 'Periodo 005', DATE '2004-03-05', 'Femenino', '0990000005', 'periodo90000005@maqueta.local', 'O+');
SELECT maqueta_usuario('90000006', 'Donante', 'Periodo 006', DATE '2004-03-06', 'Femenino', '0990000006', 'periodo90000006@maqueta.local', 'O+');
SELECT maqueta_usuario('90000007', 'Donante', 'Periodo 007', DATE '2004-03-07', 'Femenino', '0990000007', 'periodo90000007@maqueta.local', 'O+');
SELECT maqueta_usuario('90000008', 'Donante', 'Periodo 008', DATE '2004-03-08', 'Femenino', '0990000008', 'periodo90000008@maqueta.local', 'O+');
SELECT maqueta_usuario('90000009', 'Donante', 'Periodo 009', DATE '2004-03-09', 'Femenino', '0990000009', 'periodo90000009@maqueta.local', 'O+');
SELECT maqueta_usuario('90000010', 'Donante', 'Periodo 010', DATE '2004-03-10', 'Femenino', '0990000010', 'periodo90000010@maqueta.local', 'O+');
SELECT maqueta_usuario('90000011', 'Donante', 'Periodo 011', DATE '2004-04-20', 'Masculino', '0990000011', 'periodo90000011@maqueta.local', 'O+');
SELECT maqueta_usuario('90000012', 'Donante', 'Periodo 012', DATE '2004-04-21', 'Masculino', '0990000012', 'periodo90000012@maqueta.local', 'O+');
SELECT maqueta_usuario('90000013', 'Donante', 'Periodo 013', DATE '2004-04-22', 'Masculino', '0990000013', 'periodo90000013@maqueta.local', 'O+');
SELECT maqueta_usuario('90000014', 'Donante', 'Periodo 014', DATE '2004-04-23', 'Masculino', '0990000014', 'periodo90000014@maqueta.local', 'O+');
SELECT maqueta_usuario('90000015', 'Donante', 'Periodo 015', DATE '2004-04-24', 'Masculino', '0990000015', 'periodo90000015@maqueta.local', 'O+');
SELECT maqueta_usuario('90000016', 'Donante', 'Periodo 016', DATE '2004-04-25', 'Masculino', '0990000016', 'periodo90000016@maqueta.local', 'O+');
SELECT maqueta_usuario('90000017', 'Donante', 'Periodo 017', DATE '2004-04-26', 'Masculino', '0990000017', 'periodo90000017@maqueta.local', 'O+');
SELECT maqueta_usuario('90000018', 'Donante', 'Periodo 018', DATE '2004-04-27', 'Masculino', '0990000018', 'periodo90000018@maqueta.local', 'O+');
SELECT maqueta_usuario('90000019', 'Donante', 'Periodo 019', DATE '2004-04-28', 'Masculino', '0990000019', 'periodo90000019@maqueta.local', 'O+');
SELECT maqueta_usuario('90000020', 'Donante', 'Periodo 020', DATE '2004-04-29', 'Masculino', '0990000020', 'periodo90000020@maqueta.local', 'O+');
SELECT maqueta_usuario('90000021', 'Donante', 'Periodo 021', DATE '2004-04-30', 'Masculino', '0990000021', 'periodo90000021@maqueta.local', 'O+');
SELECT maqueta_usuario('90000022', 'Donante', 'Periodo 022', DATE '2004-05-01', 'Masculino', '0990000022', 'periodo90000022@maqueta.local', 'O+');
SELECT maqueta_usuario('90000023', 'Donante', 'Periodo 023', DATE '1994-06-10', 'Femenino', '0990000023', 'periodo90000023@maqueta.local', 'O+');
SELECT maqueta_usuario('90000024', 'Donante', 'Periodo 024', DATE '1994-06-11', 'Femenino', '0990000024', 'periodo90000024@maqueta.local', 'O+');
SELECT maqueta_usuario('90000025', 'Donante', 'Periodo 025', DATE '1994-06-12', 'Femenino', '0990000025', 'periodo90000025@maqueta.local', 'O+');
SELECT maqueta_usuario('90000026', 'Donante', 'Periodo 026', DATE '1994-06-13', 'Femenino', '0990000026', 'periodo90000026@maqueta.local', 'A+');
SELECT maqueta_usuario('90000027', 'Donante', 'Periodo 027', DATE '1994-06-14', 'Femenino', '0990000027', 'periodo90000027@maqueta.local', 'A+');
SELECT maqueta_usuario('90000028', 'Donante', 'Periodo 028', DATE '1994-06-15', 'Femenino', '0990000028', 'periodo90000028@maqueta.local', 'A+');
SELECT maqueta_usuario('90000029', 'Donante', 'Periodo 029', DATE '1994-06-16', 'Femenino', '0990000029', 'periodo90000029@maqueta.local', 'A+');
SELECT maqueta_usuario('90000030', 'Donante', 'Periodo 030', DATE '1994-06-17', 'Femenino', '0990000030', 'periodo90000030@maqueta.local', 'A+');
SELECT maqueta_usuario('90000031', 'Donante', 'Periodo 031', DATE '1994-06-18', 'Femenino', '0990000031', 'periodo90000031@maqueta.local', 'A+');
SELECT maqueta_usuario('90000032', 'Donante', 'Periodo 032', DATE '1994-06-19', 'Femenino', '0990000032', 'periodo90000032@maqueta.local', 'A+');
SELECT maqueta_usuario('90000033', 'Donante', 'Periodo 033', DATE '1994-06-20', 'Femenino', '0990000033', 'periodo90000033@maqueta.local', 'A+');
SELECT maqueta_usuario('90000034', 'Donante', 'Periodo 034', DATE '1994-06-21', 'Femenino', '0990000034', 'periodo90000034@maqueta.local', 'A+');
SELECT maqueta_usuario('90000035', 'Donante', 'Periodo 035', DATE '1994-06-22', 'Femenino', '0990000035', 'periodo90000035@maqueta.local', 'A+');
SELECT maqueta_usuario('90000036', 'Donante', 'Periodo 036', DATE '1994-06-23', 'Femenino', '0990000036', 'periodo90000036@maqueta.local', 'B+');
SELECT maqueta_usuario('90000037', 'Donante', 'Periodo 037', DATE '1994-07-30', 'Masculino', '0990000037', 'periodo90000037@maqueta.local', 'B+');
SELECT maqueta_usuario('90000038', 'Donante', 'Periodo 038', DATE '1994-07-31', 'Masculino', '0990000038', 'periodo90000038@maqueta.local', 'B+');
SELECT maqueta_usuario('90000039', 'Donante', 'Periodo 039', DATE '1994-08-01', 'Masculino', '0990000039', 'periodo90000039@maqueta.local', 'B+');
SELECT maqueta_usuario('90000040', 'Donante', 'Periodo 040', DATE '1994-08-02', 'Masculino', '0990000040', 'periodo90000040@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000041', 'Donante', 'Periodo 041', DATE '1994-08-03', 'Masculino', '0990000041', 'periodo90000041@maqueta.local', 'O-');
SELECT maqueta_usuario('90000042', 'Donante', 'Periodo 042', DATE '1994-08-04', 'Masculino', '0990000042', 'periodo90000042@maqueta.local', 'O-');
SELECT maqueta_usuario('90000043', 'Donante', 'Periodo 043', DATE '1994-08-05', 'Masculino', '0990000043', 'periodo90000043@maqueta.local', 'O-');
SELECT maqueta_usuario('90000044', 'Donante', 'Periodo 044', DATE '1994-08-06', 'Masculino', '0990000044', 'periodo90000044@maqueta.local', 'A-');
SELECT maqueta_usuario('90000045', 'Donante', 'Periodo 045', DATE '1994-08-07', 'Masculino', '0990000045', 'periodo90000045@maqueta.local', 'A-');
SELECT maqueta_usuario('90000046', 'Donante', 'Periodo 046', DATE '1994-08-08', 'Masculino', '0990000046', 'periodo90000046@maqueta.local', 'B-');
SELECT maqueta_usuario('90000047', 'Donante', 'Periodo 047', DATE '1994-08-09', 'Masculino', '0990000047', 'periodo90000047@maqueta.local', 'A+');
SELECT maqueta_usuario('90000048', 'Donante', 'Periodo 048', DATE '1994-08-10', 'Masculino', '0990000048', 'periodo90000048@maqueta.local', 'A+');
SELECT maqueta_usuario('90000049', 'Donante', 'Periodo 049', DATE '1994-08-11', 'Masculino', '0990000049', 'periodo90000049@maqueta.local', 'A+');
SELECT maqueta_usuario('90000050', 'Donante', 'Periodo 050', DATE '1994-08-12', 'Masculino', '0990000050', 'periodo90000050@maqueta.local', 'A+');
SELECT maqueta_usuario('90000051', 'Donante', 'Periodo 051', DATE '1994-08-13', 'Masculino', '0990000051', 'periodo90000051@maqueta.local', 'B+');
SELECT maqueta_usuario('90000052', 'Donante', 'Periodo 052', DATE '1994-08-14', 'Masculino', '0990000052', 'periodo90000052@maqueta.local', 'B+');
SELECT maqueta_usuario('90000053', 'Donante', 'Periodo 053', DATE '1994-08-15', 'Masculino', '0990000053', 'periodo90000053@maqueta.local', 'B+');
SELECT maqueta_usuario('90000054', 'Donante', 'Periodo 054', DATE '1984-09-20', 'Femenino', '0990000054', 'periodo90000054@maqueta.local', 'B+');
SELECT maqueta_usuario('90000055', 'Donante', 'Periodo 055', DATE '1984-09-21', 'Femenino', '0990000055', 'periodo90000055@maqueta.local', 'B+');
SELECT maqueta_usuario('90000056', 'Donante', 'Periodo 056', DATE '1984-09-22', 'Femenino', '0990000056', 'periodo90000056@maqueta.local', 'B+');
SELECT maqueta_usuario('90000057', 'Donante', 'Periodo 057', DATE '1984-09-23', 'Femenino', '0990000057', 'periodo90000057@maqueta.local', 'B+');
SELECT maqueta_usuario('90000058', 'Donante', 'Periodo 058', DATE '1984-09-24', 'Femenino', '0990000058', 'periodo90000058@maqueta.local', 'B+');
SELECT maqueta_usuario('90000059', 'Donante', 'Periodo 059', DATE '1984-09-25', 'Femenino', '0990000059', 'periodo90000059@maqueta.local', 'B+');
SELECT maqueta_usuario('90000060', 'Donante', 'Periodo 060', DATE '1984-09-26', 'Femenino', '0990000060', 'periodo90000060@maqueta.local', 'B+');
SELECT maqueta_usuario('90000061', 'Donante', 'Periodo 061', DATE '1984-09-27', 'Femenino', '0990000061', 'periodo90000061@maqueta.local', 'B+');
SELECT maqueta_usuario('90000062', 'Donante', 'Periodo 062', DATE '1984-11-09', 'Masculino', '0990000062', 'periodo90000062@maqueta.local', 'B+');
SELECT maqueta_usuario('90000063', 'Donante', 'Periodo 063', DATE '1984-11-10', 'Masculino', '0990000063', 'periodo90000063@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000064', 'Donante', 'Periodo 064', DATE '1984-11-11', 'Masculino', '0990000064', 'periodo90000064@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000065', 'Donante', 'Periodo 065', DATE '1984-11-12', 'Masculino', '0990000065', 'periodo90000065@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000066', 'Donante', 'Periodo 066', DATE '1984-11-13', 'Masculino', '0990000066', 'periodo90000066@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000067', 'Donante', 'Periodo 067', DATE '1984-11-14', 'Masculino', '0990000067', 'periodo90000067@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000068', 'Donante', 'Periodo 068', DATE '1984-11-15', 'Masculino', '0990000068', 'periodo90000068@maqueta.local', 'AB+');
SELECT maqueta_usuario('90000069', 'Donante', 'Periodo 069', DATE '1984-11-16', 'Masculino', '0990000069', 'periodo90000069@maqueta.local', 'O-');
SELECT maqueta_usuario('90000070', 'Donante', 'Periodo 070', DATE '1984-11-17', 'Masculino', '0990000070', 'periodo90000070@maqueta.local', 'O-');
SELECT maqueta_usuario('90000071', 'Donante', 'Periodo 071', DATE '1984-11-18', 'Masculino', '0990000071', 'periodo90000071@maqueta.local', 'O-');
SELECT maqueta_usuario('90000072', 'Donante', 'Periodo 072', DATE '1984-11-19', 'Masculino', '0990000072', 'periodo90000072@maqueta.local', 'O-');
SELECT maqueta_usuario('90000073', 'Donante', 'Periodo 073', DATE '1974-02-15', 'Femenino', '0990000073', 'periodo90000073@maqueta.local', 'O-');
SELECT maqueta_usuario('90000074', 'Donante', 'Periodo 074', DATE '1974-02-16', 'Femenino', '0990000074', 'periodo90000074@maqueta.local', 'O-');
SELECT maqueta_usuario('90000075', 'Donante', 'Periodo 075', DATE '1974-02-17', 'Femenino', '0990000075', 'periodo90000075@maqueta.local', 'O-');
SELECT maqueta_usuario('90000076', 'Donante', 'Periodo 076', DATE '1974-02-18', 'Femenino', '0990000076', 'periodo90000076@maqueta.local', 'O-');
SELECT maqueta_usuario('90000077', 'Donante', 'Periodo 077', DATE '1974-04-06', 'Masculino', '0990000077', 'periodo90000077@maqueta.local', 'A-');
SELECT maqueta_usuario('90000078', 'Donante', 'Periodo 078', DATE '1974-04-07', 'Masculino', '0990000078', 'periodo90000078@maqueta.local', 'A-');
SELECT maqueta_usuario('90000079', 'Donante', 'Periodo 079', DATE '1974-04-08', 'Masculino', '0990000079', 'periodo90000079@maqueta.local', 'A-');
SELECT maqueta_usuario('90000080', 'Donante', 'Periodo 080', DATE '1974-04-09', 'Masculino', '0990000080', 'periodo90000080@maqueta.local', 'A-');
SELECT maqueta_usuario('90000081', 'Donante', 'Periodo 081', DATE '1974-04-10', 'Masculino', '0990000081', 'periodo90000081@maqueta.local', 'A-');
SELECT maqueta_usuario('90000082', 'Donante', 'Periodo 082', DATE '1974-04-11', 'Masculino', '0990000082', 'periodo90000082@maqueta.local', 'B-');
SELECT maqueta_usuario('90000083', 'Donante', 'Periodo 083', DATE '1964-11-05', 'Femenino', '0990000083', 'periodo90000083@maqueta.local', 'B-');
SELECT maqueta_usuario('90000084', 'Donante', 'Periodo 084', DATE '1964-11-06', 'Femenino', '0990000084', 'periodo90000084@maqueta.local', 'B-');
SELECT maqueta_usuario('90000085', 'Donante', 'Periodo 085', DATE '1964-12-25', 'Masculino', '0990000085', 'periodo90000085@maqueta.local', 'B-');
SELECT maqueta_usuario('90000086', 'Donante', 'Periodo 086', DATE '1964-12-26', 'Masculino', '0990000086', 'periodo90000086@maqueta.local', 'AB-');
SELECT maqueta_usuario('90000201', 'Diferido', 'Temporal 1', DATE '1994-06-13', 'Femenino', '098900201', 'diftemp1@maqueta.local', NULL);
SELECT maqueta_usuario('90000202', 'Diferido', 'Temporal 2', DATE '1994-06-14', 'Masculino', '098900202', 'diftemp2@maqueta.local', NULL);
SELECT maqueta_usuario('90000203', 'Diferido', 'Temporal 3', DATE '1994-06-15', 'Femenino', '098900203', 'diftemp3@maqueta.local', NULL);
SELECT maqueta_usuario('90000204', 'Diferido', 'Temporal 4', DATE '1994-06-16', 'Masculino', '098900204', 'diftemp4@maqueta.local', NULL);
SELECT maqueta_usuario('90000205', 'Diferido', 'Temporal 5', DATE '1994-06-17', 'Femenino', '098900205', 'diftemp5@maqueta.local', NULL);
SELECT maqueta_usuario('90000206', 'Diferido', 'Temporal 6', DATE '1994-06-18', 'Masculino', '098900206', 'diftemp6@maqueta.local', NULL);
SELECT maqueta_usuario('90000207', 'Diferido', 'Temporal 7', DATE '1994-06-19', 'Femenino', '098900207', 'diftemp7@maqueta.local', NULL);
SELECT maqueta_usuario('90000208', 'Diferido', 'Temporal 8', DATE '1994-06-20', 'Masculino', '098900208', 'diftemp8@maqueta.local', NULL);

-- Solicitudes

SELECT maqueta_solicitud('1234567', 'Dr. Ramón Espínola', 'O+', 2, 0, 'Publicada', TIMESTAMP '2026-09-09 10:00');
SELECT maqueta_solicitud('80000001', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-09-08 10:00');
SELECT maqueta_solicitud('80000002', 'Dr. Carlos Mendoza', 'O+', 3, 0, 'Publicada', TIMESTAMP '2026-09-07 10:00');
SELECT maqueta_solicitud('80000003', 'Dra. Patricia Acuña', 'B+', 1, 0, 'Publicada', TIMESTAMP '2026-09-06 10:00');
SELECT maqueta_solicitud('80000010', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-01 09:00');
SELECT maqueta_solicitud('80000011', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-02 09:00');
SELECT maqueta_solicitud('80000012', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-03 09:00');
SELECT maqueta_solicitud('80000013', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-04 09:00');
SELECT maqueta_solicitud('80000014', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-05 09:00');
SELECT maqueta_solicitud('80000015', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-06 09:00');
SELECT maqueta_solicitud('80000016', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-07 09:00');
SELECT maqueta_solicitud('80000017', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-08 09:00');
SELECT maqueta_solicitud('80000018', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-09 09:00');
SELECT maqueta_solicitud('80000019', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-10 09:00');
SELECT maqueta_solicitud('80000020', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-11 09:00');
SELECT maqueta_solicitud('80000021', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-12 09:00');
SELECT maqueta_solicitud('80000022', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-13 09:00');
SELECT maqueta_solicitud('80000023', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-14 09:00');
SELECT maqueta_solicitud('80000024', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-15 09:00');
SELECT maqueta_solicitud('80000025', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-16 09:00');
SELECT maqueta_solicitud('80000026', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-17 09:00');
SELECT maqueta_solicitud('80000027', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-18 09:00');
SELECT maqueta_solicitud('80000028', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-19 09:00');
SELECT maqueta_solicitud('80000029', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-20 09:00');
SELECT maqueta_solicitud('80000030', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-21 09:00');
SELECT maqueta_solicitud('80000031', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-22 09:00');
SELECT maqueta_solicitud('80000032', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-23 09:00');
SELECT maqueta_solicitud('80000033', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-24 09:00');
SELECT maqueta_solicitud('80000034', 'Dra. Liz Montiel', 'O+', 1, 1, 'Completa', TIMESTAMP '2026-08-25 09:00');
SELECT maqueta_solicitud('80000035', 'Dra. Liz Montiel', 'A+', 1, 1, 'Completa', TIMESTAMP '2026-08-26 09:00');
SELECT maqueta_solicitud('80000036', 'Dra. Liz Montiel', 'B+', 1, 1, 'Completa', TIMESTAMP '2026-08-27 09:00');
SELECT maqueta_solicitud('80000037', 'Dr. Carlos Mendoza', 'O+', 2, 0, 'Publicada', TIMESTAMP '2026-09-03 11:00');
SELECT maqueta_solicitud('80000038', 'Dr. Carlos Mendoza', 'O+', 2, 0, 'Publicada', TIMESTAMP '2026-09-04 11:00');

-- Historial visible y sintético de donantes nominales

SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2026-03-12', TIME '07:30', 'UN-2026-0234', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2025-09-08', TIME '07:30', 'UN-2025-1876', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2025-03-20', TIME '07:30', 'UN-2025-0412', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2024-01-15', TIME '07:30', 'UN-2024-0087', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('4123456', 'Donacion altruista', DATE '2025-05-14', TIME '08:00', 'UN-2025-0823', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2026-09-10', TIME '08:30', 'UN-2026-0912', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2026-03-05', TIME '08:30', 'UN-2026-0198', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2025-09-22', TIME '08:30', 'UN-2025-2011', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('5234567', 'Donacion altruista', DATE '2025-08-15', TIME '09:00', 'UN-2025-1432', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3789012', 'Donacion altruista', DATE '2025-12-05', TIME '09:30', 'UN-2025-2345', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3789012', 'Donacion altruista', DATE '2025-06-18', TIME '09:30', 'UN-2025-1087', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2025-07-10', TIME '10:30', 'UN-2025-1234', 'B-', 'Reactivo', 'Descartada', NULL, NULL, NULL);
SELECT maqueta_donacion('6123456', 'Donacion altruista', DATE '2025-10-05', TIME '11:00', 'UN-2025-1789', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2026-06-15', TIME '11:30', 'UN-2026-0623', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2025-12-28', TIME '11:30', 'UN-2025-2567', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('5678901', 'Donacion solidaria', DATE '2025-07-22', TIME '12:00', 'UN-2025-1345', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, '1234567');
SELECT maqueta_donacion('5678901', 'Reposicion', DATE '2024-11-05', TIME '11:30', 'UN-2024-1987', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7111111', 'Donacion altruista', DATE '2026-04-02', TIME '08:00', 'UN-2026-0402', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7111111', 'Donacion altruista', DATE '2025-08-19', TIME '08:00', 'UN-2025-1510', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7222222', 'Donacion altruista', DATE '2025-12-18', TIME '10:30', 'UN-2025-2410', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7333333', 'Donacion altruista', DATE '2025-03-11', TIME '08:00', 'UN-2025-0311', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2025-04-14', TIME '09:00', 'UN-2025-0414', 'A+', 'Reactivo', 'Descartada', NULL, NULL, NULL);
SELECT maqueta_donacion('7555555', 'Donacion altruista', DATE '2025-06-08', TIME '08:00', 'UN-2025-0608', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('5485567', 'Donacion altruista', DATE '2026-08-20', TIME '11:00', 'UN-2026-JULI', 'O+', 'Reactivo', 'Descartada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2023-11-01', TIME '07:00', 'UN-H-3456789-01', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2023-10-31', TIME '07:00', 'UN-H-3456789-02', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3456789', 'Donacion altruista', DATE '2023-10-30', TIME '07:00', 'UN-H-3456789-03', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-31', TIME '07:00', 'UN-H-2987654-01', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-30', TIME '07:00', 'UN-H-2987654-02', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-29', TIME '07:00', 'UN-H-2987654-03', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-28', TIME '07:00', 'UN-H-2987654-04', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-27', TIME '07:00', 'UN-H-2987654-05', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-24', TIME '07:00', 'UN-H-2987654-06', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-23', TIME '07:00', 'UN-H-2987654-07', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-22', TIME '07:00', 'UN-H-2987654-08', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-21', TIME '07:00', 'UN-H-2987654-09', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-20', TIME '07:00', 'UN-H-2987654-10', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2987654', 'Donacion altruista', DATE '2024-05-17', TIME '07:00', 'UN-H-2987654-11', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3789012', 'Donacion altruista', DATE '2024-08-01', TIME '07:00', 'UN-H-3789012-01', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('3789012', 'Donacion altruista', DATE '2024-07-31', TIME '07:00', 'UN-H-3789012-02', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-05-01', TIME '07:00', 'UN-H-2345678-01', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-28', TIME '07:00', 'UN-H-2345678-02', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-27', TIME '07:00', 'UN-H-2345678-03', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-26', TIME '07:00', 'UN-H-2345678-04', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-25', TIME '07:00', 'UN-H-2345678-05', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-24', TIME '07:00', 'UN-H-2345678-06', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('2345678', 'Donacion altruista', DATE '2023-04-21', TIME '07:00', 'UN-H-2345678-07', 'B-', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-03-01', TIME '07:00', 'UN-H-1876543-01', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-28', TIME '07:00', 'UN-H-1876543-02', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-27', TIME '07:00', 'UN-H-1876543-03', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-26', TIME '07:00', 'UN-H-1876543-04', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-23', TIME '07:00', 'UN-H-1876543-05', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-22', TIME '07:00', 'UN-H-1876543-06', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-21', TIME '07:00', 'UN-H-1876543-07', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-20', TIME '07:00', 'UN-H-1876543-08', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-19', TIME '07:00', 'UN-H-1876543-09', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-16', TIME '07:00', 'UN-H-1876543-10', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-15', TIME '07:00', 'UN-H-1876543-11', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-14', TIME '07:00', 'UN-H-1876543-12', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-13', TIME '07:00', 'UN-H-1876543-13', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-12', TIME '07:00', 'UN-H-1876543-14', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-09', TIME '07:00', 'UN-H-1876543-15', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-08', TIME '07:00', 'UN-H-1876543-16', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-07', TIME '07:00', 'UN-H-1876543-17', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-06', TIME '07:00', 'UN-H-1876543-18', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-05', TIME '07:00', 'UN-H-1876543-19', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('1876543', 'Donacion altruista', DATE '2018-02-02', TIME '07:00', 'UN-H-1876543-20', 'AB+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('5678901', 'Donacion altruista', DATE '2023-09-01', TIME '07:00', 'UN-H-5678901-01', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7111111', 'Donacion altruista', DATE '2024-10-01', TIME '07:00', 'UN-H-7111111-01', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7222222', 'Donacion altruista', DATE '2024-04-01', TIME '07:00', 'UN-H-7222222-01', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7222222', 'Donacion altruista', DATE '2024-03-29', TIME '07:00', 'UN-H-7222222-02', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7222222', 'Donacion altruista', DATE '2024-03-28', TIME '07:00', 'UN-H-7222222-03', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7333333', 'Donacion altruista', DATE '2024-01-15', TIME '07:00', 'UN-H-7333333-01', 'O+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2023-06-30', TIME '07:00', 'UN-H-7444444-01', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2023-06-29', TIME '07:00', 'UN-H-7444444-02', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2023-06-28', TIME '07:00', 'UN-H-7444444-03', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2023-06-27', TIME '07:00', 'UN-H-7444444-04', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);
SELECT maqueta_donacion('7444444', 'Donacion altruista', DATE '2023-06-26', TIME '07:00', 'UN-H-7444444-05', 'A+', 'No reactivo', 'Utilizada', NULL, NULL, NULL);

-- 86 donaciones del período (más Jorge UN-2026-0912 = 87)

SELECT maqueta_donacion('90000001', 'Donacion altruista', DATE '2026-09-01', TIME '07:00', 'UN-P-0001', 'O+', 'Reactivo', 'Descartada', NULL, 'Hematoma en el sitio de punción.', NULL);
SELECT maqueta_donacion('90000002', 'Donacion altruista', DATE '2026-09-02', TIME '07:00', 'UN-P-0002', 'O+', 'Reactivo', 'Descartada', NULL, 'Hematoma en el sitio de punción.', NULL);
SELECT maqueta_donacion('90000003', 'Donacion altruista', DATE '2026-09-03', TIME '07:00', 'UN-P-0003', 'O+', 'Reactivo', 'Descartada', NULL, 'Hematoma en el sitio de punción.', NULL);
SELECT maqueta_donacion('90000004', 'Donacion altruista', DATE '2026-09-04', TIME '07:00', 'UN-P-0004', 'O+', 'Reactivo', 'Descartada', NULL, 'Hematoma en el sitio de punción.', NULL);
SELECT maqueta_donacion('90000005', 'Donacion altruista', DATE '2026-09-07', TIME '07:00', 'UN-P-0005', 'O+', 'No reactivo', 'En stock', DATE '2026-09-18', 'Cuadro febril durante la extracción.', NULL);
SELECT maqueta_donacion('90000006', 'Donacion altruista', DATE '2026-09-08', TIME '07:00', 'UN-P-0006', 'O+', 'No reactivo', 'En stock', DATE '2026-09-22', 'Cuadro febril durante la extracción.', NULL);
SELECT maqueta_donacion('90000007', 'Donacion altruista', DATE '2026-09-09', TIME '07:00', 'UN-P-0007', 'O+', 'No reactivo', 'En stock', DATE '2026-09-27', 'Cuadro febril durante la extracción.', NULL);
SELECT maqueta_donacion('90000008', 'Donacion altruista', DATE '2026-09-10', TIME '07:00', 'UN-P-0008', 'O+', 'No reactivo', 'En stock', DATE '2026-10-01', 'Lipotimia en sala de extracción.', NULL);
SELECT maqueta_donacion('90000009', 'Donacion altruista', DATE '2026-09-01', TIME '07:30', 'UN-P-0009', 'O+', 'No reactivo', 'En stock', DATE '2026-10-05', 'Lipotimia en sala de extracción.', NULL);
SELECT maqueta_donacion('90000010', 'Donacion altruista', DATE '2026-09-02', TIME '07:30', 'UN-P-0010', 'O+', 'No reactivo', 'En stock', DATE '2026-10-09', 'Lipotimia en sala de extracción.', NULL);
SELECT maqueta_donacion('90000011', 'Donacion altruista', DATE '2026-09-03', TIME '07:30', 'UN-P-0011', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Reacción alérgica leve.', NULL);
SELECT maqueta_donacion('90000012', 'Donacion altruista', DATE '2026-09-04', TIME '07:30', 'UN-P-0012', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Reacción alérgica leve.', NULL);
SELECT maqueta_donacion('90000013', 'Donacion altruista', DATE '2026-09-07', TIME '07:30', 'UN-P-0013', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Náuseas durante la donación.', NULL);
SELECT maqueta_donacion('90000014', 'Donacion altruista', DATE '2026-09-08', TIME '07:30', 'UN-P-0014', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Náuseas durante la donación.', NULL);
SELECT maqueta_donacion('90000015', 'Donacion altruista', DATE '2026-09-09', TIME '07:30', 'UN-P-0015', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Dolor local en el brazo.', NULL);
SELECT maqueta_donacion('90000016', 'Donacion altruista', DATE '2026-09-10', TIME '07:30', 'UN-P-0016', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Dolor local en el brazo.', NULL);
SELECT maqueta_donacion('90000017', 'Donacion altruista', DATE '2026-09-01', TIME '08:00', 'UN-P-0017', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Hipotensión transitoria.', NULL);
SELECT maqueta_donacion('90000018', 'Donacion altruista', DATE '2026-09-02', TIME '08:00', 'UN-P-0018', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Hormigueo en la mano.', NULL);
SELECT maqueta_donacion('90000019', 'Donacion altruista', DATE '2026-09-03', TIME '08:00', 'UN-P-0019', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Reacción vasovagal.', NULL);
SELECT maqueta_donacion('90000020', 'Donacion altruista', DATE '2026-09-04', TIME '08:00', 'UN-P-0020', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Otro evento adverso no clasificado.', NULL);
SELECT maqueta_donacion('90000021', 'Donacion altruista', DATE '2026-09-07', TIME '08:00', 'UN-P-0021', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000022', 'Donacion altruista', DATE '2026-09-08', TIME '08:00', 'UN-P-0022', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000023', 'Donacion altruista', DATE '2026-09-09', TIME '08:00', 'UN-P-0023', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000024', 'Donacion altruista', DATE '2026-09-10', TIME '08:00', 'UN-P-0024', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000025', 'Donacion altruista', DATE '2026-09-01', TIME '08:30', 'UN-P-0025', 'O+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000026', 'Donacion altruista', DATE '2026-09-02', TIME '08:30', 'UN-P-0026', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000027', 'Donacion altruista', DATE '2026-09-03', TIME '08:30', 'UN-P-0027', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000028', 'Donacion altruista', DATE '2026-09-04', TIME '08:30', 'UN-P-0028', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000029', 'Donacion altruista', DATE '2026-09-07', TIME '08:30', 'UN-P-0029', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000030', 'Donacion altruista', DATE '2026-09-08', TIME '08:30', 'UN-P-0030', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000031', 'Donacion altruista', DATE '2026-09-09', TIME '08:30', 'UN-P-0031', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000032', 'Donacion altruista', DATE '2026-09-10', TIME '08:30', 'UN-P-0032', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000033', 'Donacion altruista', DATE '2026-09-01', TIME '09:00', 'UN-P-0033', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000034', 'Donacion altruista', DATE '2026-09-02', TIME '09:00', 'UN-P-0034', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000035', 'Donacion altruista', DATE '2026-09-03', TIME '09:00', 'UN-P-0035', 'A+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000036', 'Donacion altruista', DATE '2026-09-04', TIME '09:00', 'UN-P-0036', 'B+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000037', 'Donacion altruista', DATE '2026-09-07', TIME '09:00', 'UN-P-0037', 'B+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000038', 'Donacion altruista', DATE '2026-09-08', TIME '09:00', 'UN-P-0038', 'B+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000039', 'Donacion altruista', DATE '2026-09-09', TIME '09:00', 'UN-P-0039', 'B+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000040', 'Donacion altruista', DATE '2026-09-10', TIME '09:00', 'UN-P-0040', 'AB+', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000041', 'Donacion altruista', DATE '2026-09-01', TIME '09:30', 'UN-P-0041', 'O-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000042', 'Donacion altruista', DATE '2026-09-02', TIME '09:30', 'UN-P-0042', 'O-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000043', 'Donacion altruista', DATE '2026-09-03', TIME '09:30', 'UN-P-0043', 'O-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000044', 'Donacion altruista', DATE '2026-09-04', TIME '09:30', 'UN-P-0044', 'A-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000045', 'Donacion altruista', DATE '2026-09-07', TIME '09:30', 'UN-P-0045', 'A-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000046', 'Donacion altruista', DATE '2026-09-08', TIME '09:30', 'UN-P-0046', 'B-', 'No reactivo', 'En stock', DATE '2026-11-15', 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000047', 'Donacion solidaria', DATE '2026-09-09', TIME '09:30', 'UN-P-0047', 'A+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000010');
SELECT maqueta_donacion('90000048', 'Donacion solidaria', DATE '2026-09-10', TIME '09:30', 'UN-P-0048', 'A+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000011');
SELECT maqueta_donacion('90000049', 'Donacion solidaria', DATE '2026-09-01', TIME '10:00', 'UN-P-0049', 'A+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000012');
SELECT maqueta_donacion('90000050', 'Donacion solidaria', DATE '2026-09-02', TIME '10:00', 'UN-P-0050', 'A+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000013');
SELECT maqueta_donacion('90000051', 'Donacion solidaria', DATE '2026-09-03', TIME '10:00', 'UN-P-0051', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000014');
SELECT maqueta_donacion('90000052', 'Donacion solidaria', DATE '2026-09-04', TIME '10:00', 'UN-P-0052', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000015');
SELECT maqueta_donacion('90000053', 'Donacion solidaria', DATE '2026-09-07', TIME '10:00', 'UN-P-0053', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000016');
SELECT maqueta_donacion('90000054', 'Donacion solidaria', DATE '2026-09-08', TIME '10:00', 'UN-P-0054', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000017');
SELECT maqueta_donacion('90000055', 'Donacion altruista', DATE '2026-09-09', TIME '10:00', 'UN-P-0055', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000018');
SELECT maqueta_donacion('90000056', 'Donacion altruista', DATE '2026-09-10', TIME '10:00', 'UN-P-0056', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000019');
SELECT maqueta_donacion('90000057', 'Donacion altruista', DATE '2026-09-01', TIME '10:30', 'UN-P-0057', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000020');
SELECT maqueta_donacion('90000058', 'Donacion altruista', DATE '2026-09-02', TIME '10:30', 'UN-P-0058', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000021');
SELECT maqueta_donacion('90000059', 'Donacion altruista', DATE '2026-09-03', TIME '10:30', 'UN-P-0059', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000022');
SELECT maqueta_donacion('90000060', 'Donacion altruista', DATE '2026-09-04', TIME '10:30', 'UN-P-0060', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000023');
SELECT maqueta_donacion('90000061', 'Donacion altruista', DATE '2026-09-07', TIME '10:30', 'UN-P-0061', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000024');
SELECT maqueta_donacion('90000062', 'Reposicion', DATE '2026-09-08', TIME '10:30', 'UN-P-0062', 'B+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000025');
SELECT maqueta_donacion('90000063', 'Reposicion', DATE '2026-09-09', TIME '10:30', 'UN-P-0063', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000026');
SELECT maqueta_donacion('90000064', 'Reposicion', DATE '2026-09-10', TIME '10:30', 'UN-P-0064', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000027');
SELECT maqueta_donacion('90000065', 'Reposicion', DATE '2026-09-01', TIME '11:00', 'UN-P-0065', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000028');
SELECT maqueta_donacion('90000066', 'Reposicion', DATE '2026-09-02', TIME '11:00', 'UN-P-0066', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000029');
SELECT maqueta_donacion('90000067', 'Reposicion', DATE '2026-09-03', TIME '11:00', 'UN-P-0067', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000030');
SELECT maqueta_donacion('90000068', 'Reposicion', DATE '2026-09-04', TIME '11:00', 'UN-P-0068', 'AB+', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000031');
SELECT maqueta_donacion('90000069', 'Reposicion', DATE '2026-09-07', TIME '11:00', 'UN-P-0069', 'O-', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000032');
SELECT maqueta_donacion('90000070', 'Reposicion', DATE '2026-09-08', TIME '11:00', 'UN-P-0070', 'O-', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000033');
SELECT maqueta_donacion('90000071', 'Reposicion', DATE '2026-09-09', TIME '11:00', 'UN-P-0071', 'O-', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000034');
SELECT maqueta_donacion('90000072', 'Reposicion', DATE '2026-09-10', TIME '11:00', 'UN-P-0072', 'O-', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000035');
SELECT maqueta_donacion('90000073', 'Reposicion', DATE '2026-09-01', TIME '11:30', 'UN-P-0073', 'O-', 'No reactivo', 'Asignada', NULL, 'Extracción sin incidentes.', '80000036');
SELECT maqueta_donacion('90000074', 'Reposicion', DATE '2026-09-02', TIME '11:30', 'UN-P-0074', 'O-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000075', 'Reposicion', DATE '2026-09-03', TIME '11:30', 'UN-P-0075', 'O-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000076', 'Reposicion', DATE '2026-09-04', TIME '11:30', 'UN-P-0076', 'O-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000077', 'Reposicion', DATE '2026-09-07', TIME '11:30', 'UN-P-0077', 'A-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000078', 'Reposicion', DATE '2026-09-08', TIME '11:30', 'UN-P-0078', 'A-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000079', 'Reposicion', DATE '2026-09-09', TIME '11:30', 'UN-P-0079', 'A-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000080', 'Reposicion', DATE '2026-09-10', TIME '11:30', 'UN-P-0080', 'A-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000081', 'Reposicion', DATE '2026-09-01', TIME '12:00', 'UN-P-0081', 'A-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000082', 'Reposicion', DATE '2026-09-02', TIME '12:00', 'UN-P-0082', 'B-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000083', 'Reposicion', DATE '2026-09-03', TIME '12:00', 'UN-P-0083', 'B-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000084', 'Reposicion', DATE '2026-09-04', TIME '12:00', 'UN-P-0084', 'B-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000085', 'Reposicion', DATE '2026-09-07', TIME '12:00', 'UN-P-0085', 'B-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);
SELECT maqueta_donacion('90000086', 'Reposicion', DATE '2026-09-08', TIME '12:00', 'UN-P-0086', 'AB-', 'No reactivo', 'Utilizada', NULL, 'Extracción sin incidentes.', NULL);

-- Citas del 2026-09-10 (donación y compatibilidad)

SELECT maqueta_cita('3456789', 'Donacion altruista', DATE '2026-09-10', TIME '07:30', 'Pendiente', NULL, '00000000');
SELECT maqueta_cita('4123456', 'Reposicion', DATE '2026-09-10', TIME '08:00', 'Pendiente', NULL, '00000000');
SELECT maqueta_cita('3789012', 'Donacion altruista', DATE '2026-09-10', TIME '09:30', 'Ausente', NULL, '10000001');
SELECT maqueta_cita('4567890', 'Reposicion', DATE '2026-09-10', TIME '10:00', 'Pendiente', NULL, '00000000');
SELECT maqueta_cita('6123456', 'Reposicion', DATE '2026-09-10', TIME '11:00', 'Pendiente', NULL, '00000000');
SELECT maqueta_cita('1876543', 'Donacion altruista', DATE '2026-09-10', TIME '11:30', 'Pendiente', NULL, '00000000');
SELECT maqueta_cita('5678901', 'Donacion solidaria', DATE '2026-09-10', TIME '12:00', 'Ausente', '1234567', '10000001');
-- Compatibilidad: donantes del padrón (no el paciente). RN03 impide citarse por solicitud propia.
SELECT maqueta_cita('90000009', 'Extraccion de compatibilidad', DATE '2026-09-10', TIME '07:30', 'Pendiente', '1234567', '00000000');
SELECT maqueta_cita('90000010', 'Extraccion de compatibilidad', DATE '2026-09-10', TIME '08:00', 'Completada', '80000001', '10000001');
SELECT maqueta_cita('90000011', 'Extraccion de compatibilidad', DATE '2026-09-10', TIME '08:30', 'Pendiente', '80000002', '00000000');
SELECT maqueta_cita('90000012', 'Extraccion de compatibilidad', DATE '2026-09-10', TIME '09:00', 'Pendiente', '80000003', '00000000');
SELECT maqueta_donacion('90000010', 'Extraccion de compatibilidad', DATE '2026-09-10', TIME '08:00', 'UN-2026-EC02', 'A+', 'No reactivo', 'Asignada', NULL, NULL, '80000001');

-- Citas no aptas y diferimientos

SELECT maqueta_cita('3456789', 'Donacion altruista', DATE '2024-06-12', TIME '07:30', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('3456789', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '3456789' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2024-06-12') AND h.hora_inicio = TIME '07:30' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2024-06-12', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='3456789' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2024-06-12') LIMIT 1), 'HB', 11.2, TIMESTAMP '2024-06-12 07:40');
SELECT maqueta_cita('4123456', 'Donacion altruista', DATE '2025-11-30', TIME '08:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('4123456', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '4123456' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2025-11-30') AND h.hora_inicio = TIME '08:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2025-11-30', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='4123456' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2025-11-30') LIMIT 1), 'HB', 11.8, TIMESTAMP '2025-11-30 08:10');
SELECT maqueta_diferimiento('5234567', 'Presión arterial fuera de rango', NULL, 'CUESTIONARIO_PERSONAL', 'Hospital Bautista', DATE '2026-09-10', NULL);
SELECT maqueta_diferimiento('2345678', 'HBsAg (Hepatitis B)', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '2345678' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2025-07-10') AND h.hora_inicio = TIME '10:30' LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2025-07-10', NULL);
SELECT maqueta_cita('7222222', 'Donacion altruista', DATE '2026-06-20', TIME '10:30', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('7222222', 'Tatuaje, piercing o acupuntura', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '7222222' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-06-20') AND h.hora_inicio = TIME '10:30' LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-06-20', NULL);
SELECT maqueta_cita('7333333', 'Donacion altruista', DATE '2025-09-02', TIME '08:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('7333333', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '7333333' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2025-09-02') AND h.hora_inicio = TIME '08:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2025-09-02', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='7333333' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2025-09-02') LIMIT 1), 'HB', 11.0, TIMESTAMP '2025-09-02 08:15');
SELECT maqueta_cita('7444444', 'Donacion altruista', DATE '2026-02-11', TIME '09:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('7444444', 'Anti-HCV (Hepatitis C)', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '7444444' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-02-11') AND h.hora_inicio = TIME '09:00' LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-02-11', NULL);
SELECT maqueta_diferimiento('7555555', 'Enfermedad infecciosa reciente', NULL, 'CUESTIONARIO_PERSONAL', 'Hospital Nacional de Itauguá', DATE '2026-07-01', NULL);
SELECT maqueta_diferimiento('5485567', 'VIH 1/2', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '5485567' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-08-20') AND h.hora_inicio = TIME '11:00' LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-08-20', NULL);
SELECT maqueta_cita('90000201', 'Donacion altruista', DATE '2026-09-01', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000201', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000201' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-01') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-01', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000201' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-01') LIMIT 1), 'HB', 11.1, TIMESTAMP '2026-09-01 07:15');
SELECT maqueta_cita('90000202', 'Donacion altruista', DATE '2026-09-02', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000202', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000202' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-02') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-02', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000202' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-02') LIMIT 1), 'HB', 11.1, TIMESTAMP '2026-09-02 07:15');
SELECT maqueta_diferimiento('90000202', 'Cuadro febril o gripal', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000202' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-02') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-02', NULL);
SELECT maqueta_cita('90000203', 'Donacion altruista', DATE '2026-09-03', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000203', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000203' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-03') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-03', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000203' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-03') LIMIT 1), 'HB', 11.1, TIMESTAMP '2026-09-03 07:15');
SELECT maqueta_diferimiento('90000203', 'Cuadro febril o gripal', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000203' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-03') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-03', NULL);
SELECT maqueta_cita('90000204', 'Donacion altruista', DATE '2026-09-04', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000204', 'Hemoglobina baja', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000204' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-04') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-04', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000204' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-04') LIMIT 1), 'HB', 11.1, TIMESTAMP '2026-09-04 07:15');
SELECT maqueta_diferimiento('90000204', 'Enfermedad infecciosa reciente', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000204' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-04') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-04', NULL);
SELECT maqueta_cita('90000205', 'Donacion altruista', DATE '2026-09-07', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000205', 'Presión arterial fuera de rango', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000205' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-07') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-07', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000205' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-07') LIMIT 1), 'PAS', 170, TIMESTAMP '2026-09-07 07:15');
SELECT maqueta_diferimiento('90000205', 'Enfermedad infecciosa reciente', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000205' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-07') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-07', NULL);
SELECT maqueta_cita('90000206', 'Donacion altruista', DATE '2026-09-08', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000206', 'Presión arterial fuera de rango', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000206' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-08') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-08', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000206' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-08') LIMIT 1), 'PAS', 170, TIMESTAMP '2026-09-08 07:15');
SELECT maqueta_diferimiento('90000206', 'Tratamiento con antibióticos', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000206' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-08') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-08', NULL);
SELECT maqueta_cita('90000207', 'Donacion altruista', DATE '2026-09-09', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000207', 'Presión arterial fuera de rango', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000207' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-09') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-09', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000207' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-09') LIMIT 1), 'PAS', 170, TIMESTAMP '2026-09-09 07:15');
SELECT maqueta_diferimiento('90000207', 'Tratamiento con antibióticos', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000207' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-09') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-09', NULL);
SELECT maqueta_cita('90000208', 'Donacion altruista', DATE '2026-09-10', TIME '07:00', 'No apto', NULL, '10000001');
SELECT maqueta_diferimiento('90000208', 'Presión arterial fuera de rango', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario = c.id_usuario JOIN horario_disponible h ON h.id_horario = c.id_horario WHERE u.documento = '90000208' AND c.fecha_hora_creacion = maqueta_reserva(DATE '2026-09-10') AND h.hora_inicio = TIME '07:00' LIMIT 1), 'MEDICION', 'Hospital Regional de Luque', DATE '2026-09-10', NULL);
SELECT maqueta_medicion((SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000208' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-10') LIMIT 1), 'PAS', 170, TIMESTAMP '2026-09-10 07:15');
SELECT maqueta_diferimiento('90000208', 'Peso inferior al mínimo', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000208' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-10') LIMIT 1), 'CUESTIONARIO_PERSONAL', 'Hospital Regional de Luque', DATE '2026-09-10', NULL);
SELECT maqueta_diferimiento('90000001', 'VDRL (Sífilis)', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000001' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-01') LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-09-01', NULL);
SELECT maqueta_diferimiento('90000002', 'Chagas (T. cruzi)', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000002' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-02') LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-09-02', NULL);
SELECT maqueta_diferimiento('90000003', 'HTLV I/II', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000003' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-03') LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-09-03', NULL);
SELECT maqueta_diferimiento('90000004', 'CMV', (SELECT c.id_cita FROM cita c JOIN usuario u ON u.id_usuario=c.id_usuario WHERE u.documento='90000004' AND c.fecha_hora_creacion=maqueta_reserva(DATE '2026-09-04') LIMIT 1), 'LABORATORIO', 'Hospital Regional de Luque', DATE '2026-09-04', NULL);

-- Cada resultado reactivo apunta a los diferimientos de laboratorio de esa extracción.
UPDATE registro_diferimiento rd
   SET id_resultado = r.id_resultado
  FROM resultado_laboratorio r
  JOIN unidad u ON u.id_unidad = r.id_unidad
  JOIN extraccion e ON e.id_extraccion = u.id_extraccion
 WHERE rd.id_donante = u.id_donante
   AND rd.id_cita = e.id_cita
   AND rd.origen = 'LABORATORIO'
   AND r.resultado = 'Reactivo'
   AND rd.id_resultado IS NULL
   AND rd.id_diferimiento IN (
        SELECT d.id_diferimiento FROM diferimiento d WHERE d.tipo = 'Permanente'
   );

-- Citaciones de consejería (solo permanentes con resultado)


INSERT INTO citacion_consejeria (id_donante, id_personal, id_horario, id_resultado, fecha_hora, estado, observaciones)
SELECT don.id_usuario,
       (SELECT id_usuario FROM usuario WHERE documento = '10000002'),
       maqueta_id_horario(DATE '2026-09-10', v.hora),
       r.id_resultado,
       DATE '2026-09-10' + v.hora,
       v.estado,
       v.obs
  FROM (VALUES
          ('2345678', TIME '08:00', 'Pendiente', 'Serología reactiva — permanente'),
          ('7444444', TIME '09:00', 'Pendiente', 'Serología reactiva — permanente'),
          ('5485567', TIME '11:00', 'Pendiente', 'VIH — permanente')
       ) AS v(doc, hora, estado, obs)
  JOIN usuario don ON don.documento = v.doc
  JOIN LATERAL (
        SELECT r.id_resultado
          FROM unidad u
          JOIN resultado_laboratorio r ON r.id_unidad = u.id_unidad
         WHERE u.id_donante = don.id_usuario AND r.resultado = 'Reactivo'
         ORDER BY r.id_resultado
         LIMIT 1
       ) r ON true
 WHERE NOT EXISTS (SELECT 1 FROM citacion_consejeria c WHERE c.id_resultado = r.id_resultado);


DROP FUNCTION IF EXISTS maqueta_donacion(varchar, varchar, date, time, varchar, varchar, varchar, varchar, date, text, varchar);
DROP FUNCTION IF EXISTS maqueta_solicitud(varchar, varchar, varchar, integer, integer, varchar, timestamp);
DROP FUNCTION IF EXISTS maqueta_diferimiento(varchar, varchar, integer, varchar, varchar, date, date);
DROP FUNCTION IF EXISTS maqueta_medicion(integer, varchar, numeric, timestamp);
DROP FUNCTION IF EXISTS maqueta_cita(varchar, varchar, date, time, varchar, varchar, varchar);
DROP FUNCTION IF EXISTS maqueta_usuario(varchar, varchar, varchar, date, varchar, varchar, varchar, varchar);
DROP FUNCTION IF EXISTS maqueta_reserva(date);
DROP FUNCTION IF EXISTS maqueta_id_horario(date, time);
DROP FUNCTION IF EXISTS maqueta_id_tipo(text);

COMMIT;

-- Controles (período 2026-09-01 a 2026-09-10)
SELECT
  (SELECT count(*) FROM rol) AS roles,
  (SELECT count(*) FROM tipo_sangre) AS tipos_sangre,
  (SELECT count(*) FROM compatibilidad_abo_rh) AS compatibilidades,
  (SELECT count(*) FROM tipo_medicion) AS mediciones,
  (SELECT count(*) FROM diferimiento) AS diferimientos,
  (SELECT count(*) FROM pregunta) AS preguntas,
  (SELECT count(*) FROM horario_disponible) AS franjas,
  (SELECT count(*) FROM contenido_portal) AS contenidos;

SELECT
  (SELECT count(*) FROM usuario_rol ur JOIN rol r ON r.id_rol = ur.id_rol
    WHERE r.codigo = 'DONANTE' AND EXISTS (
      SELECT 1 FROM usuario u WHERE u.id_usuario = ur.id_usuario
        AND u.documento IN ('3456789','4123456','2987654','5234567','3789012',
                            '4567890','2345678','6123456','1876543','5678901',
                            '7111111','7222222','7333333','7444444','7555555'))) AS donantes_nominales,
  (SELECT count(*) FROM usuario WHERE documento = '5485567') AS julieta,
  (SELECT count(*) FROM cita c
     JOIN usuario u ON u.id_usuario = c.id_usuario
     JOIN horario_disponible h ON h.id_horario = c.id_horario
    WHERE u.documento IN ('3456789','4123456','2987654','5234567','3789012',
                          '4567890','2345678','6123456','1876543','5678901')
      AND c.fecha_hora_creacion = timestamp '2026-09-09 08:00'
      AND c.tipo_cita <> 'Extraccion de compatibilidad') AS citas_dia_nominales,
  (SELECT count(*) FROM usuario u
    WHERE u.documento IN ('7111111','7222222','7333333','7444444','7555555')
      AND NOT EXISTS (
        SELECT 1 FROM cita c WHERE c.id_usuario = u.id_usuario
          AND c.estado IN ('Pendiente','Confirmada'))) AS espontaneos_sin_cita_activa,
  (SELECT count(*) FROM solicitud s JOIN usuario u ON u.id_usuario = s.id_solicitante
    WHERE u.documento IN ('1234567','80000001','80000002','80000003')) AS solicitudes_nominales,
  (SELECT count(*) FROM extraccion e JOIN cita c ON c.id_cita = e.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita <> 'Extraccion de compatibilidad') AS extracciones_periodo,
  (SELECT count(*) FROM cita c JOIN extraccion e ON e.id_cita = c.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita = 'Donacion altruista') AS altruistas_periodo,
  (SELECT count(*) FROM cita c JOIN extraccion e ON e.id_cita = c.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita = 'Reposicion') AS reposicion_periodo,
  (SELECT count(*) FROM cita c JOIN extraccion e ON e.id_cita = c.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita = 'Donacion solidaria') AS solidarias_periodo,
  (SELECT count(*) FROM resultado_laboratorio r JOIN unidad u ON u.id_unidad = r.id_unidad
    JOIN extraccion e ON e.id_extraccion = u.id_extraccion
    JOIN cita c ON c.id_cita = e.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita <> 'Extraccion de compatibilidad'
      AND r.resultado = 'Reactivo') AS reactivos_periodo,
  (SELECT count(*) FROM resultado_laboratorio r JOIN unidad u ON u.id_unidad = r.id_unidad
    JOIN extraccion e ON e.id_extraccion = u.id_extraccion
    JOIN cita c ON c.id_cita = e.id_cita
    WHERE e.fecha::date BETWEEN DATE '2026-09-01' AND DATE '2026-09-10'
      AND c.tipo_cita <> 'Extraccion de compatibilidad'
      AND r.resultado = 'No reactivo') AS no_reactivos_periodo,
  (SELECT count(*) FROM unidad WHERE estado = 'En stock' AND componente = 'sangre_total') AS stock_total,
  (SELECT count(*) FROM unidad
    WHERE estado = 'En stock'
      AND fecha_vencimiento > DATE '2026-09-10'
      AND fecha_vencimiento <= DATE '2026-10-10') AS proximas_a_vencer,
  (SELECT count(*) FROM solicitud WHERE estado = 'Completa') AS solicitudes_completas,
  (SELECT count(*) FROM solicitud WHERE estado = 'Publicada') AS solicitudes_publicadas,
  (SELECT count(*) FROM cita WHERE estado = 'No apto') AS citas_no_apto,
  (SELECT count(*) FROM registro_diferimiento rd JOIN diferimiento d ON d.id_diferimiento = rd.id_diferimiento
    WHERE d.tipo = 'Temporal') AS dif_temporales,
  (SELECT count(*) FROM registro_diferimiento rd JOIN diferimiento d ON d.id_diferimiento = rd.id_diferimiento
    WHERE d.tipo = 'Permanente') AS dif_permanentes;
