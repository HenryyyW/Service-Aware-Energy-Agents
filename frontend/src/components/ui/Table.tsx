import type { ReactNode } from 'react';
import { clsx } from 'clsx';

interface TableProps {
  children: ReactNode;
  className?: string;
}

export function Table({ children, className }: TableProps) {
  return (
    <div className={clsx('w-full overflow-x-auto', className)}>
      <table className="w-full text-sm">
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <thead className={clsx('bg-surface/50 border-b border-border/30', className)}>{children}</thead>;
}

export function TableBody({ children, className }: { children: ReactNode; className?: string }) {
  return <tbody className={clsx('divide-y divide-border/30', className)}>{children}</tbody>;
}

export function TableRow({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return <tr className={clsx('hover:bg-surface/50 transition-colors', className)} onClick={onClick}>{children}</tr>;
}

export function TableHeaderCell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <th className={clsx('px-4 py-3 text-left font-medium text-text-muted uppercase tracking-wider text-xs', className)}>
      {children}
    </th>
  );
}

export function TableCell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <td className={clsx('px-4 py-3 text-text', className)}>
      {children}
    </td>
  );
}