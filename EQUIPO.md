# Cómo trabajamos las dos

Documento de acuerdo entre **Johana** (portal del donante) y **Jazmín** (panel de administración).

La idea de fondo: **no nos conectamos por código, nos conectamos por la base de
datos.** Cuando el portal registra un usuario, escribe en la tabla `usuario`.
El panel de administración lee `usuario`. Ninguna llama a las funciones de la
otra. El contrato entre nosotras son **las tablas y sus columnas**, nada más.

Eso significa que el riesgo real no está en las pantallas, está en la base.
Todo lo que sigue apunta a eso.

---

## 1. Quién toca qué

| Carpeta | Dueña | Qué va |
|---|---|---|
| `app/routes/portal/` | Johana | Rutas del portal |
| `app/controllers/portal/` | Johana | Lógica del portal |
| `app/views/portal/` | Johana | Plantillas del portal |
| `app/static/css/portal.css` | Johana | Estilos del portal |
| `app/views/portal/layout.html` | Johana | Cabecera y pie del portal |
| `app/routes/admin/` | Jazmín | Rutas del panel |
| `app/controllers/admin/` | Jazmín | Lógica del panel |
| `app/views/admin/` | Jazmín | Plantillas del panel |
| `app/static/css/admin.css` | Jazmín | Estilos del panel |
| `app/views/admin/layout.html` | Jazmín | Cabecera y pie del panel |

**Compartido (se cambia de a dos, nunca a solas):**

| Archivo | Por qué |
|---|---|
| `database/schema.sql` | Estructura de la base. Ver la sección 3. |
| `database/migraciones/` | Los cambios de esquema. Ver la sección 3. |
| `app/models/` | El mapeo de las tablas. Las dos leemos las mismas. |
| `app/controllers/sesion.py` | Login y permisos, los usan los dos módulos |
| `app/config.py`, `app/__init__.py` | Arranque de la aplicación |
| `requirements.txt` | Dependencias |

Si una necesita cambiar algo de la lista compartida: **se avisa antes**, va en
su propia rama y la otra lo revisa antes de mezclarlo.

### Lo que NO hay que tocar del archivo de la otra

Ninguna edita una plantilla, ruta o controlador del módulo de la otra. Si el
portal necesita algo del admin (o al revés), se resuelve **consultando la base**,
no importando su código. Ejemplo: el portal no le pide al admin "dame las citas
de hoy"; hace su propio `SELECT` sobre `cita`.

---

## 2. Agregar una pantalla sin pisarse

Los blueprints se registran solos. `app/routes/__init__.py` recorre las
carpetas `portal/` y `admin/` y registra lo que encuentra.

Para agregar una pantalla:

1. Crear `app/routes/<tu-modulo>/mi_pantalla.py`
2. Definir ahí un Blueprint:
   ```python
   from flask import Blueprint
   mi_bp = Blueprint("mi_pantalla", __name__, url_prefix="/mi-pantalla")
   ```
3. Listo.

**No se edita ningún archivo compartido para esto.** Cada pantalla nueva es un
archivo nuevo, y dos archivos nuevos distintos nunca dan conflicto en Git.

Una sola regla: el nombre del blueprint (`"mi_pantalla"`) tiene que ser único
en todo el proyecto. Si las dos usamos `"reportes"`, una de las dos no se
registra. Para evitarlo, el admin usa el prefijo `admin_`:
`admin_reportes`, `admin_donantes`, `admin_stock`.

---

## 3. Cambios en la base de datos (lo más delicado)

**El problema:** `schema.sql` solo se ejecuta cuando la base está vacía. Si
Jazmín agrega una columna hoy y Johana hace `git pull` mañana, la base de
Johana **no se entera nunca**. El código nuevo va a fallar con
`column does not exist` y va a perder una tarde buscando por qué.

**La solución:** cada cambio del esquema es un archivo numerado en
`database/migraciones/`.

### Para hacer un cambio en la base

1. Crear `database/migraciones/NNN_descripcion.sql` con el número siguiente
   libre (hay una plantilla en `000_ejemplo.sql.txt`).
