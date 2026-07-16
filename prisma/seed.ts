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

const POSTER_TOOL_PARAMETERS: Prisma.InputJsonValue = {
  type: "object",
  properties: {
    titulo_principal: { type: "string", description: "Título del poster (alias: titulo)" },
    titulo: { type: "string" },
    color_esquema: {
      type: "string",
      enum: [
        "corporativo_azul",
        "ecologico_verde",
        "alerta_rojo",
        "minimalista_oscuro",
        "aviso_naranja",
      ],
      description: "Preset de colores (opcional si defines colores manualmente)",
    },
    color_fondo: { type: "string", description: "Hex fondo superior ej. #06140c" },
    color_fondo_secundario: { type: "string", description: "Hex fondo inferior (degradado)" },
    color_texto: { type: "string", description: "Hex color título y encabezados" },
    color_texto_secundario: { type: "string", description: "Hex color cuerpo y pie" },
    color_acento: { type: "string", description: "Hex barras, iconos y acentos" },
    color_badge: { type: "string", description: "Hex texto del badge superior" },
    ancho: { type: "number", description: "Ancho px (400-1400). Default 600" },
    alto: {
      type: "number",
      description: "Alto px opcional; si es muy bajo se auto-ajusta al contenido",
    },
    margen: { type: "number", description: "Margen lateral en px" },
    tamano_fuente_titulo: { type: "number", description: "Título grande: 40-52 recomendado" },
    tamano_fuente_cuerpo: { type: "number", description: "Tamaño fuente cuerpo" },
    tamano_fuente_subtitulo: { type: "number", description: "Tamaño fuente subtítulos de sección" },
    tamano_fuente_pie: { type: "number", description: "Tamaño fuente pie de página" },
    badge_texto: { type: "string", description: "Texto del badge superior ej. INFORMATIVO" },
    tema: { type: "string", description: "Legacy: alerta | info | exito | aviso | neutro" },
    mensaje: { type: "string", description: "Texto único si no usas secciones" },
    subtitulo: { type: "string" },
    pie_pagina: { type: "string" },
    secciones_informativas: {
      type: "array",
      description: "Hasta 3 bloques del cuerpo",
      items: {
        type: "object",
        properties: {
          subtitulo: { type: "string" },
          contenido_texto: { type: "string" },
          icono_svg_sugerido: {
            type: "string",
            enum: ["reciclaje", "grafico_barras", "usuario", "alerta", "agua", "info", "exito"],
          },
        },
        required: ["subtitulo", "contenido_texto"],
      },
    },
  },
  required: [],
};

const POSTER_TOOL: SeedTool = {
  name: "generar_poster_alerta",
  description:
    "Genera poster PNG parametrizable. Elige titulo_principal, secciones_informativas y colores/tamaños (hex y px). Usar cuando pidan poster, cartel o imagen informativa.",
  handlerKey: "generar_poster_alerta",
  parameters: POSTER_TOOL_PARAMETERS,
};

const PRESENTATION_TOOL_PARAMETERS: Prisma.InputJsonValue = {
  type: "object",
  properties: {
    contenido: {
      type: "string",
      description: "Tema, outline o texto base de la presentación.",
    },
    titulo: { type: "string", description: "Título opcional de la presentación." },
    num_diapositivas: {
      type: "number",
      description: "Cantidad de diapositivas (3-30, default 8).",
    },
    idioma: { type: "string", description: "Idioma, ej. Spanish o English." },
    plantilla: { type: "string", description: "Plantilla Presenton, ej. neo-general, education, code." },
    tono: {
      type: "string",
      description: "default | casual | professional | funny | educational | sales_pitch",
    },
    densidad: {
      type: "string",
      description: "concise | standard | text-heavy",
    },
    formato: { type: "string", description: "pptx o pdf." },
    instrucciones: {
      type: "string",
      description: "Instrucciones extra para el generador de diapositivas.",
    },
    archivos: {
      type: "array",
      items: { type: "string" },
      description:
        "Rutas o URLs de imágenes del usuario (storage/ o /files/...). Si no hay ninguna, se usan fondos en degradado.",
    },
    imagenes: {
      type: "array",
      items: { type: "string" },
      description: "Alias de archivos — mismas imágenes del usuario.",
    },
  },
  required: ["contenido"],
};

