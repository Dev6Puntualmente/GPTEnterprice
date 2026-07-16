from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Any

from tools.crm_db import fetch_crm_all, fetch_crm_one, USERS_ONLINE_CONDITION

_DOCUMENTO_RE = re.compile(r"^\d{6,15}$")
_GESTION_ALIAS_RE = re.compile(r"^G\d{5,12}$", re.IGNORECASE)

_GESTION_SELECT = """
    SELECT
        m.id::text AS id,
        m.customer_id::text AS customer_id,
        m.advisor_id::text AS advisor_id,
        m.text_management,
        m.metadata,
        m.created_at,
        m.is_active,
        c.full_name AS customer_name,
        c.document_number,
        u.full_name AS advisor_name,
        ga.alias_code AS gestion_alias,
        ch.name AS channel_name,
        ac.name AS action_name,
        ct.name AS contact_name,
        rs.name AS result_name
    FROM crm.management_history m
    LEFT JOIN crm.clients c ON c.id = m.customer_id
    LEFT JOIN crm.users u ON u.id = m.advisor_id
    LEFT JOIN crm.gestion_id_aliases ga ON ga.gestion_id = m.id
    LEFT JOIN config.catalog_items ch ON ch.id = m.channel_id
    LEFT JOIN config.catalog_items ac ON ac.id = m.action_id
    LEFT JOIN config.catalog_items ct ON ct.id = m.contact_id
    LEFT JOIN config.catalog_items rs ON rs.id = m.result_id
"""


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_gestion_filters(
    documento: str | None,
    cliente: str | None,
    asesor: str | None,
    gestion_id: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    documento = _coerce_optional_str(documento)
    cliente = _coerce_optional_str(cliente)
    asesor = _coerce_optional_str(asesor)
    gestion_id = _coerce_optional_str(gestion_id)

    # El LLM a veces manda la cédula en "cliente" — corregir automáticamente.
    if cliente and _DOCUMENTO_RE.fullmatch(cliente) and not documento:
        documento = cliente
        cliente = None

    return documento, cliente, asesor, gestion_id


def _parse_limite(value: int | str | float, default: int = 20, maximum: int = 100) -> int:
    try:
        limite = int(float(value))
    except (ValueError, TypeError):
        limite = default
    return max(1, min(limite, maximum))


def _resolve_gestion_uuid(gestion_id: str) -> str | None:
    raw = str(gestion_id or "").strip()
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        row = fetch_crm_one(
            """
            SELECT gestion_id::text AS gestion_id
            FROM crm.gestion_id_aliases
            WHERE UPPER(alias_code) = UPPER(%s)
            LIMIT 1
            """,
            (raw,),
        )
        return row.get("gestion_id") if row else None


def crm_obtener_gestion(gestion_id: str) -> dict[str, Any]:
    """Obtiene una gestión por UUID o alias corto."""
    resolved = _resolve_gestion_uuid(gestion_id)
    if not resolved:
        return {
            "success": False,
            "mensaje": f"No encontré gestión con id o alias '{gestion_id}'.",
        }

    row = fetch_crm_one(
        f"{_GESTION_SELECT} WHERE m.id = %s::uuid LIMIT 1",
        (resolved,),
    )
    if not row:
        return {"success": False, "mensaje": f"No encontré gestión {gestion_id}."}

    return {
        "success": True,
        "gestion": row,
        "mensaje": f"Gestión {row.get('gestion_alias') or row.get('id')} encontrada.",
    }


def crm_listar_gestiones(
    documento: str | None = None,
    cliente: str | None = None,
    asesor: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    gestion_id: str | None = None,
    limite: int | str | float = 20,
    solo_ultima: bool | str = False,
) -> dict[str, Any]:
    """
    Lista gestiones del CRM con filtros opcionales.
    Si solo_ultima=true devuelve la más reciente que cumpla los filtros.
    """
    if isinstance(solo_ultima, str):
        solo_ultima = solo_ultima.lower() in ("true", "1", "yes")

    documento, cliente, asesor, gestion_id = _normalize_gestion_filters(
        documento, cliente, asesor, gestion_id
    )

    if gestion_id:
        return crm_obtener_gestion(gestion_id)

    limite = 1 if solo_ultima else _parse_limite(limite)
    conditions = ["m.is_active = TRUE"]
    params: list[Any] = []

    if documento:
        conditions.append("TRIM(c.document_number) = TRIM(%s)")
        params.append(documento.strip())

    if cliente:
        conditions.append("c.full_name ILIKE %s")
        params.append(f"%{cliente.strip()}%")

    if asesor:
        conditions.append("(u.full_name ILIKE %s OR u.username ILIKE %s OR u.email ILIKE %s)")
        pattern = f"%{asesor.strip()}%"
        params.extend([pattern, pattern, pattern])

    if fecha_inicio:
        conditions.append("m.created_at >= %s::date")
        params.append(fecha_inicio.strip())

    if fecha_fin:
        conditions.append("m.created_at < (%s::date + INTERVAL '1 day')")
        params.append(fecha_fin.strip())

    if not fecha_inicio and not fecha_fin and not documento and not cliente and not asesor:
        # Sin filtros explícitos: ventana amplia para no devolver cero en listados generales.
        end = date.today()
        start = end - timedelta(days=90)
        conditions.append("m.created_at >= %s::date")
        params.append(start.isoformat())
        conditions.append("m.created_at < (%s::date + INTERVAL '1 day')")
        params.append((end + timedelta(days=1)).isoformat())

    where = " AND ".join(conditions)
    sql = f"""
        {_GESTION_SELECT}
        WHERE {where}
        ORDER BY m.created_at DESC
        LIMIT %s
    """
    params.append(limite)

    try:
        rows = fetch_crm_all(sql, tuple(params))
        if solo_ultima:
            if not rows:
                return {
                    "success": True,
                    "total": 0,
                    "gestiones": [],
                    "mensaje": "No encontré gestiones recientes con esos criterios.",
                }
            return {
                "success": True,
                "total": 1,
                "gestiones": rows,
                "mensaje": f"Última gestión: {rows[0].get('gestion_alias') or rows[0].get('id')}.",
            }

        return {
            "success": True,
            "total": len(rows),
            "gestiones": rows,
            "filtros": {
                "documento": documento,
                "cliente": cliente,
                "asesor": asesor,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "limite": limite,
            },
            "mensaje": f"Encontré {len(rows)} gestión(es) en el CRM.",
        }
    except Exception as error:
        return {"success": False, "error": str(error)}


def crm_listar_arboles_tipificacion(
    solo_activos: bool | str = True,
    nombre: str | None = None,
    limite: int | str | float = 50,
) -> dict[str, Any]:
    """Lista árboles de tipificación (config.trees)."""
    if isinstance(solo_activos, str):
        solo_activos = solo_activos.lower() in ("true", "1", "yes")

    limite = _parse_limite(limite, default=50, maximum=100)
    conditions = ["1=1"]
    params: list[Any] = []

    if solo_activos:
        conditions.append("is_active = TRUE")

    if nombre:
        conditions.append("name ILIKE %s")
        params.append(f"%{nombre.strip()}%")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id::text AS id, name, description, icon, color, is_active, created_at
        FROM config.trees
        WHERE {where}
        ORDER BY name
        LIMIT %s
    """
    params.append(limite)

    try:
        rows = fetch_crm_all(sql, tuple(params))
        return {
            "success": True,
            "total": len(rows),
            "arboles": rows,
            "mensaje": f"Encontré {len(rows)} árbol(es) de tipificación.",
        }
    except Exception as error:
        return {"success": False, "error": str(error)}


def crm_arbol_capas(
    tree_id: str | None = None,
    nombre_arbol: str | None = None,
    solo_activas: bool | str = True,
) -> dict[str, Any]:
    """Lista capas/catálogos de un árbol (config.catalogs) ordenadas por level."""
    if isinstance(solo_activas, str):
        solo_activas = solo_activas.lower() in ("true", "1", "yes")

    resolved_tree_id = tree_id
    if not resolved_tree_id and nombre_arbol:
        row = fetch_crm_one(
            """
            SELECT id::text AS id, name
            FROM config.trees
            WHERE name ILIKE %s
            ORDER BY is_active DESC, name
            LIMIT 1
            """,
            (f"%{nombre_arbol.strip()}%",),
        )
        resolved_tree_id = row.get("id") if row else None

    if not resolved_tree_id:
        return {
            "success": False,
            "mensaje": "Indica tree_id o nombre_arbol para listar las capas.",
        }

    try:
        uuid.UUID(str(resolved_tree_id))
    except ValueError:
        return {"success": False, "mensaje": f"tree_id inválido: {resolved_tree_id}"}

    conditions = ["cat.tree_id = %s::uuid"]
    params: list[Any] = [resolved_tree_id]
    if solo_activas:
        conditions.append("cat.is_active = TRUE")

    sql = f"""
        SELECT
            cat.id::text AS id,
            cat.name,
            cat.level,
            cat.icon,
            cat.is_active,
            cat.default_value,
            COUNT(ci.id) AS items_count
        FROM config.catalogs cat
        LEFT JOIN config.catalog_items ci ON ci.catalog_id = cat.id AND ci.is_active = TRUE
        WHERE {" AND ".join(conditions)}
        GROUP BY cat.id, cat.name, cat.level, cat.icon, cat.is_active, cat.default_value
        ORDER BY cat.level ASC, cat.name ASC
    """
    rows = fetch_crm_all(sql, tuple(params))
    tree = fetch_crm_one(
        "SELECT id::text AS id, name, description FROM config.trees WHERE id = %s::uuid",
        (resolved_tree_id,),
    )
    return {
        "success": True,
        "arbol": tree,
        "total": len(rows),
        "capas": rows,
        "mensaje": f"Árbol '{tree.get('name') if tree else resolved_tree_id}': {len(rows)} capa(s).",
    }


def crm_listar_flujos(
    tree_id: str | None = None,
    nombre_arbol: str | None = None,
    nombre_flujo: str | None = None,
    limite: int | str | float = 30,
) -> dict[str, Any]:
    """Lista flujos nombrados (config.named_flows) de un árbol."""
    limite = _parse_limite(limite, default=30, maximum=100)
    resolved_tree_id = tree_id
    if not resolved_tree_id and nombre_arbol:
        row = fetch_crm_one(
            "SELECT id::text AS id FROM config.trees WHERE name ILIKE %s LIMIT 1",
            (f"%{nombre_arbol.strip()}%",),
        )
        resolved_tree_id = row.get("id") if row else None

    if not resolved_tree_id:
        return {"success": False, "mensaje": "Indica tree_id o nombre_arbol para listar flujos."}

    conditions = ["nf.tree_id = %s::uuid"]
    params: list[Any] = [resolved_tree_id]
    if nombre_flujo:
        conditions.append("nf.name ILIKE %s")
        params.append(f"%{nombre_flujo.strip()}%")

    sql = f"""
        SELECT nf.id::text AS id, nf.name, nf.item_ids, nf.created_at, nf.updated_at
        FROM config.named_flows nf
        WHERE {" AND ".join(conditions)}
        ORDER BY nf.name
        LIMIT %s
    """
    params.append(limite)
    rows = fetch_crm_all(sql, tuple(params))

    enriched = []
    for row in rows:
        item_ids = row.get("item_ids") or []
        items = []
        if isinstance(item_ids, list) and item_ids:
            placeholders = ",".join(["%s::uuid"] * len(item_ids))
            items = fetch_crm_all(
                f"""
                SELECT ci.id::text AS id, ci.code, ci.name, cat.name AS capa, cat.level
                FROM config.catalog_items ci
                JOIN config.catalogs cat ON cat.id = ci.catalog_id
                WHERE ci.id IN ({placeholders})
                ORDER BY cat.level ASC
                """,
                tuple(str(item_id) for item_id in item_ids),
            )
        enriched.append({**row, "pasos": items})

    return {
        "success": True,
        "total": len(enriched),
        "flujos": enriched,
        "mensaje": f"Encontré {len(enriched)} flujo(s) en el árbol.",
    }


def crm_buscar_items_capa(
    catalog_id: str | None = None,
    nombre_capa: str | None = None,
    nombre_arbol: str | None = None,
    tree_id: str | None = None,
    query: str | None = None,
    limite: int | str | float = 30,
) -> dict[str, Any]:
    """Busca ítems dentro de una capa/catálogo del árbol de tipificación."""
    limite = _parse_limite(limite, default=30, maximum=100)
    resolved_catalog_id = catalog_id
    resolved_tree_id = tree_id

    if not resolved_tree_id and nombre_arbol:
        row = fetch_crm_one(
            """
            SELECT id::text AS id
            FROM config.trees
            WHERE name ILIKE %s
            ORDER BY is_active DESC, name
            LIMIT 1
            """,
            (f"%{nombre_arbol.strip()}%",),
        )
        resolved_tree_id = row.get("id") if row else None

    if not resolved_catalog_id and nombre_capa:
        conditions = ["cat.name ILIKE %s"]
        params: list[Any] = [f"%{nombre_capa.strip()}%"]
        if resolved_tree_id:
            conditions.append("cat.tree_id = %s::uuid")
            params.append(resolved_tree_id)
        row = fetch_crm_one(
            f"""
            SELECT cat.id::text AS id, cat.name, cat.level
            FROM config.catalogs cat
            WHERE {" AND ".join(conditions)}
            ORDER BY cat.level
            LIMIT 1
            """,
            tuple(params),
        )
        resolved_catalog_id = row.get("id") if row else None

    if not resolved_catalog_id:
        return {"success": False, "mensaje": "Indica catalog_id o nombre_capa para buscar ítems."}

    conditions = ["ci.catalog_id = %s::uuid", "ci.is_active = TRUE"]
    params = [resolved_catalog_id]
    if query:
        conditions.append("(ci.name ILIKE %s OR ci.code ILIKE %s)")
        pattern = f"%{query.strip()}%"
        params.extend([pattern, pattern])

    sql = f"""
        SELECT ci.id::text AS id, ci.code, ci.name, ci.description, ci.weight, ci.is_default
        FROM config.catalog_items ci
        WHERE {" AND ".join(conditions)}
        ORDER BY ci.weight DESC, ci.name
        LIMIT %s
    """
    params.append(limite)
    rows = fetch_crm_all(sql, tuple(params))
    capa = fetch_crm_one(
        """
        SELECT cat.id::text AS id, cat.name, cat.level, t.name AS arbol
        FROM config.catalogs cat
        JOIN config.trees t ON t.id = cat.tree_id
        WHERE cat.id = %s::uuid
        """,
        (resolved_catalog_id,),
    )
    return {
        "success": True,
        "capa": capa,
        "total": len(rows),
        "items": rows,
        "mensaje": f"Capa '{capa.get('name') if capa else resolved_catalog_id}': {len(rows)} ítem(s).",
    }


def crm_dashboard_resumen(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict[str, Any]:
    """Resumen tipo dashboard: gestiones, clientes nuevos y agentes online en un periodo."""
    if not fecha_inicio and not fecha_fin:
        end = date.today()
        start = end - timedelta(days=7)
        fecha_inicio = start.isoformat()
        fecha_fin = end.isoformat()
    else:
        fecha_inicio = fecha_inicio or date.today().isoformat()
        fecha_fin = fecha_fin or fecha_inicio

    try:
        gestiones = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM crm.management_history
            WHERE is_active = TRUE
              AND created_at >= %s::date
              AND created_at < (%s::date + INTERVAL '1 day')
            """,
            (fecha_inicio, fecha_fin),
        )
        clientes_nuevos = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM crm.clients
            WHERE created_at >= %s::date
              AND created_at < (%s::date + INTERVAL '1 day')
            """,
            (fecha_inicio, fecha_fin),
        )
        agentes_online = fetch_crm_one(
            f"SELECT COUNT(*) AS total FROM crm.users WHERE {USERS_ONLINE_CONDITION}"
        )
        chats_activos = fetch_crm_one(
            """
            SELECT COUNT(*) AS total
            FROM whatsapp.whatsapp_chats
            WHERE LOWER(COALESCE(status::text, '')) IN ('active', 'open', 'activo', 'abierto')
            """
        )
        por_canal = fetch_crm_all(
            """
            SELECT ch.name AS canal, COUNT(*) AS total
            FROM crm.management_history m
            LEFT JOIN config.catalog_items ch ON ch.id = m.channel_id
            WHERE m.is_active = TRUE
              AND m.created_at >= %s::date
              AND m.created_at < (%s::date + INTERVAL '1 day')
            GROUP BY ch.name
            ORDER BY total DESC
            LIMIT 10
            """,
            (fecha_inicio, fecha_fin),
        )

        return {
            "success": True,
            "periodo": {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin},
            "metricas": {
                "gestiones_periodo": gestiones.get("total", 0) if gestiones else 0,
                "clientes_nuevos_periodo": clientes_nuevos.get("total", 0) if clientes_nuevos else 0,
                "agentes_online": agentes_online.get("total", 0) if agentes_online else 0,
                "chats_whatsapp_activos": chats_activos.get("total", 0) if chats_activos else 0,
                "gestiones_por_canal": por_canal,
            },
            "mensaje": (
                f"Dashboard CRM {fecha_inicio} → {fecha_fin}: "
                f"{gestiones.get('total', 0) if gestiones else 0} gestiones."
            ),
        }
    except Exception as error:
        return {"success": False, "error": str(error)}