2. Aplicarlo en tu base:
   ```
   python database/migrar.py
   ```
3. Si la migración toca una tabla que ya tiene modelo, actualizar el modelo en
   `app/models/` **en el mismo commit**. Después:
   ```
   python database/verificar_modelos.py
   ```
4. Avisarle a la otra.

### Reglas de las migraciones

- **Una migración ya subida no se edita nunca.** Si salió mal, se corrige con
  una migración nueva. Editarla dejaría las dos bases en estados distintos sin
  que se note.
- Tiene que poder aplicarse sobre una base **con datos**. Nada de `DROP TABLE`
  de tablas con información.
- Una columna `NOT NULL` nueva sobre una tabla con filas necesita `DEFAULT`, o
  el `ALTER` falla.
- `schema.sql` se actualiza también, para que quien clone el repo de cero
  obtenga la estructura final. Pero **la migración es lo que manda** para las
  bases que ya existen.

### Al hacer git pull, siempre

```
git pull
python database/migrar.py
```

Si te olvidás, la aplicación te avisa al arrancar:
`ATENCIÓN: hay N migración/es sin aplicar en tu base`.

---

## 4. Ramas y commits

`main` queda siempre funcionando. Nadie trabaja directo sobre `main`.

### Empezar algo nuevo

```
git checkout main
git pull
git checkout -b johana/pantalla-donar
```

Prefijo con tu nombre: `johana/...` y `jazmin/...`. Así de un vistazo se sabe
de quién es cada rama.

Una rama por pantalla o por tema, no una rama gigante que dure tres semanas.
Cuanto más corta, menos conflictos.

### Mientras trabajás

Commits chicos y seguido, no uno enorme al final:

```
git add .
git commit -m "Agregar formulario de agendamiento"
```

El mensaje dice **qué cambió**, no "avance" ni "cambios". Si el commit toca la
base, que se note: `"Agregar fecha_cita a cita (migración 001)"`.

### Traer lo nuevo de main

Al menos una vez por día:

```
git checkout main
git pull
git checkout johana/mi-rama
git merge main
python database/migrar.py
```

Esto es lo que evita el "se me pisó todo": si traés los cambios de la otra
todos los días, los conflictos son de tres líneas. Si esperás dos semanas, son
de trescientas.

### Cuando terminás

```
git push -u origin johana/mi-rama
```

Y en GitHub: **Pull request** hacia `main`. La otra lo mira antes de mezclar.
No es burocracia: es la forma de que ninguna se entere de un cambio grande
cuando ya está adentro.

### Si aparece un conflicto

Si las dos tocaron el mismo archivo, Git marca el conflicto y no mezcla nada.
No hay nada roto ni perdido: se abre el archivo, se decide qué queda, se borran
las marcas `<<<<<<<` y `>>>>>>>`, y se commitea. Si el archivo es de las dos
(`app/models/`, por ejemplo), lo resolvemos juntas.

---

## 5. Lo que hay que decidir entre las dos

Estos son todos los cambios de esquema que pidió el portal. Los de arriba ya
están hechos y versionados; los de abajo tocan al panel, así que la decisión
es de las dos.

### Ya aplicado

| Migración | Qué cambia | Por qué |
|---|---|---|
| **001** | Agrega `cita.fecha_cita` y un trigger que exige que la fecha caiga en el día de semana de su franja. | La tabla no guardaba el día del turno, solo la franja semanal. Sin eso no hay agenda posible ni en el portal ni en el panel. |
| **002** | `cita.id_personal` pasa a nullable. Suma controles de cupo por franja y fecha, una sola cita activa por donante, y bloqueo con diferimiento vigente o fecha pasada. | Al reservar por el portal todavía no hay personal asignado, y como quien agenda ya no es alguien del banco mirando la agenda, las reglas las tiene que hacer cumplir la base. |
| **003** | Tabla nueva `recuperacion_contrasena`. | El "¿Olvidaste tu contraseña?" necesita guardar un token temporal. **No toca ninguna tabla existente y nadie más la usa**, pero igual hay que correr `migrar.py` o la pantalla falla. |
| **004** | `pregunta` gana `seccion`, `orden`, `alerta_si`, `pide_detalle`, `etiqueta_detalle`, `nota` y `activa`. El CHECK de `notificacion.tipo` acepta además `CUESTIONARIO_PREVIO`. | El cuestionario oficial del banco son 36 preguntas en tres bloques y numeradas; sin dónde guardar el bloque y el número, la pantalla las muestra en cualquier orden. `alerta_si` dice cuál de las dos respuestas mira el personal, porque no siempre es el "sí". **Todo suma: ninguna columna cambia de tipo y el CHECK se amplía, no se achica.** Las preguntas de prueba que había quedan marcadas `activa = false`, no se borran. |

