# Listado básico de pruebas funcionales de QA

Pruebas manuales esenciales del prototipo. Cada caso está respaldado por un caso de uso (`Sistema Donante.txt`, `Sistema Enfermero.txt`, `Sistema Jefatura.txt`) o por una regla ya documentada (triangulación resumida en `CONTEXT.md`, RN y `flujo_unidad.md`).

El resultado de laboratorio no se elige en pantalla: después de guardar la extracción, la simulación deja la unidad en stock o descartada. No se exige una proporción.

## No cerrar como defecto

Estas diferencias están en las fuentes. No hay un resultado esperado único.

| Tema | Qué dicen las fuentes |
| --- | --- |
| Verificación de correo | El caso de uso del donante incluye verificación al registrarse (RF24). El modelo no tiene código de un solo uso (C15). El alta actual pide correo válido y consentimiento, y deja iniciar sesión. |
| Información del portal | El diagrama la ubica después del ingreso. M11 y la implementación publican requisitos y procedimiento sin sesión. |
| Quién registra la derivación externa | El diagrama del donante la asigna a jefatura. RF32 y el diagrama de enfermería la asignan al licenciado. La pantalla está en la ficha de enfermería. |
| Consejería | El diagrama del donante dice que el sistema genera la cita. RF31 y el código avisan sin causa y la cita nace cuando el donante reserva. |
| Diferimiento temporal de control | El diagrama de enfermería permite evaluación y extracción de control. La ficha impide extraer mientras haya un diferimiento vigente. |
| Orientación por diferimiento permanente | El diagrama pide registrar la orientación. La ficha muestra la alerta y bloquea la extracción; no hay un registro aparte de esa orientación. |
| Volumen de la solicitud | El diagrama acumula volúmenes. El cierre usa unidades requeridas y asignadas. |
| Informe de consejería | El diagrama de enfermería lo nombra. Las pestañas implementadas son donaciones, diferimientos, serología, hemovigilancia (solo enfermería) y stock. |
| Estados de la unidad | El diagrama habla de cuarentena y liberada. El modelo usa En laboratorio y En stock (C12). |
| Panel de jefatura | El diagrama pide donaciones, diferimientos y stock. El inicio lista citaciones; esos indicadores están en informes. |
| Sábado | RN06 no agenda en fin de semana. El catálogo carga sábado (C23). |

## Donante

| ID | Prueba | Esperado | Respaldo |
| --- | --- | --- | --- |
| D01 | Registrar con documento, nombre, apellido, nacimiento, género, correo, contraseña y consentimiento de privacidad. Iniciar sesión. | La cuenta queda creada y entra al portal. | Donante: registro e inicio. RF03, RF04. |
| D02 | Registrar sin consentimiento, con menos de 18 años, documento duplicado o correo ya usado. | No se crea la cuenta y se informa el motivo. | Mismas fuentes. El tope de edad en línea es el del registro implementado (hasta 65). |
| D03 | Entrar con contraseña incorrecta. | No abre sesión. | RNF04, RNF05. |
| D04 | Con sesión, abrir la información institucional. | Se ven requisitos, horarios y procedimiento. | Donante: informarse. RF22. |
| D05 | Elegir un horario con cupo, ver los requisitos, confirmar y completar la Parte A. | Queda una cita confirmada y el donante ve la confirmación. | Donante: donar. RF01, RF08. |
| D06 | Intentar agendar con un diferimiento vigente. | No reserva. El aviso pide comunicarse con el banco y no dice la causa. | Donante. RF09, RN04. |
| D07 | Con una cita activa, intentar crear otra. | No crea otra. Remite a gestionar la vigente. | RN05. El diagrama no fija el máximo (C9). |
| D08 | Gestionar cita sin ninguna vigente. | Informa que no hay citas vigentes. | Donante: gestionar cita. |
| D09 | Reprogramar a una franja libre y confirmar. | La cita muestra la nueva fecha y horario. | Donante: reprogramar. RF08. |
| D10 | Reprogramar cuando la franja elegida no tiene cupo. | Informa que no hay disponibilidad y la cita no cambia. | Donante. RN06. |
| D11 | Cancelar y no confirmar; luego cancelar y confirmar. | La primera vez la cita sigue. La segunda queda cancelada y se avisa. | Donante: cancelar. RF08. |
| D12 | Abrir el panel de enfermería o de jefatura con la cuenta del donante. | No entra. | RNF05. Roles `DONANTE`, `ENFERMERIA`, `JEFATURA`. |

