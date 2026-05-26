import sqlite3
import json
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.database_query")

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


def _query_sqlite(db_path: str, query: str) -> str:
    if not Path(db_path).exists():
        return f"Base de datos no encontrada: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)

        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            if not rows:
                return "Consulta ejecutada. 0 resultados."
            result = []
            result.append(" | ".join(cols))
            result.append("-" * 40)
            for row in rows[:50]:
                result.append(" | ".join(str(v)[:50] for v in row))
            if len(rows) > 50:
                result.append(f"... y {len(rows) - 50} filas mas.")
            conn.close()
            return "\n".join(result)
        else:
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return f"Query ejecutada. {affected} filas afectadas."

    except Exception as e:
        return f"Error SQL: {e}"


def _query_mysql(host: str, user: str, password: str, database: str, query: str) -> str:
    if not HAS_MYSQL:
        return "Necesito mysql-connector-python. Ejecuta: pip install mysql-connector-python"

    try:
        conn = mysql.connector.connect(
            host=host, user=user, password=password, database=database
        )
        cursor = conn.cursor()
        cursor.execute(query)

        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            if not rows:
                return "Consulta ejecutada. 0 resultados."
            result = []
            result.append(" | ".join(cols))
            result.append("-" * 40)
            for row in rows[:50]:
                result.append(" | ".join(str(v)[:50] for v in row))
            conn.close()
            return "\n".join(result)
        else:
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return f"Query ejecutada. {affected} filas afectadas."

    except Exception as e:
        return f"Error MySQL: {e}"


def _list_tables(db_path: str) -> str:
    if not Path(db_path).exists():
        return f"Base de datos no encontrada: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        if not tables:
            return "No se encontraron tablas."
        return "Tablas:\n" + "\n".join(f"  - {t}" for t in tables)
    except Exception as e:
        return f"Error: {e}"


def database_query(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "query")
    db_type = p.get("type", "sqlite")
    query = p.get("query", "")

    if action == "tables":
        db_path = p.get("file_path", "")
        if not db_path:
            return "Necesito la ruta de la base de datos (file_path)."
        return _list_tables(db_path)

    if not query:
        return "Necesito una consulta SQL (query)."

    if db_type == "mysql":
        host = p.get("host", "localhost")
        user = p.get("user", "root")
        password = p.get("password", "")
        database = p.get("database", "")
        return _query_mysql(host, user, password, database, query)
    else:
        db_path = p.get("file_path", "")
        if not db_path:
            return "Necesito la ruta del archivo SQLite (file_path)."
        return _query_sqlite(db_path, query)
