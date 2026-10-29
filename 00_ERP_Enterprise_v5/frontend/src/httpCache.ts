let requestSequence = 0;

export function uncachedUrl(url: string): string {
  const separator = url.includes('?') ? '&' : '?';
  const nonce = `${Date.now().toString(36)}-${(++requestSequence).toString(36)}`;
  return `${url}${separator}_request=${nonce}`;
}
