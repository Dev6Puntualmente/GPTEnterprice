import { hash } from "bcryptjs";
import { Prisma } from "@/generated/prisma/client";
import { UserRole } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";

type SeedTool = {
  name: string;
  description: string;
  handlerKey: string;
  parameters: Prisma.InputJsonValue;
};

async function upsertProjectTools(projectId: string, tools: SeedTool[]) {
  for (const tool of tools) {
    await prisma.tool.upsert({
      where: { projectId_name: { projectId, name: tool.name } },
      update: {
        description: tool.description,
        parameters: tool.parameters,
        handlerKey: tool.handlerKey,
        isActive: true,
      },
      create: {
        projectId,
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters,
        handlerKey: tool.handlerKey,
      },
    });
  }
}

const CRM_TOOLS: SeedTool[] = [
  {
    name: "crm_buscar_clientes",
    description: "Busca clientes por nombre, documento, ciudad o estado.",
    handlerKey: "crm_buscar_clientes",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string" },
        documento: { type: "string" },
        ciudad: { type: "string" },
        estado: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_buscar_usuarios",
    description: "Busca usuarios/agentes del CRM.",
    handlerKey: "crm_buscar_usuarios",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string" },
        role: { type: "string" },
        solo_activos: { type: "boolean" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_listar_gestiones",
    description: "Lista gestiones por cédula, cliente, asesor o fechas. Usa solo_ultima=true para la más reciente.",
    handlerKey: "crm_listar_gestiones",
    parameters: {
      type: "object",
      properties: {
        documento: { type: "string" },
        cliente: { type: "string" },
        asesor: { type: "string" },
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
        gestion_id: { type: "string" },
        limite: { type: "number" },
        solo_ultima: { type: "boolean" },
      },
    },
  },
  {
    name: "crm_obtener_gestion",
    description: "Obtiene una gestión por UUID o alias corto.",
    handlerKey: "crm_obtener_gestion",
    parameters: {
      type: "object",
      properties: { gestion_id: { type: "string" } },
      required: ["gestion_id"],
    },
  },
  {
    name: "crm_dashboard_resumen",
    description: "Métricas resumidas del dashboard: gestiones, clientes nuevos, agentes online.",
    handlerKey: "crm_dashboard_resumen",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
      },
    },
  },
  {
    name: "crm_listar_arboles_tipificacion",
    description: "Lista árboles de tipificación (config.trees).",
    handlerKey: "crm_listar_arboles_tipificacion",
    parameters: {
      type: "object",
      properties: {
        solo_activos: { type: "boolean" },
        nombre: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_arbol_capas",
    description: "Capas/catálogos de un árbol de tipificación ordenadas por nivel.",
    handlerKey: "crm_arbol_capas",
    parameters: {
      type: "object",
      properties: {
        tree_id: { type: "string" },
        nombre_arbol: { type: "string" },
        solo_activas: { type: "boolean" },
      },
    },
  },
  {
    name: "crm_listar_flujos",
    description: "Flujos nombrados de un árbol con sus pasos.",
    handlerKey: "crm_listar_flujos",
    parameters: {
      type: "object",
      properties: {
        tree_id: { type: "string" },
        nombre_arbol: { type: "string" },
        nombre_flujo: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_buscar_items_capa",
    description: "Busca ítems dentro de una capa del árbol de tipificación.",
    handlerKey: "crm_buscar_items_capa",
    parameters: {
      type: "object",
      properties: {
        catalog_id: { type: "string" },
        nombre_capa: { type: "string" },
        tree_id: { type: "string" },
        query: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_dashboard_whatsapp",
    description: "Dashboard WhatsApp: chats activos, mensajes y distribución por estado.",
    handlerKey: "crm_dashboard_whatsapp",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
      },
    },
  },
  {
    name: "crm_dashboard_tipologico",
    description: "Distribución tipológica de gestiones por canal, acción y resultado.",
    handlerKey: "crm_dashboard_tipologico",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_reporte_estados_agentes",
    description: "Auditoría de cambios de estado de agentes (online, pausa, etc.).",
    handlerKey: "crm_reporte_estados_agentes",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
        agente: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "crm_listar_conexiones",
    description: "Lista conexiones/canales activos del CRM.",
    handlerKey: "crm_listar_conexiones",
    parameters: {
      type: "object",
      properties: {
        solo_activas: { type: "boolean" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "generar_poster_alerta",
    description: "Genera un poster visual en SVG (alerta, info, éxito). Devuelve imagen para ver o descargar.",
    handlerKey: "generar_poster_alerta",
    parameters: {
      type: "object",
      properties: {
        titulo: { type: "string" },
        mensaje: { type: "string" },
        subtitulo: { type: "string" },
        tema: { type: "string" },
        pie_pagina: { type: "string" },
      },
      required: ["titulo", "mensaje"],
    },
  },
  {
    name: "crm_resumen_estadisticas",
    description: "Estadísticas globales del CRM.",
    handlerKey: "crm_resumen_estadisticas",
    parameters: { type: "object", properties: {} },
  },
  {
    name: "ejecutar_consulta_crm",
    description: "SQL SELECT de solo lectura en el CRM.",
    handlerKey: "ejecutar_consulta_crm",
    parameters: {
      type: "object",
      properties: { query_sql: { type: "string" } },
      required: ["query_sql"],
    },
  },
];

const RRHH_CONTEXT = {
  nombre: "Proyecto RRHH",
  tablas: {
    users: ["id", "nombre", "hora_entrada", "fecha", "departamento"],
    ventas: ["id", "valor", "asesor_id", "fecha"],
  },
  funciones_disponibles: ["generar_reporte_excel", "buscar_usuario"],
};

const SYSTEM_PROMPT = `Eres un asistente interno de RRHH para la empresa.
Respondes siempre en español, de forma clara y profesional.

Contexto del proyecto:
- Tabla users: id, nombre, hora_entrada, fecha, departamento
- Tabla ventas: id, valor, asesor_id, fecha

Cuando el usuario pida reportes, exportaciones o consultas de datos, usa las herramientas disponibles.
Nunca inventes datos. Si no tienes una herramienta para algo, dilo claramente.
Cuando una herramienta genere un archivo, incluye el enlace en tu respuesta.`;

async function main() {
  const documentId = process.env.SEED_ADMIN_DOCUMENT ?? "1000000001";
  const email = process.env.SEED_ADMIN_EMAIL ?? "admin@gptenterprice.local";
  const password = process.env.SEED_ADMIN_PASSWORD ?? "Admin1234!";
  const passwordHash = await hash(password, 12);

  const admin = await prisma.user.upsert({
    where: { documentId },
    update: {
      name: "Administrador",
      passwordHash,
      role: UserRole.ADMIN,
      email,
    },
    create: {
      documentId,
      email,
      name: "Administrador",
      passwordHash,
      role: UserRole.ADMIN,
    },
  });

  const existingServers = await prisma.aiServerConfig.count({ where: { userId: admin.id } });
  if (existingServers === 0) {
    await prisma.aiServerConfig.create({
      data: {
        userId: admin.id,
        name: "Phi 3.5",
        baseUrl: process.env.VLLM_URL ?? "http://localhost:8002/v1",
        modelName: process.env.VLLM_MODEL ?? "Phi-3.5-mini-instruct",
        apiKey:
          process.env.VLLM_API_KEY?.trim() ||
          process.env.HF_TOKEN?.trim() ||
          null,
        role: "GENERAL",
        color: "#8b5cf6",
        isDefault: true,
      },
    });
  }

  const project = await prisma.project.upsert({
    where: { id: "demo-rrhh" },
    update: {
      ownerId: admin.id,
      name: "Proyecto RRHH",
      description: "Asistente para reportes de usuarios y consultas de entrada",
      systemPrompt: SYSTEM_PROMPT,
      contextJson: RRHH_CONTEXT,
    },
    create: {
      id: "demo-rrhh",
      ownerId: admin.id,
      name: "Proyecto RRHH",
      description: "Asistente para reportes de usuarios y consultas de entrada",
      systemPrompt: SYSTEM_PROMPT,
      contextJson: RRHH_CONTEXT,
      tools: {
        create: [
          {
            name: "generar_reporte_excel",
            description:
              "Genera un reporte en Excel de usuarios que llegaron entre una hora de inicio y hora fin",
            handlerKey: "generar_reporte_excel",
            parameters: {
              type: "object",
              properties: {
                hora_inicio: {
                  type: "string",
                  description: "Hora de inicio en formato HH:MM (24h). Ej: 11:00",
                },
                hora_fin: {
                  type: "string",
                  description: "Hora de fin en formato HH:MM (24h). Ej: 17:00",
                },
                fecha: {
                  type: "string",
                  description: "Fecha en formato YYYY-MM-DD. Si no se indica, usa hoy",
                },
              },
              required: ["hora_inicio", "hora_fin"],
            },
          },
          {
            name: "buscar_usuario",
            description:
              "Busca a qué hora llegó un usuario en una fecha específica, por nombre o ID",
            handlerKey: "buscar_usuario",
            parameters: {
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "Nombre parcial o ID del usuario",
                },
                fecha: {
                  type: "string",
                  description: "Fecha en formato YYYY-MM-DD",
                },
              },
              required: ["query", "fecha"],
            },
          },
        ],
      },
    },
  });

  console.log(`Admin documento: ${admin.documentId}`);
  console.log(`Password demo: ${password}`);
  console.log(`Proyecto demo: ${project.name} (${project.id})`);

  const salesCloserContext = {
    nombre: "SalesCloser AI",
    tablas: {
      calls: ["id", "customer_name", "agent_id", "campaign_id", "created_at"],
      call_transcripts: ["call_id", "content"],
      call_evaluations: ["call_id", "compliance_score", "data"],
      campaigns: ["id", "name", "is_active"],
      escalations: ["id", "call_id", "status", "level", "reason"],
    },
    funciones_disponibles: [
      "listar_campanas",
      "buscar_llamadas",
      "obtener_transcripcion_llamada",
      "resumen_evaluacion_llamada",
      "reporte_llamadas_excel",
      "listar_escalaciones",
    ],
  };

  const salesCloserPrompt = `Eres un asistente interno de SalesCloser / Qontrol.
Respondes en español. Ayudas a supervisores y operadores a consultar llamadas, campañas, transcripciones, evaluaciones y escalaciones.

Usa las herramientas disponibles para consultas de datos reales. Nunca inventes IDs, scores ni URLs.
Si el usuario pide un Excel, el sistema lo genera en segundo plano: no inventes enlaces ni digas que ya está listo hasta tener confirmación.`;

  const salesProject = await prisma.project.upsert({
    where: { id: "demo-salescloser" },
    update: {
      ownerId: admin.id,
      name: "SalesCloser AI",
      description: "Consultas de llamadas, campañas, transcripciones y evaluaciones",
      systemPrompt: salesCloserPrompt,
      contextJson: salesCloserContext,
    },
    create: {
      id: "demo-salescloser",
      ownerId: admin.id,
      name: "SalesCloser AI",
      description: "Consultas de llamadas, campañas, transcripciones y evaluaciones",
      systemPrompt: salesCloserPrompt,
      contextJson: salesCloserContext,
      tools: {
        create: [
          {
            name: "listar_campanas",
            description: "Lista campañas activas o todas las campañas del sistema",
            handlerKey: "listar_campanas",
            parameters: {
              type: "object",
              properties: {
                solo_activas: { type: "boolean", description: "Si true, solo campañas activas" },
              },
            },
          },
          {
            name: "buscar_llamadas",
            description: "Busca llamadas por rango de fechas, nombre de campaña o cliente",
            handlerKey: "buscar_llamadas",
            parameters: {
              type: "object",
              properties: {
                fecha_inicio: { type: "string", description: "YYYY-MM-DD" },
                fecha_fin: { type: "string", description: "YYYY-MM-DD" },
                campana: { type: "string", description: "Nombre parcial de campaña" },
                cliente: { type: "string", description: "Nombre parcial del cliente" },
                limite: { type: "number", description: "Máximo de resultados (default 20)" },
              },
            },
          },
          {
            name: "obtener_transcripcion_llamada",
            description: "Obtiene la transcripción de una llamada por su ID",
            handlerKey: "obtener_transcripcion_llamada",
            parameters: {
              type: "object",
              properties: {
                call_id: { type: "number", description: "ID numérico de la llamada" },
              },
              required: ["call_id"],
            },
          },
          {
            name: "resumen_evaluacion_llamada",
            description: "Obtiene score de compliance y evaluación IA de una llamada",
            handlerKey: "resumen_evaluacion_llamada",
            parameters: {
              type: "object",
              properties: {
                call_id: { type: "number", description: "ID numérico de la llamada" },
              },
              required: ["call_id"],
            },
          },
          {
            name: "reporte_llamadas_excel",
            description: "Genera Excel con llamadas en un rango de fechas",
            handlerKey: "reporte_llamadas_excel",
            parameters: {
              type: "object",
              properties: {
                fecha_inicio: { type: "string", description: "YYYY-MM-DD" },
                fecha_fin: { type: "string", description: "YYYY-MM-DD" },
                campana: { type: "string", description: "Filtrar por campaña (opcional)" },
              },
              required: ["fecha_inicio", "fecha_fin"],
            },
          },
          {
            name: "listar_escalaciones",
            description: "Lista escalaciones por estado (PENDING, RESOLVED, etc.)",
            handlerKey: "listar_escalaciones",
            parameters: {
              type: "object",
              properties: {
                estado: { type: "string", description: "Estado de escalación. Default PENDING" },
                limite: { type: "number", description: "Máximo de resultados" },
              },
            },
          },
          {
            name: "obtener_reporte_estadisticas",
            description: "Obtiene estadísticas agregadas de llamadas (total, promedios, sentiment, marcadas) y detalles simplificados, con soporte para filtrado.",
            handlerKey: "obtener_reporte_estadisticas",
            parameters: {
              type: "object",
              properties: {
                fecha_inicio: { type: "string", description: "YYYY-MM-DD. Opcional (por defecto busca los últimos 30 días)" },
                fecha_fin: { type: "string", description: "YYYY-MM-DD" },
                campana: { type: "string", description: "Filtrar por nombre parcial de campaña (opcional)" },
                agente: { type: "string", description: "Filtrar por nombre parcial de agente/asesor (opcional)" },
                min_score: { type: "number", description: "Score mínimo de compliance (opcional)" },
                max_score: { type: "number", description: "Score máximo de compliance (opcional)" },
              },
            },
          },
        ],
      },
    },
  });

  console.log(`Proyecto SalesCloser: ${salesProject.name} (${salesProject.id})`);

  // ── Proyecto CRM ──────────────────────────────────────────────────────────
  const crmSystemPrompt = `Eres un asistente inteligente del CRM empresarial.
Respondes siempre en español con claridad y precisión.

Puedes consultar:
- Clientes y usuarios/agentes
- Gestiones (historial, última gestión por cédula, gestión por ID/alias)
- Dashboard (métricas por periodo)
- Árboles de tipificación, capas, flujos e ítems de catálogo

Para SQL personalizado usa ejecutar_consulta_crm (solo SELECT).
Nunca inventes datos. Si no hay resultados, dilo claramente.`;

  const crmContext = {
    nombre: "CRM Empresarial",
    esquemas: {
      "crm.clients": ["id", "document_type", "document_number", "full_name", "email", "phone", "city", "department", "client_type", "client_status", "preferred_channel", "created_at"],
      "crm.users": ["id", "username", "email", "full_name", "role", "position", "is_active", "is_online", "phone", "created_at"],
      "whatsapp.whatsapp_chats": ["id", "phone", "name", "status", "last_message_at", "document_number", "created_at"],
      "whatsapp.whatsapp_messages": ["id", "chat_id", "sender", "message_type", "content", "created_at"],
    },
    herramientas: [
      "crm_buscar_clientes",
      "crm_buscar_usuarios",
      "crm_listar_gestiones",
      "crm_obtener_gestion",
      "crm_dashboard_resumen",
      "crm_listar_arboles_tipificacion",
      "crm_arbol_capas",
      "crm_listar_flujos",
      "crm_buscar_items_capa",
      "crm_resumen_estadisticas",
      "ejecutar_consulta_crm",
    ],
  };

  const crmProject = await prisma.project.upsert({
    where: { id: "demo-crm" },
    update: {
      ownerId: admin.id,
      name: "CRM Empresarial",
      description: "Consultas de clientes, gestiones, tipificación y dashboard del CRM",
      systemPrompt: crmSystemPrompt,
      contextJson: crmContext,
    },
    create: {
      id: "demo-crm",
      ownerId: admin.id,
      name: "CRM Empresarial",
      description: "Consultas de clientes, gestiones, tipificación y dashboard del CRM",
      systemPrompt: crmSystemPrompt,
      contextJson: crmContext,
      tools: {
        create: CRM_TOOLS.map((tool) => ({
          name: tool.name,
          description: tool.description,
          handlerKey: tool.handlerKey,
          parameters: tool.parameters,
        })),
      },
    },
  });

  console.log(`Proyecto CRM: ${crmProject.name} (${crmProject.id})`);

  await upsertProjectTools("demo-crm", CRM_TOOLS);
  await upsertProjectTools("demo-salescloser", [
    {
      name: "generar_poster_alerta",
      description: "Genera poster visual en SVG para avisos internos.",
      handlerKey: "generar_poster_alerta",
      parameters: {
        type: "object",
        properties: {
          titulo: { type: "string" },
          mensaje: { type: "string" },
          tema: { type: "string" },
        },
        required: ["titulo", "mensaje"],
      },
    },
  ]);
  await upsertProjectTools("demo-rrhh", [
    {
      name: "generar_poster_alerta",
      description: "Genera poster visual en SVG para comunicados internos.",
      handlerKey: "generar_poster_alerta",
      parameters: {
        type: "object",
        properties: {
          titulo: { type: "string" },
          mensaje: { type: "string" },
          tema: { type: "string" },
        },
        required: ["titulo", "mensaje"],
      },
    },
  ]);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
