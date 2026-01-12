import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Loader2 } from 'lucide-react';
import { cn } from '../utils/cn';
import 'highlight.js/styles/github-dark.css';

interface LLMResponsePaneProps {
  title: string;
  content: string;
  isLoading: boolean;
  error?: string;
  model: 'gpt-4o' | 'gemini-2.0-flash';
}

export const LLMResponsePane: React.FC<LLMResponsePaneProps> = ({
  title,
  content,
  isLoading,
  error,
  model,
}) => {
  const getModelColor = () => {
    return model === 'gpt-4o' ? 'border-green-500' : 'border-blue-500';
  };

  return (
    <div className={cn("flex flex-col h-full border rounded-lg", getModelColor())}>
      <div className={cn("p-3 border-b font-semibold", getModelColor())}>
        {title}
      </div>
      <div className="flex-1 overflow-auto p-4">
        {isLoading && !content && (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}
        {error && (
          <div className="text-destructive text-sm">
            Error: {error}
          </div>
        )}
        {content && (
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};
