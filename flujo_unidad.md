# UNIDAD

Representa una unidad de sangre total. **Una extracción = una unidad.** En el prototipo no se realiza fraccionamiento en hemocomponentes.

## 1. Estructura de la tabla `UNIDAD`

| Atributo | Tipo | Nulo | Restricción | Descripción |
|---|---|---|---|---|
| `id_unidad` | INTEGER | No | PK | Identificador de la unidad. |
| `id_extraccion` | INTEGER | No | UK, FK → `EXTRACCION` | Extracción de origen. |
| `id_donante` | INTEGER | No | FK → `USUARIO` | Donante que realizó la donación. Permite la trazabilidad directa. |
| `id_solicitud` | INTEGER | Sí | FK → `SOLICITUD` | Solicitud a la que se asigna la unidad, únicamente después del análisis de laboratorio, si la solicitud continúa abierta y existe compatibilidad. |
| `codigo` | VARCHAR(40) | No | UK | Identificador único de la unidad, igual o derivado de `codigo_unico`. |
| `id_tipo_sangre` | INTEGER | Sí | FK → `TIPO_SANGRE` | Tipo de sangre determinado por el laboratorio. |
| `componente` | VARCHAR(20) | No | DEFAULT `sangre_total` | Componente disponible. El único valor permitido en el prototipo es `sangre_total`. |
| `estado` | VARCHAR(20) | No | CK | Estado actual de la unidad. Ver transiciones permitidas. |
| `fecha_vencimiento` | DATE | Sí | — | Fecha de vencimiento calculada según la vida útil parametrizada. Se utilizan datos de prueba. |

## 2. Estructura de la tabla `TRANSICION_ESTADO`

Registra la bitácora de cambios de estado de una unidad. Los registros no se eliminan ni se sobrescriben, conforme al RF35.

| Atributo | Tipo | Nulo | Restricción | Descripción |
|---|---|---|---|---|
| `id_transicion` | INTEGER | No | PK | Identificador de la transición. |
| `id_unidad` | INTEGER | No | FK → `UNIDAD` | Unidad cuyo estado cambió. |
| `id_personal` | INTEGER | No | FK → `USUARIO` | Personal responsable del cambio de estado. |
| `estado_origen` | VARCHAR(20) | No | — | Estado anterior de la unidad. |
| `estado_destino` | VARCHAR(20) | No | — | Nuevo estado de la unidad. |
| `motivo` | TEXT | Sí | — | Motivo del cambio. Es obligatorio cuando la unidad se descarta. |
| `fecha` | TIMESTAMP | No | — | Fecha y hora en que se registró la transición. |

## 3. Estructura de la tabla `RESULTADO_LABORATORIO`

Registra el resultado sintético del análisis de una unidad, incluyendo su fecha, tipificación sanguínea y, si el resultado es reactivo, el diferimiento correspondiente.

| Atributo | Tipo | Nulo | Restricción | Descripción |
|---|---|---|---|---|
| `id_resultado` | INTEGER | No | PK | Identificador del resultado. |
| `id_unidad` | INTEGER | No | UK, FK → `UNIDAD` | Unidad analizada. Solo se permite un resultado por unidad. |
| `id_diferimiento` | INTEGER | Sí | FK → `DIFERIMIENTO` | Causa de diferimiento del catálogo asociada al resultado reactivo. |
| `id_registro_diferimiento` | INTEGER | Sí | FK → `REGISTRO_DIFERIMIENTO` | Registro del diferimiento permanente confirmado para el donante. |
| `id_tipo_sangre` | INTEGER | No | FK → `TIPO_SANGRE` | Tipo de sangre determinado por el laboratorio. Se copia al perfil del donante y a la unidad. |
| `resultado` | VARCHAR(20) | No | CK | Resultado del análisis: `No reactivo` o `Reactivo`. |
| `fecha` | TIMESTAMP | No | — | Fecha y hora de creación del resultado. |

### 3.1. Comportamiento según el resultado

**Resultado no reactivo:**

- La unidad pasa al estado `En stock`.
- Se registra la tipificación sanguínea.
- El tipo de sangre se actualiza en el perfil del donante y en la unidad.
- La unidad queda disponible para una posible asignación, siempre que cumpla las condiciones correspondientes.

**Resultado reactivo:**

- La unidad pasa al estado `Descartada`.
- Se registra obligatoriamente el motivo del descarte.
- Se crea un `REGISTRO_DIFERIMIENTO` permanente para el donante.
- Se genera una `CITACION_CONSEJERIA` para el seguimiento correspondiente.
- La unidad no puede ingresar al stock ni asignarse a una solicitud.

## 4. Transiciones permitidas de `UNIDAD`

Los cambios de estado deben respetar las transiciones definidas en la siguiente tabla.

