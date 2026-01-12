import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Sessions API
export const sessionsApi = {
  list: async () => {
    const response = await apiClient.get('/api/sessions');
    return response.data;
  },
  
  get: async (sessionId: string) => {
    const response = await apiClient.get(`/api/sessions/${sessionId}`);
    return response.data;
  },
  
  create: async (title?: string) => {
    const response = await apiClient.post('/api/sessions', { title });
    return response.data;
  },
  
  delete: async (sessionId: string) => {
    const response = await apiClient.delete(`/api/sessions/${sessionId}`);
    return response.data;
  },
  
  getMessages: async (sessionId: string) => {
    const response = await apiClient.get(`/api/sessions/${sessionId}/messages`);
    return response.data;
  },
};

// Chat API
export const chatApi = {
  send: async (data: {
    message: string;
    session_id?: string;
    model_preferences: string[];
    file_ids?: string[];
  }) => {
    const response = await apiClient.post('/api/chat', data);
    return response.data;
  },
};

// Files API
export const filesApi = {
  upload: async (file: File, sessionId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) {
      formData.append('session_id', sessionId);
    }
    const response = await apiClient.post('/api/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
  
  list: async (sessionId: string) => {
    const response = await apiClient.get(`/api/files/${sessionId}`);
    return response.data;
  },
  
  delete: async (fileId: string) => {
    const response = await apiClient.delete(`/api/files/${fileId}`);
    return response.data;
  },
};

export default apiClient;
