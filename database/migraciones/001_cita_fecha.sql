-- 001_cita_fecha.sql
--
-- Agrega la fecha concreta de la cita.
--
-- Por qué hace falta: cita solo tenía id_horario, que apunta a una franja
-- semanal ("Lunes 07:00"), y fecha_hora_creacion, que es cuándo se registró.
-- No había dónde guardar QUÉ DÍA es la cita. Sin eso no se puede construir
-- ni el agendamiento del portal ni la agenda del panel de administración:
-- las dos necesitan saber a qué lunes se refiere la franja.
--
-- Es un cambio aditivo: no modifica ni elimina nada existente. El código que
-- no menciona fecha_cita sigue funcionando igual que antes.

-- 1. La columna nace nullable para que el ALTER no falle si ya hay filas.
ALTER TABLE cita
    ADD COLUMN fecha_cita date;

-- 2. A las citas que ya existían se les asigna la fecha de creación. Es lo
--    más cercano a la verdad que se puede reconstruir, y evita dejar filas
--    sin fecha que después rompan las consultas.
UPDATE cita
   SET fecha_cita = fecha_hora_creacion::date
 WHERE fecha_cita IS NULL;

-- 3. Recién ahora se exige que siempre esté. Una cita sin día no tiene
--    sentido: mejor que la base lo impida a que se cuele una fila así.
ALTER TABLE cita
    ALTER COLUMN fecha_cita SET NOT NULL;

-- 4. La fecha tiene que caer en el día de la semana de su franja. Sin esto,
--    nada impide guardar una cita el miércoles en una franja de los lunes.
CREATE OR REPLACE FUNCTION fn_cita_fecha_coincide_franja()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_dia_fecha  text;
    v_dia_franja text;
BEGIN
    v_dia_fecha := CASE EXTRACT(DOW FROM NEW.fecha_cita)
                     WHEN 0 THEN 'Domingo'  WHEN 1 THEN 'Lunes'
                     WHEN 2 THEN 'Martes'   WHEN 3 THEN 'Miercoles'
                     WHEN 4 THEN 'Jueves'   WHEN 5 THEN 'Viernes'
                     ELSE 'Sabado' END;

    SELECT dia_semana INTO v_dia_franja
      FROM horario_disponible
     WHERE id_horario = NEW.id_horario;

    IF v_dia_franja IS DISTINCT FROM v_dia_fecha THEN
        RAISE EXCEPTION 'La fecha % cae en % y la franja es de %',
              NEW.fecha_cita, v_dia_fecha, v_dia_franja;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cita_fecha_coincide_franja
BEFORE INSERT OR UPDATE ON cita
FOR EACH ROW
EXECUTE FUNCTION fn_cita_fecha_coincide_franja();

-- 5. El cupo de una franja se cuenta por fecha, no en general: cuatro
--    donantes el lunes 5 no ocupan el cupo del lunes 12. Este índice es el
--    que hace rápida esa consulta.
CREATE INDEX idx_cita_fecha_horario ON cita (fecha_cita, id_horario);
