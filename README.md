# GPTEnterprice — Agente interno con Function Calling

ChatGPT interno configurable por proyecto: **Next.js + Prisma + FastAPI + VLLM**.

Sin Docker. Cada servicio se levanta en su propia terminal.

## Arquitectura

```
Usuario (Next.js :3000)
    ↓
API /api/chat (Next.js + Prisma)
    ↓
FastAPI Agent (:8100) — ejecuta tools en Python
    ↓
VLLM OpenAI-compatible
    ├─ :8001 Qwen2.5-7B  → tools / razonamiento
    └─ :8002 Phi-3.5-mini → chat rápido
```

## Requisitos

- Node.js 20+
- Python 3.11+
- PostgreSQL
- VLLM instalado con GPU (20GB VRAM recomendado)
- Modelos: `Qwen/Qwen2.5-7B-Instruct` y `microsoft/Phi-3.5-mini-instruct`

## Setup rápido

### 1. Variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales PostgreSQL. Puedes usar variables separadas o `DATABASE_URL` completa:

```env
DB_HOST=localhost
DB_PORT=5434
DB_USER=SalesCloser
DB_PASSWORD=tu_password
DB_NAME=SalesCloserAI
DB_SCHEMA=gptenterprice

AUTH_SECRET=genera-un-secreto-largo
NEXTAUTH_URL=http://localhost:3000
```

> **Importante:** GPTEnterprice usa el schema PostgreSQL `gptenterprice` dentro de tu BD existente. No toca las tablas de SalesCloser en `public`.

### 2. Frontend + base de datos + auth

```bash
npm install
npm run db:migrate
npm run db:seed
npm run dev
```

Credenciales demo del seed:
- Email: `admin@gptenterprice.local`
- Password: `Admin1234!`

Login: [http://localhost:3000/login](http://localhost:3000/login)

### 3. Backend Python

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8100
```

O desde la raíz:

```powershell
.\scripts\start-backend.ps1
```

### 4. VLLM (2 terminales o script)

```powershell
.\scripts\start-vllm.ps1
```

Manual:

```bash
# Terminal A — cerebro
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8001 --gpu-memory-utilization 0.35 --tool-call-parser hermes

# Terminal B — chat rápido
vllm serve microsoft/Phi-3.5-mini-instruct --port 8002 --gpu-memory-utilization 0.25
```

### 5. Next.js

```bash
npm run dev
```

Abre [http://localhost:3000/chat](http://localhost:3000/chat) (requiere login)

## Probar

Ejemplos de mensajes:

- `Dame el reporte de usuarios de 11:00 a 17:00 en Excel`
- `¿A qué hora llegó Ana García hoy?`
- `Hola, ¿qué puedes hacer?`

## Tools incluidas (demo RRHH)

| Tool | Descripción |
|------|-------------|
| `generar_reporte_excel` | Excel de usuarios entre dos horas |
| `buscar_usuario` | Consulta hora de entrada por nombre/ID |

Los datos demo están en SQLite (`backend/data/demo.db`), generados automáticamente.

## Agregar un proyecto nuevo

1. Crea el proyecto en Prisma (o extiende el panel en `/projects`)
2. Define tools con `name`, `description`, `parameters` (JSON Schema) y `handlerKey`
3. Implementa el handler en `backend/tools/registry.py`
4. El LLM recibe las tools en formato OpenAI y decide cuándo llamarlas

## Estructura

```
GPTEnterprice/
├── app/                 # Next.js UI + API routes
├── backend/             # FastAPI agent + tools
│   ├── main.py
│   ├── services/        # agent loop + model router
│   └── tools/           # handlers Python
├── prisma/              # Project, Tool, Conversation, Message
└── scripts/             # start-vllm, start-backend (sin Docker)
```

## Licencias de modelos

- **Phi-3.5**: MIT — uso comercial libre
- **Qwen2.5**: Qwen License — uso comercial permitido

## Puertos

| Servicio | Puerto |
|----------|--------|
| Next.js | 3000 |
| FastAPI | 8100 |
| VLLM Qwen 7B | 8001 |
| VLLM Phi 3.5 | 8002 |
