import { forwardRef, type InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';

export interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  min: number;
  max: number;
  step?: number;
  showValue?: boolean;
  valueFormatter?: (value: number) => string;
}

export const Slider = forwardRef<HTMLInputElement, SliderProps>(
  ({ className, label, min, max, step = 1, showValue = true, valueFormatter, id, ...props }, ref) => {
    const sliderId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const value = props.value as number || min;
    const percentage = ((value - min) / (max - min)) * 100;

    return (
      <div className="w-full">
        <div className="flex items-center justify-between mb-1.5">
          {label && (
            <label htmlFor={sliderId} className="block text-caption text-text-muted">
              {label}
            </label>
          )}
          {showValue && (
            <span className="font-mono text-data text-sun whitespace-nowrap">
              {valueFormatter ? valueFormatter(value) : value}
            </span>
          )}
        </div>
        <input
          ref={ref}
          id={sliderId}
          type="range"
          min={min}
          max={max}
          step={step}
          className={clsx('slider', className)}
          style={{
            background: `linear-gradient(to right, var(--color-sun) ${percentage}%, var(--color-border) ${percentage}%)`,
          } as React.CSSProperties}
          {...props}
        />
      </div>
    );
  }
);

Slider.displayName = 'Slider';