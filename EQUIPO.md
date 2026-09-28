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
| `database/schema.sql` | El modelo acordado. No se modifica. Ver la sección 3. |
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

## 3. La base de datos no se toca

`database/schema.sql` es el modelo que acordamos y **no se modifica**. Nada
de columnas nuevas, tablas nuevas ni triggers agregados por un lado.

Todo lo que el portal necesitaba y el esquema no daba se resolvió en el
código, sin tocar la estructura:

| Lo que hacía falta | Cómo se resolvió, sin tocar el esquema |
|---|---|
| Saber qué día es una cita | Se deduce: la franja dice el día de la semana y `fecha_hora_creacion` dice desde cuándo contar. La cuenta está en `app/calendario.py`. |
| Quién atiende (`cita.id_personal` es NOT NULL) | Un usuario de servicio, **«Personal de turno»** (documento `00000000`), que carga `catalogos.sql`. El panel lo reemplaza por la persona real en el mostrador. |
| Cupo, una sola cita activa, diferimiento vigente | Lo comprueba `app/controllers/portal/agenda.py` antes de grabar, tomando un bloqueo sobre la fila de la franja. |
| Guardar el token de recuperar contraseña | No se guarda: el enlace lleva un token firmado con la `SECRET_KEY`. Ver `app/controllers/portal/recuperacion.py`. |
| Bloque, orden y aclaraciones del cuestionario | En `app/controllers/portal/preguntas.py`, emparejado con la tabla por el enunciado. |
| Avisar el cuestionario sin un tipo nuevo de notificación | Usa `RECORDATORIO_CITA`, que el CHECK ya admite. |

### Si algún día hace falta cambiar el esquema

Se habla entre las dos **antes** de escribir una línea, y se cambia
`schema.sql`. Después, las dos corren:

```
python database/reconstruir.py
```

Eso borra la base y la vuelve a crear con la estructura y los catálogos.
**Se pierden los datos de prueba**, así que conviene hacerlo el mismo día
las dos y volver a crear las cuentas desde el portal.

### Al hacer git pull, siempre

```
git pull
python database/verificar_modelos.py
```

Si `verificar_modelos.py` se queja de una columna o una tabla, es que el
`schema.sql` cambió y tu base quedó vieja: corré `reconstruir.py`.

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
base, que se note: `"Cambiar schema.sql: agregar X a la tabla Y"`.

### Traer lo nuevo de main

Al menos una vez por día:

```
git checkout main
git pull
git checkout johana/mi-rama
git merge main
python database/verificar_modelos.py
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

## 5. Decisiones del modelo que conviene tener a mano

Ninguna de estas necesita cambiar la base. Están acá porque son las
preguntas que van a aparecer cuando alguien lea el código o el tribunal
pregunte.

### La agenda llega hasta 7 días

`horario_disponible` es un catálogo de franjas semanales: «Lunes, 07:00 a
07:30». Una cita apunta a una franja y se toma para **la próxima vez que
esa franja ocurre**. Por eso la agenda ofrece siete días: al octavo, dos
lunes distintos apuntarían a la misma franja y no habría cómo distinguirlos.

Reprogramar actualiza `fecha_hora_creacion`, porque es lo que ancla el
cálculo: es la fecha de alta de *esa* reserva.

### El cupo se cuenta sobre las citas activas

`cupo_atencion` es el máximo de citas **Pendiente o Confirmada** de esa
franja. Cuando el personal cierra una cita (Completada, Ausente, No apto),
su lugar queda libre para la semana siguiente. Es lo que hace que un
catálogo de franjas semanales alcance sin guardar fechas.

### Las reglas las hace cumplir la aplicación

Sin triggers, quien escribe directo en la base puede saltear el cupo o la
regla de una sola cita activa. El portal las respeta; el panel tiene que
respetarlas también. Las tres están en `agenda.py`, cada una en su función,
para que se puedan leer y copiar.

Al grabar una cita se toma un `SELECT ... FOR UPDATE` sobre la fila de la
franja: así dos personas que reservan en el mismo segundo no pasan las dos.

### Lo que se calcula y no se guarda

**Última donación, donaciones realizadas, fecha estimada de habilitación**
(RF30) e **historial de citas** salen de las citas completadas y del género
del donante. **El día de la cita** sale de la franja. Ninguna necesita
columnas.

---

## 6. Al empezar a trabajar, cada vez

En PowerShell:

```powershell
cd C:\Users\johan\gestion_banco_de_sangre; .\venv\Scripts\Activate.ps1
git pull
python database/verificar_modelos.py
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

```

Sin esas dos líneas, **el esquema y los catálogos no se suben** y quien
clone el proyecto no puede levantarlo: la base se queda vacía.
