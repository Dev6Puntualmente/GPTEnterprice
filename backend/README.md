# GPTEnterprice Agent API (Python)

Servidor FastAPI que orquesta VLLM + function calling.  
**Puede vivir en repo aparte** — esta carpeta es autocontenida.

## Requisitos

- Python 3.11+
- PostgreSQL (SalesCloserAI)
- VLLM corriendo en puertos 8001 (Qwen) y 8002 (Phi)

## Setup

```powershell
cd backend

# Opción A — venv estándar
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Opción B — si ya tienes ServerVisor como venv
.\ServerVisor\Scripts\activate
pip install -r requirements.txt
```

Copia el `.env` de la raíz del monorepo o crea uno local:

```powershell
copy ..\.env .env
```

## Iniciar servidor

```powershell
# Desde backend/
.\.venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8100
```

O desde la raíz del monorepo:

```powershell
..\scripts\start-backend.ps1
```

Verifica: http://localhost:8100/health  
Tools disponibles: http://localhost:8100/tools

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | PostgreSQL SalesCloser |
| `SALESCLOSER_SCHEMA` | Schema de Qontrol (default: `public`) |
| `VLLM_SMART_URL` | Qwen 7B — tools complejas |
| `VLLM_FAST_URL` | Phi 3.5 — chat rápido |
| `PUBLIC_BASE_URL` | URL pública para descargar Excel |
| `CORS_ORIGINS` | Orígenes Next.js permitidos |

## Tools disponibles

### Demo RRHH (SQLite local)
- `generar_reporte_excel` — Excel usuarios por horario
- `buscar_usuario` — Buscar entrada de usuario

### SalesCloser / Qontrol (PostgreSQL public)
- `listar_campanas` — Campañas activas
- `buscar_llamadas` — Llamadas por fecha/campaña/cliente
- `obtener_transcripcion_llamada` — Transcripción por ID
- `resumen_evaluacion_llamada` — Score compliance + evaluación IA
- `reporte_llamadas_excel` — Exportar llamadas a Excel
- `listar_escalaciones` — Escalaciones por estado

## Estructura

```
backend/
├── main.py           # FastAPI app
├── config.py         # Settings desde .env
├── db.py             # Conexión PostgreSQL SalesCloser
├── services/
│   ├── agent.py      # Loop function calling
│   └── model_router.py
└── tools/
    ├── registry.py   # Registro de handlers
    ├── salescloser.py
    └── ...
```

## Subir a repo aparte

1. Copia la carpeta `backend/` completa
2. Incluye `requirements.txt`, `README.md`, `.env.example`
3. En Next.js cambia `AGENT_API_URL` a la URL del servidor desplegado
