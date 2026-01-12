import React from 'react';
import { cn } from '../utils/cn';

interface ToggleOption {
  value: string;
  label: string;
}

interface ToggleProps {
  options: ToggleOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export const Toggle: React.FC<ToggleProps> = ({ options, selected, onChange }) => {
  const toggleOption = (value: string) => {
    if (selected.includes(value)) {
      if (selected.length > 1) {
        onChange(selected.filter(v => v !== value));
      }
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex gap-2">
      {options.map(option => (
        <button
          key={option.value}
          onClick={() => toggleOption(option.value)}
          className={cn(
            "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            selected.includes(option.value)
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
};
