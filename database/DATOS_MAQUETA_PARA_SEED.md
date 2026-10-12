# Datos de la maqueta para construir el script de carga

Este documento reúne los escenarios nominales y los datos agregados que debe
reproducir un futuro script de prueba para PostgreSQL.

No es un script SQL. El script deberá respetar sin cambios
`database/schema.sql` y reutilizar los catálogos de `database/catalogos.sql`.

## 1. Criterios generales

- Fecha de referencia de la maqueta: **2026-09-10**.
- Período inicial de los informes: **2026-09-01 a 2026-09-10**, inclusive.
- Institución local: **Hospital Regional de Luque (HRL)**.
- Personal de enfermería: **María Recalde**, documento `10000001`.
- Personal de jefatura: **Jorge Fernández**, documento `10000002`.
- Personal de servicio para citas todavía no asignadas: documento `00000000`.
- Los documentos deben guardarse sin puntos para facilitar las búsquedas.
- El script debe ser idempotente: identificar usuarios por `documento` y usar
  comprobaciones `NOT EXISTS` o `ON CONFLICT` donde exista una restricción
  única.
- No se deben insertar contraseñas para los donantes de prueba.
- Todos los donantes deben tener el rol `DONANTE`.

## 2. Correspondencia entre la maqueta y el esquema

- `Altruista` se guarda como `Donacion altruista`.
- `Reposición` se guarda como `Reposicion`.
- `Solicitud` se guarda como `Donacion solidaria` y requiere
  `cita.id_solicitud`.
- `Extracción de compatibilidad` se guarda con ese mismo valor.
- `Diferido` se guarda como estado de cita `No apto`.
- `Pendiente`, `Completada` y `Ausente` tienen correspondencia directa.
- La maqueta usa el tipo de cita `Diagnóstico`, pero el esquema no lo admite.
  Para Valeria se debe usar `Extraccion de compatibilidad` si existe una
  solicitud asociada; de lo contrario, `Donacion altruista` y dejar documentada
  la adaptación.
- El esquema no guarda dirección. Ese dato de la maqueta no puede insertarse.
- Teléfono y correo se guardan en `telefono` y `correo`.
- El grupo sanguíneo se referencia desde `usuario.id_tipo_sangre`.
- Una donación completada que deba aparecer en informes necesita, como mínimo:
  `cita` completada, `extraccion` y `unidad`.
- Para que una unidad esté disponible en stock necesita además
  `resultado_laboratorio = 'No reactivo'`, `unidad.estado = 'En stock'` y su
  tipo de sangre.

## 3. Donantes nominales

### 3.1 Carlos Benítez Ortiz

- Documento: `3456789`.
- Nacimiento: `1985-03-15`.
- Género: Masculino.
- Teléfono: `0981456789`.
- Correo: `cbenitez@gmail.com`.
- Grupo: O+.
- Cita del día: 07:30, altruista, pendiente.
- Historial visible:
  - 2026-03-12, altruista, completada, unidad `UN-2026-0234`, HRL.
  - 2025-09-08, altruista, completada, unidad `UN-2025-1876`, HRL.
  - 2025-03-20, altruista, completada, unidad `UN-2025-0412`, HRL.
  - 2024-06-12, altruista, no apto.
  - 2024-01-15, altruista, completada, unidad `UN-2024-0087`, HRL.
- Diferimiento temporal por hemoglobina baja:
  - Inicio: `2024-06-12`.
  - Fin esperado: `2024-09-10`.
  - Ya vencido para la fecha de referencia.
- La maqueta indica 7 donaciones totales, pero solo detalla 4 completadas. Si el
  total debe derivarse de la base, crear 3 donaciones completadas históricas
  adicionales.

### 3.2 María Fernanda Acosta

- Documento: `4123456`.
- Nacimiento: `1992-07-22`.
- Género: Femenino.
- Teléfono: `0991234567`.
- Correo: `mfacosta@outlook.com`.
- Cita del día: 08:00, reposición, pendiente.
- Historial visible:
  - 2025-11-30, no apta por hemoglobina baja.
  - 2025-05-14, altruista, completada, unidad `UN-2025-0823`.
