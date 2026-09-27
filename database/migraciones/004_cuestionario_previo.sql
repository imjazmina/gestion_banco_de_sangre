-- 004_cuestionario_previo.sql
--
-- Prepara la tabla `pregunta` para el cuestionario oficial del banco de
-- sangre (36 preguntas de la Parte A) y habilita el aviso que se le manda
-- al donante unas horas antes de su cita.
--
-- AFECTA AL PANEL DE ADMINISTRACIÓN, pero solo sumando:
--   * `pregunta` gana cinco columnas, todas con valor por defecto. Ninguna
--     consulta que ya existe deja de funcionar.
--   * el CHECK de `notificacion.tipo` acepta un tipo más. Se amplía, no se
--     achica: todo lo que entraba antes sigue entrando.
--
-- Nada se borra. Las preguntas de prueba que había cargadas quedan marcadas
-- como inactivas en lugar de eliminarse, porque puede haber cuestionarios
-- viejos que las referencian.

-- ---------------------------------------------------------------------------
-- 1. El cuestionario oficial viene agrupado y numerado.
-- ---------------------------------------------------------------------------
-- El formulario del banco tiene tres bloques ("En la actualidad",
-- "Antecedentes personales", "En los últimos 12 meses") y las preguntas van
-- numeradas del 1 al 36. Sin dónde guardar el bloque y el número, la
-- pantalla las mostraría en el orden en que se insertaron, que no es el del
-- papel que firma el donante.
ALTER TABLE pregunta
    ADD COLUMN seccion varchar(40),
    ADD COLUMN orden integer,
    -- Algunas preguntas piden una aclaración además del sí o el no
    -- ("¿Por qué?", "¿Dónde? ¿Cuándo?", "¿Cuáles?").
    ADD COLUMN pide_detalle boolean NOT NULL DEFAULT false,
    ADD COLUMN etiqueta_detalle varchar(60),
    -- Aclaraciones del formulario original, como la de la pregunta 5.
    ADD COLUMN nota text,
    -- Para retirar una pregunta sin borrarla: los cuestionarios ya
    -- respondidos la siguen referenciando.
    ADD COLUMN activa boolean NOT NULL DEFAULT true,
    -- Cuál de las dos respuestas es la que el personal tiene que mirar.
    -- No alcanza con preselecciona_exclusion, que da por sentado que lo
    -- preocupante es el "sí": en "¿Se siente bien?" o "¿Descansó?" lo
    -- preocupante es el "no". Nulo en las preguntas informativas.
    -- El sistema NO decide con esto: marca, y decide el personal.
    ADD COLUMN alerta_si varchar(2);

ALTER TABLE pregunta
    ADD CONSTRAINT ck_pregunta_alerta
        CHECK (alerta_si IS NULL OR alerta_si IN ('Si', 'No'));

-- Las preguntas de ejemplo que se habían cargado no son las del formulario
-- real. Se apagan; el catálogo carga las oficiales.
UPDATE pregunta SET activa = false WHERE parte = 'A';

CREATE INDEX idx_pregunta_orden ON pregunta (parte, activa, orden);

-- ---------------------------------------------------------------------------
-- 2. Un tipo más de notificación.
-- ---------------------------------------------------------------------------
-- El aviso con el cuestionario no es un recordatorio de cita: se manda una
-- sola vez, unas horas antes, y sirve además para saber a quién ya se le
-- envió y no mandárselo dos veces.
ALTER TABLE notificacion
    DROP CONSTRAINT ck_notificacion_tipo;

ALTER TABLE notificacion
    ADD CONSTRAINT ck_notificacion_tipo CHECK (tipo IN (
        'CONFIRMACION_CITA',
        'RECORDATORIO_CITA',
        'CUESTIONARIO_PREVIO',
        'HABILITACION',
        'AGRADECIMIENTO',
        'ASIGNACION_DONANTE',
        'ASIGNACION_SOLICITANTE',
        'META_COMPLETA',
        'CITACION_GENERICA'
    ));
