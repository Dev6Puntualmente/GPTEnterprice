from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tools.crm_db import fetch_crm_all, fetch_crm_one


def _period(fecha_inicio: str | None, fecha_fin: str | None) -> tuple[str, str]:
    if not fecha_inicio and not fecha_fin:
        end = date.today()
        start = end - timedelta(days=7)
        return start.isoformat(), end.isoformat()
    start = fecha_inicio or date.today().isoformat()
    end = fecha_fin or start
    return start, end


def crm_listar_conexiones(
    solo_activas: bool | str = True,
    limite: int | str | float = 30,
) -> dict[str, Any]:
    """Lista conexiones/canales activos del CRM (crm.active_channels)."""
    if isinstance(solo_activas, str):
        solo_activas = solo_activas.lower() in ("true", "1", "yes")
    try:
        limite = max(1, min(int(float(limite)), 100))
    except (ValueError, TypeError):
        limite = 30

    conditions = ["ac.deleted_at IS NULL"]
    if solo_activas:
        conditions.append("ac.is_active = TRUE")

    rows = fetch_crm_all(
        f"""
        SELECT
            ac.id::text AS id,
            ac.connection_id::text AS connection_id,
            ac.department_id::text AS department_id,
            ac.channel_id::text AS channel_id,
            ac.is_active,
            ac.bot_name,
            ac.ai_enabled,
            ac.max_agent,
            ac.created_at
        FROM crm.active_channels ac
        WHERE {" AND ".join(conditions)}
        ORDER BY ac.created_at DESC NULLS LAST
        LIMIT %s
        """,
        (limite,),
    )
    return {
        "success": True,
        "total": len(rows),
        "conexiones": rows,
        "mensaje": f"Encontré {len(rows)} conexión(es) activa(s).",
    }


def crm_dashboard_whatsapp(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict[str, Any]:
    """Métricas WhatsApp: chats por estado y mensajes en el periodo."""
    start, end = _period(fecha_inicio, fecha_fin)
    try:
        chats_por_estado = fetch_crm_all(
            """
            SELECT COALESCE(status::text, 'N/D') AS estado, COUNT(*) AS total
            FROM whatsapp.whatsapp_chats
            GROUP BY status
            ORDER BY total DESC
            """
        )
        chats_periodo = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM whatsapp.whatsapp_chats
            WHERE last_message_at >= %s::date
              AND last_message_at < (%s::date + INTERVAL '1 day')
            """,
            (start, end),
        )
        mensajes_periodo = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM whatsapp.whatsapp_messages
            WHERE created_at >= %s::date
              AND created_at < (%s::date + INTERVAL '1 day')
            """,
            (start, end),
        )
        chats_activos = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM whatsapp.whatsapp_chats
            WHERE LOWER(COALESCE(status::text, '')) IN ('active', 'open', 'activo', 'abierto')
            """
        )
        return {
            "success": True,
            "periodo": {"fecha_inicio": start, "fecha_fin": end},
            "metricas": {
                "chats_con_actividad_periodo": chats_periodo.get("total", 0) if chats_periodo else 0,
                "mensajes_periodo": mensajes_periodo.get("total", 0) if mensajes_periodo else 0,
                "chats_activos_ahora": chats_activos.get("total", 0) if chats_activos else 0,
                "distribucion_estado": chats_por_estado,
            },
            "mensaje": f"Dashboard WhatsApp {start} → {end}.",
        }
    except Exception as error:
        return {"success": False, "error": str(error)}


def crm_dashboard_tipologico(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    limite: int | str | float = 30,
) -> dict[str, Any]:
    """Distribución tipológica: gestiones agrupadas por canal/acción/resultado."""
    start, end = _period(fecha_inicio, fecha_fin)
    try:
        limite = max(1, min(int(float(limite)), 100))
    except (ValueError, TypeError):
        limite = 30

    try:
        total = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM crm.management_history m
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            """,
            (start, end),
        )
        por_canal = fetch_crm_all(
            """
            SELECT COALESCE(ch.name, 'Sin canal') AS etiqueta, COUNT(*) AS total
            FROM crm.management_history m
            LEFT JOIN config.catalog_items ch ON ch.id = m.channel_id
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            GROUP BY ch.name
            ORDER BY total DESC
            LIMIT %s
            """,
            (start, end, limite),
        )
        por_accion = fetch_crm_all(
            """
            SELECT COALESCE(ac.name, 'Sin acción') AS etiqueta, COUNT(*) AS total
            FROM crm.management_history m
            LEFT JOIN config.catalog_items ac ON ac.id = m.action_id
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            GROUP BY ac.name
            ORDER BY total DESC
            LIMIT %s
            """,
            (start, end, limite),
        )
        por_resultado = fetch_crm_all(
            """
            SELECT COALESCE(rs.name, 'Sin resultado') AS etiqueta, COUNT(*) AS total
            FROM crm.management_history m
            LEFT JOIN config.catalog_items rs ON rs.id = m.result_id
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            GROUP BY rs.name
            ORDER BY total DESC
            LIMIT %s
            """,
            (start, end, limite),
        )
        combinado = fetch_crm_all(
            """
            SELECT
                COALESCE(ch.name, 'Sin canal') AS canal,
                COALESCE(ac.name, 'Sin acción') AS accion,
                COALESCE(rs.name, 'Sin resultado') AS resultado,
                COUNT(*) AS total
            FROM crm.management_history m
            LEFT JOIN config.catalog_items ch ON ch.id = m.channel_id
            LEFT JOIN config.catalog_items ac ON ac.id = m.action_id
            LEFT JOIN config.catalog_items rs ON rs.id = m.result_id
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            GROUP BY ch.name, ac.name, rs.name
            ORDER BY total DESC
            LIMIT %s
            """,
            (start, end, limite),
        )
        return {
            "success": True,
            "periodo": {"fecha_inicio": start, "fecha_fin": end},
            "total_gestiones": total.get("total", 0) if total else 0,
            "por_canal": por_canal,
            "por_accion": por_accion,
            "por_resultado": por_resultado,
            "combinaciones_top": combinado,
            "mensaje": (
                f"Tipológico {start} → {end}: "
                f"{total.get('total', 0) if total else 0} gestiones."
            ),
        }
    except Exception as error:
        return {"success": False, "error": str(error)}


