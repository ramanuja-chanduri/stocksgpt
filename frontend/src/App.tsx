import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from './components/Sidebar';
import { ChatInterface } from './components/ChatInterface';
import { Session, Message } from './types';
import { sessionsApi } from './services/api';

const queryClient = new QueryClient();

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (currentSessionId) {
      loadMessages(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId]);

  const loadSessions = async () => {
    try {
      setIsLoading(true);
      const data = await sessionsApi.list();
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].session_id);
      }
    } catch (error) {
      console.error('Error loading sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMessages = async (sessionId: string) => {
    try {
      const data = await sessionsApi.getMessages(sessionId);
      setMessages(data);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const handleNewSession = async () => {
    try {
      const newSession = await sessionsApi.create();
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.session_id);
      setMessages([]);
    } catch (error) {
      console.error('Error creating session:', error);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await sessionsApi.delete(sessionId);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        const remaining = sessions.filter(s => s.session_id !== sessionId);
        setCurrentSessionId(remaining.length > 0 ? remaining[0].session_id : null);
        setMessages([]);
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  };

  const handleNewMessage = (message: Message) => {
    setMessages(prev => [...prev, message]);
  };

  const handleSessionCreated = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    loadSessions();
  };

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-background">
        <Sidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          isLoading={isLoading}
        />
        <div className="flex-1 flex flex-col">
          {currentSessionId ? (
            <ChatInterface
              sessionId={currentSessionId}
              messages={messages}
              onNewMessage={handleNewMessage}
              onSessionCreated={handleSessionCreated}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <p className="text-lg font-medium mb-2">Welcome to StocksGPT</p>
                <p>Select a conversation or create a new one to get started</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </QueryClientProvider>
  );
}

export default App;