- Diferimiento temporal HRL por hemoglobina baja:
  - Inicio: `2025-11-30`.
  - Fin mostrado por la maqueta: `2026-11-30`.
  - Sigue vigente el 2026-09-10.
- Revisión de jefatura: 11:30, ausente.
- La duración no coincide con los 30 días del catálogo actual. El script debe
  insertar explícitamente `fecha_fin = '2026-11-30'` si se quiere reproducir
  la maqueta.

### 3.3 Jorge Luis Gómez Díaz

- Documento: `2987654`.
- Nacimiento: `1978-11-08`.
- Género: Masculino.
- Teléfono: `0972345678`.
- Correo: `jlgomez@hotmail.com`.
- Grupo: A+.
- Cita del día: 08:30, altruista, completada.
- Historial visible:
  - 2026-09-10, completada, unidad `UN-2026-0912`.
  - 2026-03-05, completada, unidad `UN-2026-0198`.
  - 2025-09-22, completada, unidad `UN-2025-2011`.
- Sin diferimientos.
- La maqueta indica 14 donaciones totales; crear 11 históricas adicionales si
  el total debe calcularse desde la base.

### 3.4 Ana Patricia Ríos

- Documento: `5234567`.
- Nacimiento: `1990-05-30`.
- Género: Femenino.
- Teléfono: `0983567890`.
- Correo: `aprios@gmail.com`.
- Cita del día: 09:00, solidaria/solicitud, no apta.
- Historial visible:
  - 2026-09-10, no apta, Hospital Bautista.
  - 2025-08-15, altruista, completada, unidad `UN-2025-1432`, HRL.
- Diferimiento temporal externo por presión arterial elevada:
  - Inicio: `2026-09-10`.
  - Fin: `2026-12-10`.
  - Institución: `Hospital Bautista`.
- Revisión de jefatura: 10:00, pendiente.

### 3.5 Roberto Solís Ramírez

- Documento: `3789012`.
- Nacimiento: `1982-01-20`.
- Género: Masculino.
- Teléfono: `0994678901`.
- Correo: `rsolisram@gmail.com`.
- Cita del día: 09:30, altruista, ausente.
- Sin diferimientos.
- Historial visible:
  - 2025-12-05, completada, unidad `UN-2025-2345`.
  - 2025-06-18, completada, unidad `UN-2025-1087`.
- La maqueta indica 4 donaciones; crear 2 históricas adicionales si hace falta
  reproducir el total calculado.

### 3.6 Lucía Giménez Paredes

- Documento: `4567890`.
- Nacimiento: `1995-09-14`.
- Género: Femenino.
- Teléfono: `0985789012`.
- Correo: `lgparedes@gmail.com`.
- Cita del día: 10:00, reposición, pendiente.
- Primera donación: no tiene historial ni diferimientos.

### 3.7 Diego Cabrera Núñez

- Documento: `2345678`.
- Nacimiento: `1988-04-03`.
- Género: Masculino.
- Teléfono: `0971890123`.
- Correo: `dcabrera@yahoo.com`.
- Grupo: B-.
- Cita del día: 10:30, altruista, pendiente.
- Historial visible:
  - 2026-01-20, no apto.
  - 2025-07-10, completada, unidad `UN-2025-1234`.
- Diferimiento permanente HRL por serología reactiva:
  - Inicio: `2026-01-20`.
  - Sin fecha de fin.
- Revisión de jefatura: 08:00, pendiente.
- La maqueta indica 8 donaciones; crear 7 históricas adicionales si el total
  debe calcularse.

### 3.8 Valeria Morínigo Flores

- Documento: `6123456`.
- Nacimiento: `2000-12-25`.
- Género: Femenino.
- Teléfono: `0992901234`.
- Correo: `vmorinigo@gmail.com`.
- Cita del día: 11:00, diagnóstico, pendiente.
- Sin diferimientos.
- Historial: 2025-10-05, completada, unidad `UN-2025-1789`.
- Aplicar la adaptación del tipo `Diagnóstico` indicada en la sección 2.

### 3.9 Hugo Ramón Aquino