def crm_reporte_estados_agentes(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    agente: str | None = None,
    limite: int | str | float = 50,
) -> dict[str, Any]:
    """Reporte de cambios de estado de agentes (crm.agent_state_logs)."""
    start, end = _period(fecha_inicio, fecha_fin)
    try:
        limite = max(1, min(int(float(limite)), 200))
    except (ValueError, TypeError):
        limite = 50

    conditions = [
        "asl.changed_at >= %s::date",
        "asl.changed_at < (%s::date + INTERVAL '1 day')",
    ]
    params: list[Any] = [start, end]
    if agente:
        conditions.append(
            "(asl.agent_name ILIKE %s OR u.full_name ILIKE %s OR u.username ILIKE %s)"
        )
        pattern = f"%{agente.strip()}%"
        params.extend([pattern, pattern, pattern])

    where = " AND ".join(conditions)
    try:
        resumen = fetch_crm_all(
            f"""
            SELECT UPPER(COALESCE(asl.to_status, 'N/D')) AS estado, COUNT(*) AS total
            FROM crm.agent_state_logs asl
            LEFT JOIN crm.users u ON u.id = asl.agent_id
            WHERE {where}
            GROUP BY UPPER(COALESCE(asl.to_status, 'N/D'))
            ORDER BY total DESC
            """,
            tuple(params),
        )
        params_with_limit = [*params, limite]
        filas = fetch_crm_all(
            f"""
            SELECT
                asl.changed_at,
                COALESCE(asl.agent_name, u.full_name, u.username) AS agente,
                asl.from_status,
                asl.to_status,
                asl.department_name,
                asl.channel
            FROM crm.agent_state_logs asl
            LEFT JOIN crm.users u ON u.id = asl.agent_id
            WHERE {where}
            ORDER BY asl.changed_at DESC
            LIMIT %s
            """,
            tuple(params_with_limit),
        )
        return {
            "success": True,
            "periodo": {"fecha_inicio": start, "fecha_fin": end},
            "resumen_por_estado": resumen,
            "ultimos_cambios": filas,
            "mensaje": f"Estados de agentes {start} → {end}: {len(filas)} registro(s) recientes.",
        }
    except Exception as error:
        return {"success": False, "error": str(error)}
