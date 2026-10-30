import { clsx } from 'clsx';
import * as TabsPrimitive from '@radix-ui/react-tabs';

interface TabsProps {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

export function Tabs({ value, defaultValue, onValueChange, children, className }: TabsProps) {
  return (
    <TabsPrimitive.Root 
      value={value} 
      defaultValue={defaultValue} 
      onValueChange={onValueChange} 
      className={clsx('w-full', className)}
    >
      {children}
    </TabsPrimitive.Root>
  );
}

interface TabListProps {
  children: React.ReactNode;
  className?: string;
}

export function TabList({ children, className }: TabListProps) {
  return (
    <TabsPrimitive.List
      className={clsx('flex gap-1 p-1 bg-surface/50 rounded-lg border border-border/30', className)}
      aria-label="Tabs"
    >
      {children}
    </TabsPrimitive.List>
  );
}

interface TabProps {
  value: string;
  children: React.ReactNode;
  disabled?: boolean;
  className?: string;
}

export function Tab({ value, children, disabled, className }: TabProps) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      disabled={disabled}
      className={clsx(
        'tab px-4 py-2 rounded-md font-body text-body-sm transition-all duration-fast',
        'data-[state=active]:tab-active',
        disabled && 'opacity-50 pointer-events-none',
        className
      )}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

interface TabPanelProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

export function TabPanel({ value, children, className }: TabPanelProps) {
  return (
    <TabsPrimitive.Content
      value={value}
      className={clsx('animate-fade-in', className)}
    >
      {children}
    </TabsPrimitive.Content>
  );
}