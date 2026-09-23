from flask import render_template
from sqlalchemy import text

from app.models import db


def mostrar_estado():
    db.session.execute(text("SELECT 1"))
    return render_template("base.html")