const PRESENTATION_TOOL: SeedTool = {
  name: "generar_presentacion",
  description:
    "Genera presentación PPTX o PDF vía Presenton (Apache 2.0, self-hosted). " +
    "Imágenes: el usuario las sube (archivos/imagenes); si no hay ninguna → fondos en degradado. " +
    "Sin API de imágenes externa por ahora. Usar para presentación, diapositivas, PowerPoint, PPT o pitch.",
  handlerKey: "generar_presentacion",
  parameters: PRESENTATION_TOOL_PARAMETERS,
};

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
    description:
      "Lista gestiones del CRM. Para cédula/documento usa el parámetro documento (NO cliente). " +
      "cliente es solo para buscar por nombre. gestion_id acepta alias como G00000207. " +
      "solo_ultima=true devuelve la más reciente.",
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
    description:
      "Detalle de UNA gestión por alias (ej. G00000207) o UUID. " +
      "Incluye text_management (texto completo de la gestión). " +
      "Usar cuando pidan texto, detalle o comentario de una gestión específica.",
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
    description:
      "LISTAR las capas (catálogos/niveles) de un árbol de tipificación. " +
      "Usar cuando pidan 'capas del árbol X' o 'catálogos del árbol'. " +
      "NO usar crm_buscar_items_capa para esto. Requiere nombre_arbol o tree_id.",
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
    description:
      "Buscar ÍTEMS dentro de una capa ya identificada (ej. ítems de la capa Canal). " +
      "NO usar para listar capas del árbol — usa crm_arbol_capas. Requiere nombre_capa o catalog_id.",
    handlerKey: "crm_buscar_items_capa",
    parameters: {
      type: "object",
      properties: {
        catalog_id: { type: "string" },
        nombre_capa: { type: "string", description: "Nombre de la capa/catálogo (ej. Canal)" },
        nombre_arbol: { type: "string", description: "Árbol al que pertenece la capa (ej. SAC)" },
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
  POSTER_TOOL,
  PRESENTATION_TOOL,
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

const SALESCLOSER_TOOLS: SeedTool[] = [
  {
    name: "listar_campanas",
    description: "Lista campañas activas o todas las campañas del sistema",
    handlerKey: "listar_campanas",
    parameters: {
      type: "object",
      properties: {
        solo_activas: { type: "boolean" },
        nombre: { type: "string" },
        nombre_exacto: { type: "boolean" },
      },
    },
  },
  {
    name: "listar_criterios_campana",
    description:
      "Lista todos los criterios de evaluación de una campaña Qontrol (supervisor_criteria). Busca la campaña por nombre (ej. BBVA), no solo por ID. Incluye criterios heredados del padre si aplica.",
    handlerKey: "listar_criterios_campana",
    parameters: {
      type: "object",
      properties: {
        campana: { type: "string", description: "Nombre de la campaña (parcial o exacto, ej. BBVA)" },
        campana_id: { type: "number", description: "ID numérico opcional si ya lo conoces" },
        incluir_heredados: { type: "boolean", description: "Incluir criterios heredados de campaña padre (default true)" },
        solo_activos: { type: "boolean", description: "Solo criterios activos (default true)" },
        incluir_prompt: {
          type: "boolean",
          description:
            "true solo si piden el prompt completo de TODOS los criterios; por defecto false (solo títulos)",
        },
      },
      required: ["campana"],
    },
  },
  {
    name: "buscar_criterio_campana",
    description:
      "Busca un criterio por título (ej. 'Tono de voz alta') y devuelve categoria, tipo, peso y prompt. Usar campana='BBVA' para filtrar.",
    handlerKey: "buscar_criterio_campana",
    parameters: {
      type: "object",
      properties: {
        nombre: { type: "string", description: "Nombre o título del criterio a buscar" },
        campana: { type: "string", description: "Opcional: limitar búsqueda a una campaña por nombre" },
        solo_activos: { type: "boolean" },
      },
      required: ["nombre"],
    },
  },
  {
    name: "buscar_llamadas",
    description: "Busca llamadas por ID, fechas, campaña o cliente",
    handlerKey: "buscar_llamadas",
    parameters: {
      type: "object",
      properties: {
        call_id: { type: "number" },
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
        campana: { type: "string" },
        cliente: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "obtener_detalle_llamada",
    description:
      "Detalle de una llamada Qontrol. Usa seccion para devolver solo lo pedido: campana | cliente | agente | score | canal | documento | fecha | resumen | criterios | transcripcion | chat | acustica | callgist | completo",
    handlerKey: "obtener_detalle_llamada",
    parameters: {
      type: "object",
      properties: {
        call_id: { type: "number" },
        seccion: {
          type: "string",
          description:
            "campana | cliente | agente | score | canal | documento | fecha | resumen | criterios | transcripcion | chat | acustica | callgist | completo",
        },
        limite_transcripcion: { type: "number" },
      },
      required: ["call_id"],
    },
  },
  {
    name: "obtener_transcripcion_llamada",
    description: "Obtiene la transcripción de una llamada por su ID",
    handlerKey: "obtener_transcripcion_llamada",
    parameters: {
      type: "object",
      properties: { call_id: { type: "number" } },
      required: ["call_id"],
    },
  },
  {
    name: "resumen_evaluacion_llamada",
    description: "Obtiene score de compliance y evaluación IA de una llamada",
    handlerKey: "resumen_evaluacion_llamada",
    parameters: {
      type: "object",
      properties: { call_id: { type: "number" } },
      required: ["call_id"],
    },
  },
  {
    name: "exportar_excel_salescloser",
    description:
      "PRINCIPAL para Excel: exporta el resultado de un SELECT en SalesCloser. Ej: solo nombres → SELECT customer_name AS nombre FROM calls ORDER BY created_at DESC. Obligatorio cuando pidan columnas custom o todas las llamadas.",
    handlerKey: "exportar_excel_salescloser",
    parameters: {
      type: "object",
      properties: {
        query_sql: { type: "string", description: "SELECT que define columnas y filas del Excel" },
        nombre_hoja: { type: "string", description: "Nombre de la hoja Excel" },
        nombre_archivo: { type: "string", description: "Prefijo del archivo sin extensión" },
        limite: { type: "number", description: "Máximo de filas (default 50000)" },
      },
      required: ["query_sql"],
    },
  },
  {
    name: "reporte_llamadas_excel",
    description:
      "Excel de llamadas con plantilla fija (opcional por fechas). NO usar si piden solo nombres o todas las llamadas sin fechas — usa exportar_excel_salescloser.",
    handlerKey: "reporte_llamadas_excel",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string", description: "Opcional YYYY-MM-DD" },
        fecha_fin: { type: "string", description: "Opcional YYYY-MM-DD" },
        campana: { type: "string" },
        columnas: {
          type: "array",
          items: { type: "string" },
          description: "Ej: ['nombre'] o ['customer_name','created_at']",
        },
        todas: { type: "boolean", description: "true = todas las llamadas sin filtro de fecha" },
      },
    },
  },
  {
    name: "obtener_esquema_salescloser",
    description:
      "PASO 1 OBLIGATORIO antes de SQL: devuelve tablas, columnas reales y patrones SQL de ejemplo. Siempre llamar primero en consultas analíticas o compuestas.",
    handlerKey: "obtener_esquema_salescloser",
    parameters: {
      type: "object",
      properties: {
        tabla: { type: "string", description: "Opcional: filtrar por nombre de tabla (ej. calls)" },
      },
    },
  },
  {
    name: "ejecutar_consulta_salescloser",
    description:
      "PASO 2: ejecuta SELECT de solo lectura en SalesCloser. Solo después de obtener_esquema_salescloser. Una consulta por cada parte del pedido. calls.id (no call_id), campaigns.name, supervisor_criteria.categoria.",
    handlerKey: "ejecutar_consulta_salescloser",
    parameters: {
      type: "object",
      properties: {
        query_sql: { type: "string", description: "Consulta SELECT válida" },
        limite: { type: "number", description: "Filas de muestra (default 100)" },
      },
      required: ["query_sql"],
    },
  },
  {
    name: "listar_escalaciones",
    description: "Lista escalaciones por estado (PENDING, RESOLVED, etc.)",
    handlerKey: "listar_escalaciones",
    parameters: {
      type: "object",
      properties: {
        estado: { type: "string" },
        limite: { type: "number" },
      },
    },
  },
  {
    name: "obtener_reporte_estadisticas",
    description: "Estadísticas agregadas de llamadas (scores, sentimiento, marcadas)",
    handlerKey: "obtener_reporte_estadisticas",
    parameters: {
      type: "object",
      properties: {
        fecha_inicio: { type: "string" },
        fecha_fin: { type: "string" },
        campana: { type: "string" },
        agente: { type: "string" },
        min_score: { type: "number" },
        max_score: { type: "number" },
      },
    },
  },
  POSTER_TOOL,
  PRESENTATION_TOOL,
];

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
      calls: [
        "id",
        "customer_name",
        "customer_document",
        "agent_id",
        "campaign_id",
        "campana",
        "channel",
        "is_flagged",
        "created_at",
      ],
      campaigns: ["id", "name", "description", "parent_id", "is_active"],
      users: ["id", "name", "email"],
      call_evaluations: ["call_id", "compliance_score", "data"],
      call_transcripts: ["call_id", "content"],
      escalations: ["id", "call_id", "status", "level", "reason", "created_at"],
      supervisor_criteria: ["id", "campaign_id", "title", "prompt", "weight", "is_active"],
    },
    funciones_disponibles: [
      "listar_campanas",
      "listar_criterios_campana",
      "buscar_criterio_campana",
      "buscar_llamadas",
      "obtener_detalle_llamada",
      "obtener_transcripcion_llamada",
      "resumen_evaluacion_llamada",
      "obtener_esquema_salescloser",
      "ejecutar_consulta_salescloser",
      "exportar_excel_salescloser",
      "reporte_llamadas_excel",
      "listar_escalaciones",
      "obtener_reporte_estadisticas",
    ],
    reportes: {
      flujo: "1) obtener_esquema_salescloser → 2) ejecutar_consulta_salescloser (una o más veces) → 3) exportar_excel si piden archivo",
      ejemplo_compuesto: [
        "SELECT customer_name FROM calls WHERE id = 166",
        "SELECT sc.categoria FROM supervisor_criteria sc JOIN campaigns c ON c.id = sc.campaign_id WHERE sc.title ILIKE '%Tono de voz alta%' AND c.name ILIKE '%BBVA%'",
        "SELECT c.name, COUNT(sc.id) cnt FROM campaigns c LEFT JOIN supervisor_criteria sc ON sc.campaign_id = c.id GROUP BY c.id, c.name HAVING COUNT(sc.id) < 10",
      ],
      sql_vs_crm: "ejecutar_consulta_salescloser = Qontrol. ejecutar_consulta_crm = CRM (otro proyecto).",
      solo_lectura: "No hay tools de borrado ni UPDATE/DELETE.",
    },
  };

  const salesCloserPrompt = `Eres un asistente interno de SalesCloser / Qontrol.
Respondes en español. Consultas datos reales SOLO mediante herramientas.

FLUJO PRINCIPAL (consultas con datos, reportes, listados, agregaciones):
1. obtener_esquema_salescloser — SIEMPRE primero (columnas reales + patrones SQL)
2. ejecutar_consulta_salescloser — uno o más SELECT según lo que pidió el usuario
3. exportar_excel_salescloser — solo si piden Excel/archivo

EJEMPLO — pedido compuesto:
"nombre llamada 166 + categoría criterio Tono de voz alta BBVA + campañas con menos de 10 criterios"
→ Paso 1: obtener_esquema_salescloser()
→ Paso 2a: SELECT customer_name FROM calls WHERE id = 166
→ Paso 2b: SELECT sc.categoria, sc.title FROM supervisor_criteria sc JOIN campaigns c ON c.id = sc.campaign_id WHERE sc.title ILIKE '%Tono de voz alta%' AND c.name ILIKE '%BBVA%'
→ Paso 2c: SELECT c.name, COUNT(sc.id) AS total FROM campaigns c LEFT JOIN supervisor_criteria sc ON sc.campaign_id = c.id AND sc.is_active GROUP BY c.id, c.name HAVING COUNT(sc.id) < 10
→ Responde en viñetas con los resultados. NUNCA muestres SQL al usuario.

REGLAS SQL:
- calls.id (NO call_id), customer_name = nombre del cliente
- campaigns.name (NO campana en esa tabla)
- supervisor_criteria.categoria para categoría del criterio
- Usa ILIKE para textos; JOIN campaigns ON campaigns.id = supervisor_criteria.campaign_id

TOOLS AUXILIARES (solo si el caso es muy simple, ej. transcripción completa):
- obtener_detalle_llamada(call_id, seccion) · obtener_transcripcion_llamada · listar_campanas

SOLO LECTURA: no hay borrado ni modificación. Nunca digas "eliminado" sin tool de escritura.

PRESENTACIONES: si piden PowerPoint, PPT, diapositivas o pitch → generar_presentacion (no poster).
Si el usuario adjuntó imágenes, pásalas en archivos/imagenes. Si no subió ninguna, la tool usa fondos en degradado automáticamente.

Nunca inventes datos. Si falta un resultado de consulta, ejecuta otra consulta — no adivines.`;

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

IMPORTANTE:
- Tienes herramientas (functions) conectadas al CRM real.
- Para CUALQUIER dato (clientes, gestiones, estadísticas, árboles, capas) DEBES invocar la herramienta correspondiente.
- NUNCA escribas SQL ni digas "puedes usar la función X". Ejecuta la herramienta y responde con los resultados.
- Si no hay resultados, dilo claramente.
- NUNCA inventes datos: si la herramienta falló o devolvió success:false, repítelo y pide lo que falte.
- Capas del árbol → crm_arbol_capas. Ítems dentro de una capa → crm_buscar_items_capa.`;

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
  await upsertProjectTools("demo-salescloser", SALESCLOSER_TOOLS);
  await upsertProjectTools("demo-rrhh", [POSTER_TOOL, PRESENTATION_TOOL]);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