- Documento: `1876543`.
- Nacimiento: `1975-06-12`.
- Género: Masculino.
- Teléfono: `0981012345`.
- Correo: `hraquino@outlook.com`.
- Grupo: AB+.
- Cita del día: 11:30, altruista, pendiente.
- Historial visible:
  - 2026-06-15, completada, unidad `UN-2026-0623`.
  - 2025-12-28, completada, unidad `UN-2025-2567`.
- Sin diferimientos.
- La maqueta indica 22 donaciones; crear 20 históricas adicionales si se debe
  reproducir el total calculado.

### 3.10 Sandra Beatriz Villalba

- Documento: `5678901`.
- Nacimiento: `1993-03-08`.
- Género: Femenino.
- Teléfono: `0993123456`.
- Correo: `sbvillalba@gmail.com`.
- Cita del día: 12:00, solidaria/solicitud, ausente.
- Sin diferimientos.
- Historial:
  - 2025-07-22, solidaria, completada, unidad `UN-2025-1345`.
  - 2024-11-05, reposición, completada, unidad `UN-2024-1987`.
- La maqueta indica 3 donaciones; crear 1 histórica adicional si se debe
  reproducir el total calculado.

## 4. Donantes espontáneos

Estos usuarios no deben tener una cita activa al iniciar la demostración.

### 4.1 Elena Rojas Medina

- Documento: `7111111`.
- Nacimiento: `1991-02-18`.
- Género: Femenino.
- Teléfono: `0981111111`.
- Correo: `erojas@gmail.com`.
- Sin diferimientos.
- Historial:
  - 2026-04-02, completada, unidad `UN-2026-0402`.
  - 2025-08-19, completada, unidad `UN-2025-1510`.
- La maqueta indica 3 donaciones; falta 1 histórica para reproducir el total.

### 4.2 Pablo Estigarribia López

- Documento: `7222222`.
- Nacimiento: `1986-10-09`.
- Género: Masculino.
- Teléfono: `0991222222`.
- Correo: `pestigarribia@outlook.com`.
- Diferimiento temporal HRL por tatuaje:
  - Inicio: `2026-06-20`.
  - Fin mostrado: `2026-12-17`.
- Historial:
  - 2026-06-20, no apto.
  - 2025-12-18, completada, unidad `UN-2025-2410`.
- Revisiones de jefatura:
  - 10:30, pendiente.
  - 11:00, realizada.
- La maqueta indica 4 donaciones; faltan 3 históricas completadas.

### 4.3 Silvia Duarte Caballero

- Documento: `7333333`.
- Nacimiento: `1994-05-27`.
- Género: Femenino.
- Teléfono: `0972333333`.
- Correo: `sduarte@gmail.com`.
- Diferimiento temporal HRL por hemoglobina baja:
  - Inicio: `2025-09-02`.
  - Fin: `2025-12-01`.
  - Vencido para la fecha de referencia.
- Historial:
  - 2025-09-02, no apta.
  - 2025-03-11, completada, unidad `UN-2025-0311`.
- La maqueta indica 2 donaciones; falta 1 histórica completada.

### 4.4 Ramón Ortiz Franco

- Documento: `7444444`.
- Nacimiento: `1979-08-04`.
- Género: Masculino.
- Teléfono: `0983444444`.
- Correo: `rortiz@hotmail.com`.
- Diferimiento permanente HRL por serología reactiva:
  - Inicio: `2026-02-11`.
  - Sin fecha de fin.
- Historial:
  - 2026-02-11, no apto.
  - 2025-04-14, completada, unidad `UN-2025-0414`.
- Revisión de jefatura: 09:00, pendiente.
- La maqueta indica 6 donaciones; faltan 5 históricas completadas.

### 4.5 Natalia Pereira Soto

- Documento: `7555555`.
- Nacimiento: `1989-11-21`.
- Género: Femenino.
- Teléfono: `0994555555`.
- Correo: `npereira@gmail.com`.
- Diferimiento temporal externo:
  - Inicio: `2026-07-01`.
  - Fin: `2026-12-01`.
  - Institución: `Hospital Nacional de Itauguá`.
  - Causa mostrada: `Información no disponible`.
