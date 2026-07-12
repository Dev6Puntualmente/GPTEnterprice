export type ChatMessage = {
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  tool_call_id?: string;
  name?: string;
};

export type ToolDefinition = {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
};

export type ProjectContext = {
  nombre: string;
  tablas?: Record<string, string[]>;
  funciones_disponibles?: string[];
};

export type ChatResponse = {
  message: string;
  model_used: string;
  tool_calls?: Array<{
    name: string;
    arguments: Record<string, unknown>;
    result: string;
  }>;
  files?: string[];
  pending_job?: BackgroundJobSnapshot;
};

export type BackgroundJobSnapshot = {
  id: string;
  tool: string;
  label: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
  progress?: number;
  stage?: string;
};

export type BackgroundJob = BackgroundJobSnapshot & {
  args?: Record<string, unknown>;
  result?: {
    url?: string;
    archivo?: string;
    total_llamadas?: number;
    mensaje?: string;
  };
  error?: string | null;
};

export type MessageMetadata = {
  model_used?: string;
  files?: string[];
  pending_job?: BackgroundJobSnapshot;
  job_status?: BackgroundJobSnapshot["status"];
  job_progress?: number;
  job_stage?: string;
};