## Enfermería

| ID | Prueba | Esperado | Respaldo |
| --- | --- | --- | --- |
| E01 | Ingresar con correo institucional y contraseña. Repetir con datos incorrectos. | El válido abre el panel. El inválido no. | Enfermero: ingreso. RN17. |
| E02 | Abrir la lista del día, la ficha, revisar la Parte A, cargar la Parte B, registrar signos dentro de rango y registrar la extracción. | La unidad queda en laboratorio, con código, y el donante recibe el agradecimiento. No hay pantalla de laboratorio. | Enfermero: atender con cita. Donante: extracción. RF26, RF27, RF33. |
| E03 | En la evaluación, cargar un signo fuera de rango y confirmar el diferimiento. | No se extrae. La cita queda no apta y el diferimiento queda registrado. `apto` no se tipea a mano. | Enfermero: rechaza. RN01, RN10. |
| E04 | En la Parte B, diferir con una causa del catálogo. | La cita queda no apta. No sigue a extracción. | Enfermero: registrar diferimiento. RF02, RF29. |
| E05 | Abrir la ficha de un donante con diferimiento permanente vigente. | Muestra la alerta, indica que no puede extraerse y no habilita la extracción. | Enfermero: permanente. RF09. |
| E06 | Abrir la ficha con diferimiento vigente de otro establecimiento y registrar la derivación. | La evaluación queda desactivada. La derivación queda registrada por enfermería. | Enfermero: antecedente externo. RF32. |
| E07 | Buscar un documento que no existe. Luego un donante sin cita, sin cupo hoy, y otro con cupo. | No crea una cuenta. Sin cupo, informa que no hay turno. Con cupo, asigna el turno y deja completar la Parte A. | Donante: espontáneo. Enfermero: sin cita. |
| E08 | Intentar abrir la atención sobre la propia cuenta del licenciado. | No abre la atención. | RN02. |
| E09 | En informes, filtrar un período, ver cada pestaña y exportar. | Genera donaciones, diferimientos, serología, hemovigilancia y stock, y descarga el CSV del período. | Enfermero: informes. RF20, RF21. |

## Jefatura

| ID | Prueba | Esperado | Respaldo |
| --- | --- | --- | --- |
| J01 | Con una citación pendiente o confirmada cuyo día es hoy o anterior, registrar realizada y, en otra, ausente. | El estado pasa a realizada o ausente y queda el personal que cerró. | Jefatura: citaciones. RF31. |
| J02 | Intentar cerrar una citación de un día futuro, o confirmarla o cancelarla desde jefatura. | No cambia el estado. La confirmación, la reprogramación y la cancelación son del donante. | RF31. Jefatura: no agenda ni confirma. |
| J03 | Filtrar informes, recorrer las pestañas y exportar. | Hay donaciones, diferimientos, serología y stock. No hay hemovigilancia. | Jefatura: informes. RF20. |
| J04 | Entrar a jefatura con enfermería y al revés. | Cada rol vuelve a su propio inicio. | RNF05. |

## Laboratorio simulado, solicitud y consejería

| ID | Prueba | Esperado | Respaldo |
| --- | --- | --- | --- |
| L01 | Después de una extracción, esperar el resultado simulado. | No reactivo: la unidad pasa a stock. Reactivo: queda descartada, con diferimiento permanente, y el donante recibe un aviso genérico, sin resultado ni causa. | Donante: laboratorio y resultado reactivo. `flujo_unidad.md`. RN14. |
| L02 | Si la cita estaba ligada a una solicitud abierta, compatible y con cupo, y el resultado es no reactivo. | La unidad queda asignada, la solicitud suma una unidad y, al cubrir las pedidas, pasa a completa. | Donante: solicitud y asignación. RN08, RN20. |
| L03 | Con aviso de consejería, el donante elige horario, confirma la reserva, reprograma, cancela y vuelve a reservar. El día de la cita, confirma la asistencia. | La cita la crea el donante. Cancelar permite reservar de nuevo la misma consejería. Confirmar solo es posible ese día. El aviso no revela la causa. | RF31. |
| L04 | Repetir L03 eligiendo una franja de consejería ya llena. | No reserva e informa que no hay cupo. | RN06. |