### Lo que falta decidir entre las dos

| # | Cambio | Por qué hace falta | A quién afecta |
|---|---|---|---|
| 1 | `correo.verificado boolean NOT NULL DEFAULT false` | **RN17** pide que el donante inicie sesión solo con correo verificado. Hoy no hay dónde guardar ese estado, así que la regla no se puede cumplir. | Portal: registro y login. Panel: ver quién confirmó. |
| 2 | `notificacion.leido boolean NOT NULL DEFAULT false` | Sin esto no se puede marcar una notificación como vista ni mostrar el aviso en la campana. | Portal: listarlas. Panel: saber si el donante vio el recordatorio. |
| 3 | `buzon.id_usuario` a nullable | El prototipo promete que el mensaje es anónimo, y hoy la columna es NOT NULL. | Panel: tiene que tolerar mensajes sin remitente. |
| 4 | `buzon.tipo varchar(20)` con CHECK | No hay columna para Sugerencia / Comentario / Reclamo. Hoy el tipo va al principio del texto (`[Sugerencia] ...`), que funciona pero impide filtrar y contar. | Panel: leer y clasificar. |

Los puntos 1 y 2 son una columna booleana con default: riesgo cero y les sirven
a las dos. Conviene acordarlos primero y hacerlos en una sola migración.

Los del buzón son los que más cambian lo que recibe el panel: hasta que se
decidan, el portal sigue guardando el tipo dentro del texto y pidiendo sesión
para escribir.

### Lo que Jazmín tiene que correr después del pull

```
python database/migrar.py            aplica 001 a 004
python database/cargar_catalogos.py  carga las 36 preguntas del cuestionario
```

El segundo hace falta esta vez: la migración agrega las columnas, pero las
preguntas del formulario son datos y entran por el catálogo. Después de
correrlo, `pregunta` tiene 49 filas (36 del cuestionario oficial, 5 de la
Parte B del check-in y 8 de prueba que quedan inactivas).

### Lo que NO necesita cambios

Es fácil pedir de más, así que conviene dejarlo escrito: **última donación,
donaciones realizadas, fecha estimada de habilitación** (RF30) e **historial de
citas** se calculan a partir de las citas completadas y el género del donante.
No hacen falta columnas nuevas.

---

## 6. Al empezar a trabajar, cada vez

En PowerShell:

```powershell
cd C:\Users\johan\gestion_banco_de_sangre; .\venv\Scripts\Activate.ps1
git pull
python database/migrar.py
python run.py
```

El prompt tiene que decir `(venv) PS C:\...\gestion_banco_de_sangre>`. Si dice
otra cosa, estás en la carpeta equivocada y nada va a funcionar.

---

## 7. Lo que no se sube al repositorio

El `.gitignore` excluye `.env` (tiene contraseñas) y `*.sql`.

**Eso último es un problema:** `database/schema.sql` y `database/catalogos.sql`
no se suben, así que quien clone el repo no los recibe y la aplicación no
arranca. Conviene agregar las excepciones:

```
*.sql
!database/schema.sql
!database/catalogos.sql
!database/migraciones/*.sql
```

Sin la tercera línea, **las migraciones tampoco se suben** y todo el mecanismo
de la sección 3 no sirve de nada.
