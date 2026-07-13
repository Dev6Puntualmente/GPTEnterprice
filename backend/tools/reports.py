from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from db import fetch_all


def obtener_reporte_estadisticas(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    campana: str | None = None,
    agente: str | None = None,
    min_score: float | str | None = None,
    max_score: float | str | None = None,
) -> dict[str, Any]:
    """
    Calcula agregaciones y estadísticas de llamadas (compliance score, sentimientos, marcadas, etc.)
    siguiendo la lógica de reportes de Qontrol, diseñado para uso de la IA de forma autónoma.
    """
    # Coerción de tipos para scores
    try:
        min_score = float(min_score) if min_score is not None else None
    except (ValueError, TypeError):
        min_score = None

    try:
        max_score = float(max_score) if max_score is not None else None
    except (ValueError, TypeError):
        max_score = None

    # Lógica inteligente de rango de fechas
    if not fecha_inicio and not fecha_fin:
        # Default a últimos 30 días si no se especifican fechas
        end_dt = date.today()
        start_dt = end_dt - timedelta(days=30)
        start = start_dt.isoformat()
        end = end_dt.isoformat()
    else:
        start = fecha_inicio or date.today().isoformat()
        end = fecha_fin or start

    # Construir condiciones SQL
    conditions = [
        "c.created_at >= %s::date",
        "c.created_at < (%s::date + INTERVAL '1 day')"
    ]
    params: list[Any] = [start, end]

    if campana:
        conditions.append("(camp.name ILIKE %s OR c.campana ILIKE %s)")
        pattern = f"%{campana}%"
        params.extend([pattern, pattern])

    if agente:
        conditions.append("(u.name ILIKE %s OR u.email ILIKE %s)")
        pattern = f"%{agente}%"
        params.extend([pattern, pattern])

    where = " AND ".join(conditions)

    query = f"""
        SELECT
            c.id,
            c.customer_name,
            c.campana,
            c.is_flagged,
            c.created_at,
            c.human_calibration,
            c.ai_evaluation,
            u.name AS agente,
            u.email AS agente_email,
            camp.name AS campana_nombre,
            ce.compliance_score AS ai_score,
            ce.data AS evaluation_data
        FROM calls c
        LEFT JOIN users u ON u.id = c.agent_id
        LEFT JOIN campaigns camp ON camp.id = c.campaign_id
        LEFT JOIN call_evaluations ce ON ce.call_id = c.id
        WHERE {where}
        ORDER BY c.created_at DESC
        LIMIT 500
    """
    try:
        rows = fetch_all(query, tuple(params))
    except Exception as err:
        return {
            "success": False,
            "error": f"Error al consultar la base de datos: {err}",
            "mensaje": "No se pudieron obtener las estadísticas de llamadas en este momento."
        }

    # Procesar filas y calcular estadísticas
    filtered_rows = []
    scores = []
    ai_scores = []
    human_scores = []
    flagged_count = 0
    sentiment_distribution: dict[str, int] = {}

    for row in rows:
        # Calcular score efectivo (siguiendo lógica de Qontrol)
        # 1. Intentar obtener score de calibración humana
        human_calib = row.get("human_calibration")
        human_score = None
        if isinstance(human_calib, dict):
            if human_calib.get("discrepancyStatus") == "confirmed":
                try:
                    human_score = float(human_calib.get("humanScore"))
                except (ValueError, TypeError):
                    pass
        elif isinstance(human_calib, str):
            try:
                parsed = json.loads(human_calib)
                if parsed.get("discrepancyStatus") == "confirmed":
                    human_score = float(parsed.get("humanScore"))
            except Exception:
                pass

        # 2. Score de IA (tabla o columna fallback)
        ai_score = row.get("ai_score")
        if ai_score is None:
            ai_eval = row.get("ai_evaluation")
            if isinstance(ai_eval, dict):
                ai_score = ai_eval.get("compliance_score")
            elif isinstance(ai_eval, str):
                try:
                    parsed = json.loads(ai_eval)
                    ai_score = parsed.get("compliance_score")
                except Exception:
                    pass

        try:
            ai_score = float(ai_score) if ai_score is not None else None
        except (ValueError, TypeError):
            ai_score = None

        effective_score = human_score if human_score is not None else ai_score

        # Filtrar por score si se especificó min_score o max_score
        if min_score is not None and (effective_score is None or effective_score < min_score):
            continue
        if max_score is not None and (effective_score is None or effective_score > max_score):
            continue

        # Guardar scores para agregación
        if effective_score is not None:
            scores.append(effective_score)
        if ai_score is not None:
            ai_scores.append(ai_score)
        if human_score is not None:
            human_scores.append(human_score)

        # Flagged count
        is_flagged = bool(row.get("is_flagged"))
        if is_flagged:
            flagged_count += 1

        # Sentiment distribution
        sentiment = None
        eval_data = row.get("evaluation_data") or row.get("ai_evaluation")
        if isinstance(eval_data, dict):
            sentiment = eval_data.get("sentiment")
        elif isinstance(eval_data, str):
            try:
                parsed = json.loads(eval_data)
                sentiment = parsed.get("sentiment")
            except Exception:
                pass
        
        if sentiment:
            sentiment = str(sentiment).capitalize()
            sentiment_distribution[sentiment] = sentiment_distribution.get(sentiment, 0) + 1

        created = row.get("created_at")
        if isinstance(created, datetime):
            created = created.isoformat()

        # Guardar registro procesado simplificado
        filtered_rows.append({
            "id": row.get("id"),
            "created_at": created,
            "customer_name": row.get("customer_name"),
            "agente": row.get("agente"),
            "campana": row.get("campana_nombre") or row.get("campana") or "Sin campaña",
            "effective_score": effective_score,
            "ai_score": ai_score,
            "human_score": human_score,
            "is_flagged": is_flagged,
            "sentiment": sentiment,
        })

    # Calcular estadísticas finales
    total_calls = len(filtered_rows)
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    avg_ai_score = round(sum(ai_scores) / len(ai_scores), 1) if ai_scores else None
    avg_human_score = round(sum(human_scores) / len(human_scores), 1) if human_scores else None
    flagged_rate = round((flagged_count / total_calls) * 100, 1) if total_calls > 0 else 0.0

    return {
        "success": True,
        "filtros": {
            "fecha_inicio": start,
            "fecha_fin": end,
            "campana": campana,
            "agente": agente,
            "min_score": min_score,
            "max_score": max_score,
        },
        "estadisticas": {
            "total_llamadas": total_calls,
            "score_promedio_efectivo": avg_score,
            "score_promedio_ai": avg_ai_score,
            "score_promedio_humano": avg_human_score,
            "llamadas_marcadas": flagged_count,
            "tasa_marcadas_porcentaje": flagged_rate,
            "distribucion_sentimiento": sentiment_distribution,
        },
        "detalles_llamadas": filtered_rows[:50],  # Limitar para no sobrecargar el contexto del modelo
        "mensaje": f"Reporte de estadísticas generado para {total_calls} llamadas entre {start} y {end}.",
    }
