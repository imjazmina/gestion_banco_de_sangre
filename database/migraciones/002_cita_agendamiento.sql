-- 002_cita_agendamiento.sql
--
-- Habilita que el donante agende su propia cita desde el portal.
--
-- Hasta acá la tabla cita suponía que alguien del banco la cargaba: exigía
-- personal asignado y no controlaba cupos ni repeticiones, porque se asumía
-- que la persona que la cargaba miraba la agenda. Con el portal eso cambia:
-- quien agenda es el donante, sin nadie mirando, y las reglas las tiene que
-- hacer cumplir la base.
--
-- AFECTA AL PANEL DE ADMINISTRACIÓN. Los controles de abajo se aplican a
-- toda cita, venga del portal o del panel. Es a propósito: una regla que
-- solo vale para una mitad del sistema no es una regla.

-- ---------------------------------------------------------------------------
-- 1. El personal se asigna después, no al reservar.
-- ---------------------------------------------------------------------------
-- Cuando el donante reserva todavía no hay nadie asignado: eso lo hace el
-- banco al organizar el día. Mantenerlo NOT NULL obligaría al portal a
-- inventar un responsable, que es peor que dejarlo vacío.
ALTER TABLE cita
    ALTER COLUMN id_personal DROP NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Una sola cita activa por donante.
-- ---------------------------------------------------------------------------
-- Sin esto, nada impide reservar veinte turnos y no presentarse a ninguno,
-- ocupando cupos que otra persona necesitaba. El índice es parcial: las
-- citas ya cerradas (Completada, Cancelada, Ausente, No apto) no cuentan,
-- así que el historial no estorba.
CREATE UNIQUE INDEX uq_cita_activa_por_donante
    ON cita (id_usuario)
    WHERE estado IN ('Pendiente', 'Confirmada');

-- ---------------------------------------------------------------------------
-- 3. Cupo de la franja, contado por fecha.
-- ---------------------------------------------------------------------------
-- horario_disponible.cupo_atencion dice cuántos donantes entran en la
-- franja. El cupo es por día: cuatro personas el lunes 5 no ocupan el cupo
-- del lunes 12. Sin este control, dos donantes que reservan al mismo tiempo
-- pasan los dos y el día de la cita sobra gente.
CREATE OR REPLACE FUNCTION fn_cita_controlar_cupo()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_cupo      integer;
    v_ocupados  integer;
    v_disponible boolean;
BEGIN
    -- Cancelar o cerrar una cita no consume cupo: no hace falta revalidar.
    IF NEW.estado NOT IN ('Pendiente', 'Confirmada') THEN
        RETURN NEW;
    END IF;

    SELECT cupo_atencion, disponible
      INTO v_cupo, v_disponible
      FROM horario_disponible
     WHERE id_horario = NEW.id_horario;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La franja horaria no existe';
    END IF;
    IF NOT v_disponible THEN
        RAISE EXCEPTION 'Esa franja horaria no está habilitada';
    END IF;

    SELECT count(*)
      INTO v_ocupados
      FROM cita
     WHERE fecha_cita = NEW.fecha_cita
       AND id_horario = NEW.id_horario
       AND estado IN ('Pendiente', 'Confirmada')
       AND id_cita IS DISTINCT FROM NEW.id_cita;

    IF v_ocupados >= v_cupo THEN
        RAISE EXCEPTION 'Sin cupo en esa franja (% de % ocupados)', v_ocupados, v_cupo;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cita_controlar_cupo
BEFORE INSERT OR UPDATE ON cita
FOR EACH ROW
EXECUTE FUNCTION fn_cita_controlar_cupo();

-- ---------------------------------------------------------------------------
-- 4. No se agenda con un diferimiento vigente.
-- ---------------------------------------------------------------------------
-- Si el personal registró un diferimiento, el donante no puede reservar
-- hasta que venza. Va en la base y no solo en la pantalla: así no se puede
-- saltear armando el pedido a mano.
CREATE OR REPLACE FUNCTION fn_cita_sin_diferimiento()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.estado NOT IN ('Pendiente', 'Confirmada') THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM registro_diferimiento r
         WHERE r.id_donante = NEW.id_usuario
           AND (r.fecha_fin IS NULL OR r.fecha_fin > CURRENT_DATE)
    ) THEN
        RAISE EXCEPTION 'El donante tiene un diferimiento vigente';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cita_sin_diferimiento
BEFORE INSERT OR UPDATE ON cita
FOR EACH ROW
EXECUTE FUNCTION fn_cita_sin_diferimiento();

-- ---------------------------------------------------------------------------
-- 5. No se agenda para una fecha que ya pasó.
-- ---------------------------------------------------------------------------
-- Solo al crear: el personal tiene que poder cerrar una cita de ayer como
-- Completada o Ausente, y eso es un UPDATE sobre una fecha pasada.
CREATE OR REPLACE FUNCTION fn_cita_fecha_futura()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.fecha_cita < CURRENT_DATE THEN
        RAISE EXCEPTION 'No se puede agendar para una fecha que ya pasó (%)', NEW.fecha_cita;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cita_fecha_futura
BEFORE INSERT ON cita
FOR EACH ROW
EXECUTE FUNCTION fn_cita_fecha_futura();
