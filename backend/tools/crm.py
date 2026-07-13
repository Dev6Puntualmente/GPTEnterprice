from __future__ import annotations

import json
from typing import Any

from tools.crm_db import fetch_crm_all, fetch_crm_one


def ejecutar_consulta_crm(query_sql: str) -> dict[str, Any]:
    """
    Ejecuta una consulta SQL SELECT personalizada en la base de datos del CRM (de solo lectura).
    El modelo puede usar esta herramienta para generar reportes dinámicos complejos e inspeccionar tablas.
    """
    clean_query = query_sql.strip().lower()
    
    # Validación estricta de solo lectura
    if not clean_query.startswith("select"):
        return {
            "success": False,
            "error": "Operación no permitida. Solo se admiten consultas de tipo SELECT (de lectura)."
        }

    # Prohibir palabras clave de modificación
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "create", "grant", "revoke", "replace"]
    if any(keyword in clean_query for keyword in forbidden):
        return {
            "success": False,
            "error": "Operación de modificación denegada. Solo se admiten consultas de lectura."
        }

    try:
        rows = fetch_crm_all(query_sql)
        return {
            "success": True,
            "total_registros_encontrados": len(rows),
            "resultados": rows[:100],  # Limitar para no desbordar el contexto
            "mensaje": f"Consulta ejecutada con éxito. Mostrando {min(len(rows), 100)} de {len(rows)} registros."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error de sintaxis o conexión SQL: {e}"
        }


def crm_buscar_clientes(
    query: str | None = None,
    documento: str | None = None,
    ciudad: str | None = None,
    estado: str | None = None,
    limite: int | str | float = 20
) -> dict[str, Any]:
    """
    Busca clientes en el crm.clients por nombre, documento, ciudad o estado de cliente.
    """
    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 20
    limite = max(1, min(limite, 100))

    conditions = ["1=1"]
    params = []

    if query:
        conditions.append("(full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s)")
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])

    if documento:
        conditions.append("TRIM(document_number) = TRIM(%s)")
        params.append(documento.strip())

    if ciudad:
        conditions.append("city ILIKE %s")
        params.append(f"%{ciudad.strip()}%")

    if estado:
        conditions.append("client_status ILIKE %s")
        params.append(estado.strip())

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, document_type, document_number, full_name, email, phone, city, department, client_type, client_status, created_at
        FROM crm.clients
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT %s
    """
    params.append(limite)

    try:
        rows = fetch_crm_all(sql, tuple(params))
        return {
            "success": True,
            "total": len(rows),
            "clientes": rows,
            "mensaje": f"Encontré {len(rows)} cliente(s) en el CRM."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def crm_buscar_usuarios(
    query: str | None = None,
    role: str | None = None,
    solo_activos: bool | str = True,
    limite: int | str | float = 20
) -> dict[str, Any]:
    """
    Busca usuarios de administración o agentes del CRM en crm.users.
    """
    if isinstance(solo_activos, str):
        solo_activos = solo_activos.lower() in ("true", "1", "yes")

    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 20
    limite = max(1, min(limite, 100))

    conditions = ["1=1"]
    params = []

    if query:
        conditions.append("(full_name ILIKE %s OR username ILIKE %s OR email ILIKE %s)")
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern])

    if role:
        conditions.append("role ILIKE %s")
        params.append(f"%{role.strip()}%")

    if solo_activos:
        conditions.append("is_active = TRUE")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, username, email, full_name, role, position, is_active, is_online, phone, created_at
        FROM crm.users
        WHERE {where}
        ORDER BY username
        LIMIT %s
    """
    params.append(limite)

    try:
        rows = fetch_crm_all(sql, tuple(params))
        return {
            "success": True,
            "total": len(rows),
            "usuarios": rows,
            "mensaje": f"Encontré {len(rows)} usuario(s) en el CRM."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def crm_resumen_estadisticas() -> dict[str, Any]:
    """
    Obtiene un resumen estadístico consolidado del CRM: conteo de clientes por estado/tipo,
    usuarios activos/online y chats de whatsapp activos.
    """
    try:
        # Clientes
        total_clientes = fetch_crm_one("SELECT COUNT(*) as cnt FROM crm.clients")
        clientes_por_estado = fetch_crm_all(
            "SELECT client_status, COUNT(*) as cnt FROM crm.clients GROUP BY client_status"
        )
        clientes_por_canal = fetch_crm_all(
            "SELECT preferred_channel, COUNT(*) as cnt FROM crm.clients GROUP BY preferred_channel"
        )

        # Usuarios
        total_usuarios = fetch_crm_one("SELECT COUNT(*) as cnt FROM crm.users")
        usuarios_activos = fetch_crm_one("SELECT COUNT(*) as cnt FROM crm.users WHERE is_active=TRUE")
        usuarios_online = fetch_crm_all(
            "SELECT is_online, COUNT(*) as cnt FROM crm.users GROUP BY is_online"
        )

        # Chats de Whatsapp
        total_chats = fetch_crm_one("SELECT COUNT(*) as cnt FROM whatsapp.whatsapp_chats")
        chats_por_estado = fetch_crm_all(
            "SELECT status, COUNT(*) as cnt FROM whatsapp.whatsapp_chats GROUP BY status"
        )

        return {
            "success": True,
            "estadisticas": {
                "clientes": {
                    "total": total_clientes.get("cnt") if total_clientes else 0,
                    "distribucion_estado": {r["client_status"] or "N/D": r["cnt"] for r in clientes_por_estado},
                    "distribucion_canal_preferido": {r["preferred_channel"] or "N/D": r["cnt"] for r in clientes_por_canal}
                },
                "usuarios": {
                    "total": total_usuarios.get("cnt") if total_usuarios else 0,
                    "activos": usuarios_activos.get("cnt") if usuarios_activos else 0,
                    "distribucion_disponibilidad": {r["is_online"] or "N/D": r["cnt"] for r in usuarios_online}
                },
                "whatsapp_chats": {
                    "total": total_chats.get("cnt") if total_chats else 0,
                    "distribucion_estado": {str(r["status"]): r["cnt"] for r in chats_por_estado}
                }
            },
            "mensaje": "Estadísticas agregadas del CRM obtenidas exitosamente."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
