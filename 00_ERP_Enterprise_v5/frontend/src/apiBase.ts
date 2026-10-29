export function configuredApiBase(): string {
  const storedBase = typeof sessionStorage === 'undefined'
    ? ''
    : sessionStorage.getItem('bim.api') || '';
  return storedBase || import.meta.env.VITE_API_BASE_URL || '';
}
