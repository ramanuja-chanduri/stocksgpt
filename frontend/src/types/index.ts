export interface Session {
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  model: string | null;
  created_at: string;
}

export interface FileUpload {
  file_id: string;
  session_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  cloud_url: string | null;
  uploaded_at: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  model_preferences: string[];
  file_ids?: string[];
}

export interface ChatResponse {
  session_id: string;
  user_message_id: string;
  responses: Message[];
  tool_calls?: any[];
}

export interface StreamingChunk {
  session_id: string;
  message_id: string;
  model: string;
  content: string;
  done: boolean;
  error?: string;
}
