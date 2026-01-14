import React, { useState, useEffect, useRef, useCallback } from 'react';
import SplitPane from 'react-split-pane';
import { LLMResponsePane } from './LLMResponsePane';
import { SearchBar } from './SearchBar';
import { Message, FileUpload as FileUploadType, StreamingChunk } from '../types';
import { chatApi, filesApi } from '../services/api';
import { wsClient } from '../services/websocket';
import { Toggle } from './Toggle';

interface ChatInterfaceProps {
  sessionId: string | null;
  messages: Message[];
  onNewMessage: (message: Message) => void;
  onSessionCreated: (sessionId: string) => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  sessionId,
  messages,
  onNewMessage,
  onSessionCreated,
}) => {
  const [gptContent, setGptContent] = useState('');
  const [geminiContent, setGeminiContent] = useState('');
  const [gptLoading, setGptLoading] = useState(false);
  const [geminiLoading, setGeminiLoading] = useState(false);
  const [gptError, setGptError] = useState<string>();
  const [geminiError, setGeminiError] = useState<string>();
  const [uploadedFiles, setUploadedFiles] = useState<FileUploadType[]>([]);
  const [modelPreferences, setModelPreferences] = useState<string[]>([
    'meta-llama/llama-4-scout-17b-16e-instruct',
    'gemini-3-flash-preview',
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeSessionIdRef = useRef<string | null>(sessionId);
  useEffect(() => {
    activeSessionIdRef.current = sessionId;
  }, [sessionId]);

  // Connect WebSocket once for streaming
  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsUrl = apiBase.replace(/^http/, 'ws') + '/api/chat/stream';
    wsClient.connect(wsUrl);

    const offMessage = wsClient.onMessage((chunk: StreamingChunk) => {
      if ((chunk as any).error) {
        // Backend may send {error: "..."} for general failures
        setGptError((chunk as any).error);
        setGeminiError((chunk as any).error);
        setGptLoading(false);
        setGeminiLoading(false);
        return;
      }

      if (chunk.model === 'meta-llama/llama-4-scout-17b-16e-instruct') {
        if (chunk.content) setGptContent(prev => prev + chunk.content);
        if (chunk.done) setGptLoading(false);
        if (chunk.error) setGptError(chunk.error);
      } else if (chunk.model === 'gemini-3-flash-preview') {
        if (chunk.content) setGeminiContent(prev => prev + chunk.content);
        if (chunk.done) setGeminiLoading(false);
        if (chunk.error) setGeminiError(chunk.error);
      }
    });

    const offError = wsClient.onError((err) => {
      setGptError(String(err));
      setGeminiError(String(err));
      setGptLoading(false);
      setGeminiLoading(false);
    });

    return () => {
      offMessage();
      offError();
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, gptContent, geminiContent]);

  const handleSend = async (message: string, fileIds: string[]) => {
    if (!message.trim()) return;

    setGptContent('');
    setGeminiContent('');
    setGptError(undefined);
    setGeminiError(undefined);
    setGptLoading(modelPreferences.includes('meta-llama/llama-4-scout-17b-16e-instruct'));
    setGeminiLoading(modelPreferences.includes('gemini-3-flash-preview'));

    try {
      // If WebSocket is connected, stream to UI.
      if (wsClient.readyState === WebSocket.OPEN) {
        wsClient.send({
          message,
          session_id: sessionId || null,
          model_preferences: modelPreferences,
          file_ids: fileIds,
        });
        setUploadedFiles([]);
        return;
      }

      // Fallback to non-streaming HTTP if WS isn't available.
      const response = await chatApi.send({
        message,
        session_id: sessionId || undefined,
        model_preferences: modelPreferences,
        file_ids: fileIds,
      });

      if (!sessionId && response.session_id) {
        onSessionCreated(response.session_id);
      }

      response.responses.forEach((msg: Message) => {
        if (msg.role === 'assistant_gpt') {
          setGptContent(msg.content);
          setGptLoading(false);
        } else if (msg.role === 'assistant_gemini') {
          setGeminiContent(msg.content);
          setGeminiLoading(false);
        }
        onNewMessage(msg);
      });

      setUploadedFiles([]);
    } catch (error: any) {
      setGptError(error.response?.data?.detail || error.message);
      setGeminiError(error.response?.data?.detail || error.message);
      setGptLoading(false);
      setGeminiLoading(false);
    }
  };

  const handleFilesSelected = async (files: File[]): Promise<string[]> => {
    const fileIds: string[] = [];
    
    for (const file of files) {
      try {
        const response = await filesApi.upload(file, sessionId || undefined);
        fileIds.push(response.file_id);
        setUploadedFiles(prev => [...prev, response]);
      } catch (error) {
        console.error('Error uploading file:', error);
      }
    }
    
    return fileIds;
  };

  const handleRemoveFile = async (fileId: string) => {
    try {
      await filesApi.delete(fileId);
      setUploadedFiles(prev => prev.filter(f => f.file_id !== fileId));
    } catch (error) {
      console.error('Error removing file:', error);
    }
  };

  const showGpt = modelPreferences.includes('meta-llama/llama-4-scout-17b-16e-instruct');
  const showGemini = modelPreferences.includes('gemini-3-flash-preview');

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <Toggle
          options={[
            { value: 'meta-llama/llama-4-scout-17b-16e-instruct', label: 'Llama (Groq)' },
            { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash' },
          ]}
          selected={modelPreferences}
          onChange={setModelPreferences}
        />
      </div>

      <div className="flex-1 overflow-auto p-4">
        {/* Display conversation history */}
        {messages
          .filter(msg => msg.role === 'user')
          .map((userMsg, idx) => {
            const responses = messages.filter(
              m => m.created_at > userMsg.created_at && m.role.startsWith('assistant')
            );

            return (
              <div key={userMsg.message_id} className="mb-8">
                <div className="mb-2 p-3 bg-muted rounded-lg">
                  {userMsg.content}
                </div>
                {responses.length > 0 && (
                  <div className="grid grid-cols-2 gap-4">
                    {responses.map(response => (
                      <div key={response.message_id} className="p-3 bg-card border rounded-lg">
                        <div className="text-xs text-muted-foreground mb-2">
                          {response.model || response.role}
                        </div>
                        <div className="text-sm">{response.content}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

        {/* Show current responses if loading or have content */}
        {(gptLoading || geminiLoading || gptContent || geminiContent) && (
          <div className="grid grid-cols-2 gap-4 mb-4" style={{ minHeight: '200px' }}>
            {showGpt && (
              <LLMResponsePane
                title="Llama (Groq)"
                content={gptContent}
                isLoading={gptLoading}
                error={gptError}
                model="meta-llama/llama-4-scout-17b-16e-instruct"
              />
            )}
            {showGemini && (
              <LLMResponsePane
                title="Gemini 3 Flash"
                content={geminiContent}
                isLoading={geminiLoading}
                error={geminiError}
                model="gemini-3-flash-preview"
              />
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t">
        <SearchBar
          onSend={handleSend}
          onFilesSelected={handleFilesSelected}
          uploadedFiles={uploadedFiles}
          onRemoveFile={handleRemoveFile}
          disabled={gptLoading || geminiLoading}
        />
      </div>
    </div>
  );
};