- Historial:
  - 2026-07-01, no apta, institución externa.
  - 2025-06-08, completada, unidad `UN-2025-0608`.

## 5. Solicitudes y extracciones de compatibilidad

Crear un usuario solicitante/paciente por cada fila, el tipo de sangre que se
defina para la prueba, una `solicitud` y su cita de
`Extraccion de compatibilidad`.

- Mirta Elisa Vera de González:
  - Documento `1234567`.
  - 2 unidades requeridas.
  - Fecha de creación `2026-09-09`.
  - Estado de maqueta pendiente; en el esquema usar `Publicada`.
  - Médico: Dr. Ramón Espínola.
  - Cita: 07:30, pendiente.
- Pedro Antonio Ruiz:
  - Documento `2345678`.
  - 1 unidad requerida y 1 asignada.
  - Fecha `2026-09-08`.
  - Estado `Completa`.
  - Médico: Dra. Liz Montiel.
  - Cita: 08:00, completada.
  - Atención: crear extracción, unidad y asignación.
- Rosa María Duarte:
  - Documento `3456789`.
  - 3 unidades requeridas.
  - Fecha `2026-09-07`.
  - Estado `Publicada`.
  - Médico: Dr. Carlos Mendoza.
  - Cita: 08:30, pendiente.
- Fulgencio Adorno Benítez:
  - Documento `4567890`.  
  - 1 unidad requerida.
  - Fecha `2026-09-06`.
  - Estado `Publicada`.
  - Médico: Dra. Patricia Acuña.
  - Cita: 09:00, pendiente.

Los documentos de Pedro, Rosa y Fulgencio coinciden con documentos de donantes
nominales. Como `usuario.documento` es único, el script debe decidir una de
estas opciones:

1. Reutilizar esos usuarios como solicitantes, aunque la maqueta los presente
   con nombres distintos.
2. Dar a los pacientes documentos sintéticos distintos.

Se recomienda la segunda opción para no cambiar los nombres de los escenarios
de donantes.

## 6. Revisiones y consejería

El esquema solo permite crear `citacion_consejeria` cuando existe un
`resultado_laboratorio` relacionado. Para las revisiones permanentes se debe
crear la cadena completa:

`cita completada → extraccion → unidad → resultado reactivo → registro de
diferimiento → citacion_consejeria`.

Escenarios:

- Diego Cabrera: pendiente, serología reactiva, permanente.
- Ramón Ortiz: pendiente, serología reactiva, permanente.
- Ana Patricia Ríos: pendiente, presión arterial elevada, temporal.
- Pablo Estigarribia: una pendiente y otra realizada, temporal.
- María Fernanda Acosta: ausente, hemoglobina baja, temporal.
- Julieta Rojas: pendiente, VIH, permanente.

Julieta no existe entre los donantes originales. Crear una usuaria independiente
con documento sintético `5485567`. No reutilizar el identificador de Ana.

Las revisiones temporales no encajan naturalmente en `citacion_consejeria`,
porque esa tabla exige un resultado de laboratorio. Deben quedar como
`registro_diferimiento` y, si corresponde, `derivacion`; no se debe fabricar un
resultado reactivo solo para poder mostrar una cita.

## 7. Datos necesarios para los informes

### 7.1 Donaciones

Objetivo del período 2026-09-01 a 2026-09-10:

- Donaciones/extracciones completadas: **87**.
- Por tipo:
  - Altruista: 54.
  - Reposición: 22.
  - Solidaria/solicitud: 8.
  - Diagnóstico: 3.
- Por género:
  - Femenino: 38.
  - Masculino: 49.
- Por rango de edad al 2026-09-10:
  - 18 a 25: 22.
  - 26 a 35: 31.
  - 36 a 45: 19.
  - 46 a 55: 11.
  - 56 a 65: 4.
- Colectas mensuales de 2026:
  - Enero: 112.
  - Febrero: 98.
  - Marzo: 124.
  - Abril: 103.
  - Mayo: 117.
  - Junio: 89.
  - Julio: 131.
  - Agosto: 108.
  - Septiembre: 87.