| Estado de origen | Estado de destino | Responsable | Condición |
|---|---|---|---|
| Alta | `Registrada` | Enfermería | Se registra la extracción y se crea la unidad. |
| `Registrada` | `En laboratorio` | Enfermería / Sistema | Transición automática al crear la unidad. |
| `En laboratorio` | `En stock` | Laboratorio | El resultado es no reactivo y se registra la tipificación sanguínea. |
| `En laboratorio` | `Descartada` | Laboratorio | El resultado es reactivo. Se requiere motivo de descarte, diferimiento permanente y citación a consejería. |
| `En stock` | `Asignada` | Laboratorio | Existe una solicitud abierta, compatibilidad ABO/Rh y cupo disponible. Se registra `UNIDAD.id_solicitud` y la correspondiente `ASIGNACION`. |
| `En stock` | `Vencida` | Sistema (datos de prueba) | Se supera la fecha de vencimiento. |
| `Asignada` | `Utilizada` | Enfermería | Se registra el uso de la unidad asignada. |
| `Asignada` | `Vencida` | Sistema (datos de prueba) | La unidad vence después de haber sido asignada. |

### 4.1. Consideraciones

- Cada cambio de estado debe registrarse en `TRANSICION_ESTADO`.
- La bitácora debe conservar el estado de origen, el estado de destino, el responsable, la fecha y el motivo cuando corresponda.
- La asignación solo puede realizarse después de obtener un resultado no reactivo.
- Una unidad descartada no puede volver al stock.
- Los vencimientos se simulan con datos de prueba; no representan necesariamente vencimientos reales.
- No se permite fraccionar una unidad de sangre total en hemocomponentes dentro del prototipo.

## 5. Estructura de la tabla `DIFERIMIENTO`

Catálogo de causas de diferimiento definidas por el protocolo. Cada causa tiene un nombre, un tipo (temporal o permanente) y, cuando corresponda, una cantidad de días de rehabilitación. La causa se selecciona del catálogo y no se escribe manualmente en cada registro.

Conforme al RF30, `REGISTRO_DIFERIMIENTO.fecha_fin` se calcula como `fecha_inicio + dias_rehabilitacion`. Si el diferimiento es permanente, `fecha_fin` es nula.

| Atributo | Tipo | Nulo | Restricción | Descripción |
|---|---|---|---|---|
| `id_diferimiento` | INTEGER | No | PK | Identificador del diferimiento. |
| `nombre` | VARCHAR(120) | No | UK | Nombre de la causa. Ejemplos: hemoglobina baja, tatuaje reciente o serología reactiva. |
| `tipo` | VARCHAR(20) | No | CK | Tipo de diferimiento: `Temporal` o `Permanente`. |
| `dias_rehabilitacion` | INTEGER | Sí | CHECK (>= 0) | Cantidad de días hasta la rehabilitación aproximada. Es nulo si el diferimiento es permanente y se utiliza para calcular `REGISTRO_DIFERIMIENTO.fecha_fin`. |

## 6. Estructura de la tabla `REGISTRO_DIFERIMIENTO`

Registra la causa de diferimiento aplicada a un donante. Representa un hecho clínico que puede interrumpir el flujo de donación mientras se encuentre vigente, conforme a los RF09 y RF30.

| Atributo | Tipo | Nulo | Restricción | Descripción |
|---|---|---|---|---|
| `id_registro` | INTEGER | No | PK | Identificador del registro de diferimiento. |
| `id_donante` | INTEGER | No | FK → `USUARIO` | Donante al que se aplica el diferimiento. |
| `id_diferimiento` | INTEGER | No | FK → `DIFERIMIENTO` | Causa seleccionada del catálogo de diferimientos. |
| `id_cita` | INTEGER | Sí | FK → `CITA` | Cita o etapa del flujo de donación en la que se identificó el diferimiento. |
| `id_personal` | INTEGER | Sí | FK → `USUARIO` | Personal que identificó el diferimiento. Es nulo cuando lo genera automáticamente el sistema, por ejemplo, mediante el cuestionario o el laboratorio. |
| `origen` | VARCHAR(30) | No | CK | Origen del diferimiento: `CUESTIONARIO_SISTEMA`, `CUESTIONARIO_PERSONAL`, `MEDICION` o `LABORATORIO`. |
| `institucion_diagnostico` | VARCHAR(120) | No | — | Institución donde se diagnosticó la causa: este banco de sangre u otra institución. Se utiliza información simulada. |
| `fecha_inicio` | DATE | No | — | Fecha a partir de la cual se aplica el diferimiento. |
| `fecha_fin` | DATE | Sí | — | Fecha aproximada de rehabilitación, calculada como `fecha_inicio + dias_rehabilitacion`. Es nula para los diferimientos permanentes. |

### 6.1. Reglas de negocio

- Las causas de diferimiento deben seleccionarse de la tabla `DIFERIMIENTO`; no se ingresan manualmente en cada registro.
- Los diferimientos temporales deben tener una cantidad de días de rehabilitación definida en el catálogo.
- Los diferimientos permanentes deben tener `dias_rehabilitacion` y `fecha_fin` nulos.
- La fecha de finalización de un diferimiento temporal se calcula a partir de la fecha de inicio y los días de rehabilitación definidos en el catálogo.
- Un donante con un diferimiento vigente no puede continuar con el flujo de donación, conforme al RF09.
- Los diferimientos detectados por el cuestionario automático o por el laboratorio pueden registrarse sin un responsable humano en `id_personal`.
- Cuando el laboratorio detecta un resultado serológico reactivo, se debe registrar el diferimiento permanente correspondiente y generar la citación a consejería, según las reglas definidas para `RESULTADO_LABORATORIO`.