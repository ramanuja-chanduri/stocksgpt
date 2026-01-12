import React, { useCallback, useState } from 'react';
import { Upload, X, File as FileIcon } from 'lucide-react';
import { cn } from '../utils/cn';

interface FileUploadProps {
  onFilesSelected: (files: File[]) => void;
  uploadedFiles: Array<{ file_id: string; file_name: string; file_type: string }>;
  onRemoveFile: (fileId: string) => void;
  disabled?: boolean;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFilesSelected,
  uploadedFiles,
  onRemoveFile,
  disabled = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    const validFiles = files.filter(file => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      return ['.jpg', '.jpeg', '.png', '.webp', '.pdf'].includes(ext);
    });

    if (validFiles.length > 0) {
      onFilesSelected(validFiles);
    }
  }, [disabled, onFilesSelected]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      onFilesSelected(files);
    }
  }, [onFilesSelected]);

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
          isDragging ? "border-primary bg-primary/5" : "border-border",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          multiple
          accept=".jpg,.jpeg,.png,.webp,.pdf"
          onChange={handleFileInput}
          disabled={disabled}
        />
        <label
          htmlFor="file-upload"
          className={cn(
            "cursor-pointer flex flex-col items-center gap-2",
            disabled && "cursor-not-allowed"
          )}
        >
          <Upload className="w-8 h-8 text-muted-foreground" />
          <div>
            <span className="text-sm font-medium text-primary">Click to upload</span>
            <span className="text-sm text-muted-foreground"> or drag and drop</span>
          </div>
          <span className="text-xs text-muted-foreground">
            JPG, PNG, WEBP, PDF (max 20MB)
          </span>
        </label>
      </div>

      {uploadedFiles.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploadedFiles.map((file) => (
            <div
              key={file.file_id}
              className="flex items-center justify-between p-2 bg-muted rounded-md"
            >
              <div className="flex items-center gap-2">
                <FileIcon className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">{file.file_name}</span>
              </div>
              <button
                onClick={() => onRemoveFile(file.file_id)}
                className="p-1 hover:bg-destructive/10 rounded"
                disabled={disabled}
              >
                <X className="w-4 h-4 text-muted-foreground hover:text-destructive" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
