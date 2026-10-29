const random = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  throw new Error('SECURE_RANDOM_SOURCE_UNAVAILABLE');
};

export function createInteractionIds(): { commandId: string; correlationId: string; idempotencyKey: string } {
  const correlationId = random();
  return { commandId: random(), correlationId, idempotencyKey: random() };
}
