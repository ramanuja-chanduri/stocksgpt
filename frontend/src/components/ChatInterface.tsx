import React, { useState, useEffect, useRef, useCallback } from 'react';
import SplitPane from 'react-split-pane';
import { LLMResponsePane } from './LLMResponsePane';
import { SearchBar } from './SearchBar';
import { Message, FileUpload as FileUploadType } from '../types';
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
  const [modelPreferences, setModelPreferences] = useState<string[]>(['gpt-4o', 'gemini-2.0-flash']);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
    setGptLoading(true);
    setGeminiLoading(true);

    try {
      const response = await chatApi.send({
        message,
        session_id: sessionId || undefined,
        model_preferences: modelPreferences,
        file_ids: fileIds,
      });

      if (!sessionId && response.session_id) {
        onSessionCreated(response.session_id);
      }

      // Update content from responses
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

      // Clear uploaded files after sending
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

  const showGpt = modelPreferences.includes('gpt-4o');
  const showGemini = modelPreferences.includes('gemini-2.0-flash');

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <Toggle
          options={[
            { value: 'gpt-4o', label: 'GPT-4o' },
            { value: 'gemini-2.0-flash', label: 'Gemini 2.0' },
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
                title="GPT-4o"
                content={gptContent}
                isLoading={gptLoading}
                error={gptError}
                model="gpt-4o"
              />
            )}
            {showGemini && (
              <LLMResponsePane
                title="Gemini 2.0 Flash"
                content={geminiContent}
                isLoading={geminiLoading}
                error={geminiError}
                model="gemini-2.0-flash"
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