Para producir estos valores desde consultas reales, el seed deberá generar
usuarios sintéticos adicionales, sus citas completadas y sus extracciones. Los
15 donantes nominales no alcanzan para representar esos totales.

La fecha que debe gobernar el informe es `extraccion.fecha`. La cita no guarda
directamente la fecha de atención y su día se calcula a partir de una franja
semanal.

El tipo `Diagnóstico` no existe en el esquema. Cambiar por reposicion.

### 7.2 Diferimientos

- Personas/citas aptas: 67.
- Personas/citas diferidas o no aptas: 20.
- Clasificación principal:
  - Temporales: 14.
  - Permanentes: 6.
- Registros por motivo:
  - Hemoglobina baja: 7.
  - Presión arterial fuera de rango: 5.
  - Temperatura elevada: 3.
  - Infección activa: 3.
  - Medicación incompatible: 2.
  - Peso insuficiente: 2.


Los motivos suman **23 registros**, mientras que la maqueta muestra **20
personas diferidas**. Es posible reproducirlo haciendo que 3 de las 20 personas
tengan dos causas registradas. El informe debe contar personas/citas distintas
para el KPI y filas de `registro_diferimiento` para el detalle por motivo.

Antes del seed hay que asegurar estas equivalencias de catálogo:

- `Temperatura elevada` puede usar `Cuadro febril o gripal`.
- `Infección activa` puede usar `Enfermedad infecciosa reciente`.
- `Medicación incompatible` puede usar `Tratamiento con antibióticos`.
- `Peso insuficiente` puede usar `Peso inferior al mínimo`.
- `Otro` no existe en el catálogo y debe resolverse con una causa existente o
  agregarse a `catalogos.sql` mediante una decisión explícita.

### 7.3 Serología e inmunohematología

- Volúmenes procesados: 87.
- Reactivos: 4.
- No reactivos: 83.
- En investigación: 2.
- Detalle visual de marcadores reactivos:
  - VIH 1/2: 10.
  - HBsAg (Hepatitis B): 8.
  - Anti-HCV (Hepatitis C): 7.
  - VDRL (Sífilis): 6.
  - Chagas (T. cruzi): 5.
  - HTLV I/II: 4.
  - Anti-HBc (Hepatitis B): 3.
  - HBsAg(Hepatitis B): 2.
  - CMV: 2.
  - Anti-HCV(Hepatitis C): 1.

Limitaciones del esquema:

- `resultado_laboratorio` solo admite `Reactivo` o `No reactivo`; no admite
  `En investigación`.
- Solo existe un resultado por unidad.
- No existe una tabla o columna de marcador serológico.
- El detalle de marcadores suma 48, aunque el KPI indica 4 volúmenes reactivos.

Por lo tanto, el seed puede crear 87 resultados binarios, 4 reactivos y 83 no
reactivos, pero no puede producir el estado `En investigación` ni el detalle de
marcadores. Esas dos visualizaciones deben seguir como series de presentación
o requieren una ampliación acordada del esquema.

### 7.4 Hemovigilancia

- Extracciones: 87.
- Eventos adversos: 20.
- Por momento:
  - Durante: 12.
  - Posterior: 8.
- Por severidad:
  - Leve: 12.
  - Moderado: 6.
  - Grave: 2.
- Por tipo:
  - Hematoma: 4.
  - Febril: 3.
  - Lipotimia: 3.
  - Alérgica: 2.
  - Náuseas: 2.
  - Dolor local: 2.
  - Hipotensión: 1.
  - Hormigueo: 1.
  - Vasovagal: 1.
  - Otro: 1.

El esquema no tiene una tabla de eventos adversos, ni campos estructurados para
momento y severidad. `extraccion.observacion` puede contener texto, pero no
permite generar el informe completo de forma confiable. El controlador actual
solo detecta la palabra `lipotimia`.

El seed puede colocar descripciones en 20 observaciones para demostración, pero
los gráficos completos deben permanecer simulados mientras no exista una
estructura específica.

### 7.5 Stock y solicitudes

Stock actual por grupo sanguíneo:

- O+: 21.
- A+: 10.
- B+: 4.
- AB+: 1.
- O-: 3.
- A-: 2.
- B-: 1.
- AB-: 0.
- Total representable en el esquema actual: **42 unidades de sangre total en
  stock**.

Datos adicionales de la maqueta React:

- Concentrado de glóbulos rojos: 42.
- Plasma fresco congelado: 18.
- Plaquetas: 9.
- Total de hemocomponentes: 69.

El esquema tiene el `CHECK componente = 'sangre_total'`. Por eso el seed solo
puede reproducir las 42 unidades por grupo, no las 69 unidades separadas por
hemocomponente.

Otros indicadores:

- Unidades próximas a vencer: 6.
  - Crear 6 unidades `En stock` con `fecha_vencimiento` posterior a
    `2026-09-10` y dentro del umbral que defina el informe.
- Solicitudes atendidas: 28.
- Solicitudes pendientes: 5.
- Total de solicitudes: 33.
  - Atendidas: estado `Completa`.
  - Pendientes: estado `Publicada`, con consentimiento verdadero y unidades
    asignadas menores que las requeridas.
- Evolución mensual visual del volumen:
  - Enero: 58.
  - Febrero: 63.
  - Marzo: 71.
  - Abril: 66.
  - Mayo: 74.
  - Junio: 61.
  - Julio: 78.
  - Agosto: 72.
  - Septiembre: 69.

La evolución termina en 69, pero el stock por grupos suma 42. Además, la tabla
`unidad` solo representa sangre total. Esa serie no puede derivarse de una
instantánea actual; para calcularla habría que reconstruir el saldo histórico
con `transicion_estado` y acordar si mide bolsas o hemocomponentes. Hasta
resolverlo debe continuar como serie de presentación.

## 8. Orden recomendado de inserción

1. Verificar catálogos: roles, tipos de sangre, mediciones, diferimientos,
   preguntas y horarios.
2. Insertar o localizar personal de turno, enfermería y jefatura.
3. Insertar donantes nominales, teléfonos, correos y roles.
4. Insertar usuarios sintéticos requeridos por los informes.
5. Insertar solicitantes y solicitudes.
6. Insertar citas históricas y del día.
7. Insertar mediciones para los casos aptos/no aptos cuando correspondan.
8. Insertar registros de diferimiento.
9. Insertar extracciones de citas completadas.
10. Insertar unidades.
11. Insertar resultados de laboratorio.
12. Insertar transiciones de estado.
13. Insertar asignaciones a solicitudes.
14. Insertar citaciones de consejería y derivaciones posibles.
15. Ejecutar consultas de control y confirmar los totales.

## 9. Controles mínimos posteriores

El futuro script debe incluir consultas que permitan comprobar:

- 15 donantes nominales, más Julieta y los usuarios sintéticos.
- 10 citas nominales de donación del día.
- 5 escenarios espontáneos sin cita activa inicial.
- 4 solicitudes nominales de compatibilidad.
- 87 extracciones entre 2026-09-01 y 2026-09-10.
- 54/22/8 por los tres tipos admitidos y una decisión documentada para las 3
  de diagnóstico.
- 38 donantes femeninos y 49 masculinos dentro del conjunto de 87.
- Distribución 22/31/19/11/4 por edades.
- 20 citas no aptas y 23 registros de diferimiento.
- 14 diferimientos temporales y 6 permanentes como clasificación principal.
- 87 resultados de laboratorio: 4 reactivos y 83 no reactivos.
- 42 unidades de sangre total en stock con la distribución ABO/Rh indicada.
- 6 unidades próximas a vencer.
- 28 solicitudes completas y 5 publicadas.

## 10. Decisiones 

1. Los totales históricos de cada donante deben completarse con citas
   sintéticas no visibles.
3. Qué causa del catálogo usar para `Otro`.
4. Reemplazar los documentos duplicados entre pacientes y donantes por unos nuevos.
5. Si los indicadores no soportados por el esquema deben seguir simulados:
   marcadores serológicos, investigación, hemovigilancia estructurada,
   hemocomponentes y evolución histórica del stock.
6. Qué umbral define “próximo a vencer”.

