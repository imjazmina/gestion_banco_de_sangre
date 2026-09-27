"""
Manda los avisos automáticos del portal.

Hoy manda uno: el correo con el cuestionario previo, a quienes tienen una
cita dentro de las próximas 3 horas y todavía no lo recibieron.

    python enviar_avisos.py            manda lo que corresponda ahora
    python enviar_avisos.py --ver      muestra a quién le tocaría, sin enviar
    python enviar_avisos.py --cita 12  manda el de esa cita ahora mismo

La opción --cita es para probar y para mostrar el circuito sin esperar a
que falten 3 horas.

PARA QUE SALGA SOLO, en Windows:
  Programador de tareas → Crear tarea básica → "Avisos banco de sangre"
  Desencadenador: diariamente, repetir cada 15 minutos durante 1 día
  Acción: iniciar un programa
      Programa:   C:\\Users\\johan\\gestion_banco_de_sangre\\venv\\Scripts\\python.exe
      Argumentos: enviar_avisos.py
      Iniciar en: C:\\Users\\johan\\gestion_banco_de_sangre

Correr de más no molesta: cada aviso queda registrado y no se repite.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app                                # noqa: E402
from app.controllers.portal import avisos                 # noqa: E402
from app.models import Cita, db                          # noqa: E402


def main():
    argumentos = sys.argv[1:]
    solo_ver = "--ver" in argumentos

    id_cita = None
    if "--cita" in argumentos:
        try:
            id_cita = int(argumentos[argumentos.index("--cita") + 1])
        except (IndexError, ValueError):
            print("Usá:  python enviar_avisos.py --cita 12")
            return 1

    app = create_app()
    with app.app_context():
        url_base = app.config["URL_BASE"].rstrip("/")
        print(f"{datetime.now():%d/%m/%Y %H:%M}  ·  enlaces hacia {url_base}")

        if id_cita is not None:
            # db.session.get y no Cita.query.get: el segundo es la forma
            # vieja y SQLAlchemy 2 avisa en pantalla cada vez, lo que parece
            # un error sin serlo.
            cita = db.session.get(Cita, id_cita)
            if cita is None:
                print(f"No existe la cita {id_cita}.")
                print()
                proximas = avisos.proximas_citas()
                if proximas:
                    print("Las citas que sí existen son:")
                    for c in proximas:
                        print(f"  cita {c.id_cita}: {c.donante.nombre_completo}, "
                              f"{c.fecha_cita:%d/%m/%Y} {c.horario.hora_inicio:%H:%M}")
                else:
                    print("No hay ninguna cita agendada todavía. Agendá una")
                    print("desde el portal y volvé a intentar.")
                return 1
            enviado, detalle = avisos.enviar_cuestionario(cita, url_base)
            print(f"  cita {id_cita}: {'ok' if enviado else 'FALLÓ'} — {detalle}")
            return 0 if enviado else 1

        if solo_ver:
            citas = avisos.pendientes_de_cuestionario()
            if citas:
                print(f"\nLe tocaría el aviso a {len(citas)} cita(s):")
                for c in citas:
                    print(f"  cita {c.id_cita}: {c.donante.nombre_completo}, "
                          f"{c.fecha_cita:%d/%m/%Y} {c.horario.hora_inicio:%H:%M}")
            else:
                print("\nAhora mismo no le toca a ninguna cita.")

            # Todas las próximas, con su número, para poder mandar una de
            # prueba sin esperar a que falten tres horas.
            proximas = avisos.proximas_citas()
            if proximas:
                print("\nPróximas citas (para probar con --cita):")
                for c in proximas:
                    print(f"  cita {c.id_cita}: {c.donante.nombre_completo}, "
                          f"{c.fecha_cita:%d/%m/%Y} {c.horario.hora_inicio:%H:%M}")
                print(f"\nPor ejemplo:  python enviar_avisos.py --cita {proximas[0].id_cita}")
            else:
                print("\nNo hay ninguna cita agendada. Agendá una desde el")
                print("portal y volvé a correr esto.")

            print("\n(--ver: no se envió nada)")
            return 0

        for linea in avisos.correr(url_base):
            print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
