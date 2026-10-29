import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import { forwardRef } from 'react';
import './interaction.css';

type Props = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> & {
  selected?: boolean;
  danger?: boolean;
};

export const TouchActionButton = forwardRef<HTMLButtonElement, Props>(function TouchActionButton(
  { children, selected = false, danger = false, className = '', ...props }, ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      type={props.type ?? 'button'}
      aria-pressed={selected}
      data-danger={danger || undefined}
      className={`touch-action-button ${selected ? 'is-selected' : ''} ${className}`.trim()}
    >
      <span className="touch-action-button__label">{children}</span>
    </button>
  );
});
