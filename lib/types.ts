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
};
