# Sistema de Gestión de Donantes
**Prototipo académico · Flask + PostgreSQL · Arquitectura MVC**

Sistema web desarrollado para la gestión de donantes de sangre.
La estructura de la base de datos se obtiene **únicamente** desde `database/schema.sql`.

---

## 📋 Requisitos

Antes de comenzar, verificar que estén instalados:

* **Python 3.10+**
* **PostgreSQL**

---

## ⚙️ 1. Configurar el proyecto

Clonar el repositorio y ubicarse en la carpeta del proyecto:

```powershell
git clone <repositorio>
cd <proyecto>
```

Crear y activar el entorno virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Instalar las dependencias:

```powershell
pip install -r requirements.txt
```

---

## 🗄️ 2. Crear la base de datos

Crear únicamente la base de datos vacía desde PostgreSQL:

```sql
CREATE DATABASE gestion_donantes;
```
---

## 🔐 3. Configurar `.env`

Verificar que el archivo `.env` tenga los datos correctos de conexión:

```env
DB_NAME=gestion_donantes
DB_USER=postgres
DB_PASSWORD=tu_password
SECRET_KEY=tu_secret_key
```

Asegurarse de que PostgreSQL esté ejecutándose antes de iniciar Flask.

---

## 🚀 4. Levantar el proyecto

Con el entorno virtual activo:

```powershell
flask run
```

También puede ejecutarse mediante:

```powershell
python run.py
```

Luego abrir:

**http://127.0.0.1:5000**

