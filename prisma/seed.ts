import { hash } from "bcryptjs";
import { UserRole } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";

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

Usa las herramientas disponibles para consultas de datos reales. Nunca inventes IDs ni scores.
Si generas un Excel, incluye el enlace de descarga en tu respuesta.`;

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
        ],
      },
    },
  });

  console.log(`Proyecto SalesCloser: ${salesProject.name} (${salesProject.id})`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
