import { useState, useRef } from 'react';
import { Send } from 'lucide-react';
import { FileUpload } from './FileUpload';
import { cn } from '../utils/cn';

interface SearchBarProps {
  onSend: (message: string, fileIds: string[]) => void;
  onFilesSelected: (files: File[]) => Promise<string[]>;
  uploadedFiles: Array<{ file_id: string; file_name: string; file_type: string }>;
  onRemoveFile: (fileId: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  onSend,
  onFilesSelected,
  uploadedFiles,
  onRemoveFile,
  disabled = false,
  placeholder = "Ask about stocks, financial analysis, or upload files...",
}) => {
  const [message, setMessage] = useState('');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = async () => {
    if (!message.trim() || disabled) return;

    const fileIds = uploadedFiles.map(f => f.file_id);
    onSend(message, fileIds);
    setMessage('');
    setShowFileUpload(false);
    
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  return (
    <div className="w-full space-y-4">
      {showFileUpload && (
        <FileUpload
          onFilesSelected={onFilesSelected}
          uploadedFiles={uploadedFiles}
          onRemoveFile={onRemoveFile}
          disabled={disabled}
        />
      )}
      
      <div className="flex gap-2 items-end border rounded-lg p-2 focus-within:ring-2 focus-within:ring-ring">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none border-0 outline-none bg-transparent placeholder:text-muted-foreground min-h-[24px] max-h-[200px]"
        />
        <div className="flex gap-1">
          <button
            onClick={() => setShowFileUpload(!showFileUpload)}
            className={cn(
              "p-2 rounded hover:bg-muted",
              showFileUpload && "bg-muted"
            )}
            disabled={disabled}
          >
            📎
          </button>
          <button
            onClick={handleSend}
            disabled={disabled || !message.trim()}
            className="p-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
