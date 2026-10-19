import { type ReactNode, useState, useRef } from 'react';
import { clsx } from 'clsx';
import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '../ui/Button';

interface PanelProps {
  position: 'left' | 'right' | 'bottom';
  className?: string;
  children: ReactNode;
  title?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  width?: string;
  height?: string;
  minWidth?: string;
  maxWidth?: string;
}

export function Panel({
  position,
  className,
  children,
  title,
  collapsible = true,
  defaultOpen = true,
  width,
  height,
  minWidth,
  maxWidth,
}: PanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [isHovered, setIsHovered] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const resizeHandleRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number; width: number; height: number } | null>(null);

  const positionClasses = {
    left: 'fixed left-0 top-0 h-full flex flex-col z-30',
    right: 'fixed right-0 top-0 h-full flex flex-col z-30',
    bottom: 'fixed bottom-0 left-0 right-0 flex flex-col z-30',
  };

  const handleResize = (e: MouseEvent) => {
    if (!dragStart || !panelRef.current) return;

    if (position === 'left' || position === 'right') {
      const delta = position === 'left' ? e.clientX - dragStart.x : dragStart.x - e.clientX;
      const newWidth = Math.max(parseInt(minWidth || '240'), Math.min(parseInt(maxWidth || '480'), dragStart.width + delta));
      panelRef.current.style.width = `${newWidth}px`;
    } else {
      const delta = dragStart.y - e.clientY;
      const newHeight = Math.max(200, Math.min(window.innerHeight * 0.7, dragStart.height + delta));
      panelRef.current.style.height = `${newHeight}px`;
    }
  };

  const handleResizeEnd = () => {
    setDragStart(null);
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', handleResizeEnd);
  };

  const handleResizeStart = (e: React.MouseEvent) => {
    if (!panelRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    setDragStart({
      x: e.clientX,
      y: e.clientY,
      width: panelRef.current.offsetWidth,
      height: panelRef.current.offsetHeight,
    });
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', handleResizeEnd);
  };

  if (!isOpen && position !== 'bottom') {
    return (
      <button
        className={clsx(
          'fixed z-30 panel p-2 btn-ghost',
          position === 'left' ? 'left-2 top-1/2 -translate-y-1/2' : 'right-2 top-1/2 -translate-y-1/2'
        )}
        onClick={() => setIsOpen(true)}
        aria-label={`Open ${position} panel`}
      >
        {position === 'left' ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
      </button>
    );
  }

  if (!isOpen && position === 'bottom') {
    return (
      <button
        className="fixed bottom-2 left-1/2 -translate-x-1/2 z-30 panel p-2 btn-ghost"
        onClick={() => setIsOpen(true)}
        aria-label="Open bottom panel"
      >
        <ChevronUp className="w-5 h-5" />
      </button>
    );
  }

  const panelStyle: React.CSSProperties = {
    width: position !== 'bottom' ? width : undefined,
    height: position === 'bottom' ? height : undefined,
    minWidth: position !== 'bottom' ? minWidth : undefined,
    maxWidth: position !== 'bottom' ? maxWidth : undefined,
  };

  return (
    <div
      ref={panelRef}
      className={clsx(
        'panel flex flex-col transition-all duration-300 ease-spring',
        positionClasses[position],
        className
      )}
      style={panelStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      role="region"
      aria-label={title || `${position} panel`}
    >
      {(title || collapsible) && (
        <div className="flex items-center justify-between p-3 border-b border-border flex-shrink-0">
          {title && <h3 className="font-display font-semibold text-body text-text">{title}</h3>}
          <div className="flex items-center gap-1">
            {collapsible && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(false)}
                aria-label={`Close ${position} panel`}
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              >
                {position === 'left' ? <ChevronLeft className="w-4 h-4" /> : position === 'right' ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto p-3">
        {children}
      </div>

      {/* Resize handle */}
      {position !== 'bottom' && (
        <div
          ref={resizeHandleRef}
          className={clsx(
            'absolute top-0 bottom-0 w-1 cursor-col-resize transition-colors',
            position === 'left' ? 'right-0' : 'left-0',
            isHovered || dragStart ? 'bg-sun/30' : 'bg-transparent'
          )}
          onMouseDown={handleResizeStart}
          aria-label="Resize panel"
          role="separator"
          tabIndex={0}
        />
      )}

      {position === 'bottom' && (
        <div
          ref={resizeHandleRef}
          className="absolute top-0 left-0 right-0 h-1 cursor-row-resize transition-colors"
          style={{ background: isHovered || dragStart ? 'var(--color-sun)' : 'transparent' }}
          onMouseDown={handleResizeStart}
          aria-label="Resize panel"
          role="separator"
          tabIndex={0}
        />
      )}
    </div>
  );
}

export function PanelGroup({ children }: { children: ReactNode }) {
  return <div className="relative">{children}</div>;
}