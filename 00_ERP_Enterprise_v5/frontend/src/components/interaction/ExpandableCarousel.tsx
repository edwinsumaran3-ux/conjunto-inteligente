import { useState } from 'react';
import './interaction.css';

export interface CarouselItem { id: string; title: string; subtitle?: string; disabled?: boolean; }
interface Props { items: CarouselItem[]; axis?: 'horizontal' | 'vertical'; onOpen: (item: CarouselItem) => void; }

export function ExpandableCarousel({ items, axis = 'horizontal', onOpen }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className={`erp-carousel erp-carousel--${axis}`} role="listbox" aria-label="Opciones">
      {items.map((item) => {
        const active = selected === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={active}
            disabled={item.disabled}
            className={`erp-carousel__item ${active ? 'is-expanded' : ''}`}
            onClick={() => { setSelected(item.id); onOpen(item); }}
          >
            <strong>{item.title}</strong>
            {item.subtitle && <span>{item.subtitle}</span>}
          </button>
        );
      })}
    </div>
  );
}
