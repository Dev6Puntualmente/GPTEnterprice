import bcrypt from "bcryptjs";
import { PrismaClient, UserRole } from "@prisma/client";
import { buildDatabaseUrl } from "../lib/env";

const prisma = new PrismaClient({
  datasources: {
    db: { url: buildDatabaseUrl() },
  },
});

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
  const email = process.env.SEED_ADMIN_EMAIL ?? "admin@gptenterprice.local";
  const password = process.env.SEED_ADMIN_PASSWORD ?? "Admin1234!";
  const passwordHash = await bcrypt.hash(password, 12);

  const admin = await prisma.user.upsert({
    where: { email },
    update: {
      name: "Administrador",
      passwordHash,
      role: UserRole.ADMIN,
    },
    create: {
      email,
      name: "Administrador",
      passwordHash,
      role: UserRole.ADMIN,
    },
  });

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

  console.log(`Admin: ${admin.email}`);
  console.log(`Password demo: ${password}`);
  console.log(`Proyecto demo: ${project.name} (${project.id})`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
