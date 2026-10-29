/** Utilidades de interfaz: selectores, escape HTML, iconos SVG en línea (sin CDNs) y avisos (toasts). */
export const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
export const esc = (s: unknown) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const P: Record<string, string> = {
  cube: '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 22V12M21 7l-9 5-9-5"/>', upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 20h16"/>',
  wifi: '<path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1"/>', warn: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
  xcircle: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>', tree: '<path d="M4 5h6v4H4zM14 11h6v4h-6zM14 17h6v4h-6z"/><path d="M7 9v10h7M7 13h7"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  share: '<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 10.8l7.6-3.6M8.2 13.2l7.6 3.6"/>', flow: '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="18" r="2"/><path d="M7 6h6a3 3 0 0 1 3 3v1M7 18h6a3 3 0 0 0 3-3v-1"/>',
  home: '<path d="M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10"/>', wire: '<path d="M12 3l9 5v8l-9 5-9-5V8z"/><path d="M3 8l9 5 9-5M12 13v8"/>', xray: '<circle cx="12" cy="12" r="3"/><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/>',
  isolate: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><rect x="9" y="9" width="6" height="6"/>', section: '<path d="M3 12h18"/><path d="M6 8l-3 4 3 4M18 8l3 4-3 4"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/>', link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  wrench: '<path d="M14.7 6.3a4 4 0 0 0-5 5L3 18l3 3 6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-2.6-.6-.6-2.6z"/>', shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>', check: '<path d="M5 12l5 5 9-10"/>', dot: '<circle cx="12" cy="12" r="3"/>', chevron: '<path d="M9 6l6 6-6 6"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>', plug: '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
  thermo: '<path d="M10 14V5a2 2 0 0 1 4 0v9a4 4 0 1 1-4 0z"/>', heart: '<path d="M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.5A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z"/>', bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
};
export const icon = (n: string, size = 16) => `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] ?? P.dot}</svg>`;
export function hydrateIcons(root: ParentNode = document) { root.querySelectorAll<HTMLElement>("[data-ic]").forEach((el) => { el.insertAdjacentHTML("afterbegin", icon(el.dataset.ic!, Number(el.dataset.size ?? 16))); el.removeAttribute("data-ic"); }); }
export function toast(text: string, tone: "ok" | "warn" | "bad" | "info" = "info", ms = 4200) {
  const host = $("toasts"); const el = document.createElement("div"); el.className = `toast ${tone}`; el.setAttribute("role", "status"); el.textContent = text; host.appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, ms);
}
export const sevClass = (s?: string | null) => ({ critical: "bad", high: "bad", alto: "bad", critico: "bad", medium: "warn", medio: "warn", warning: "warn", low: "warn", bajo: "warn" } as Record<string, string>)[(s ?? "").toLowerCase()] ?? "ok";
