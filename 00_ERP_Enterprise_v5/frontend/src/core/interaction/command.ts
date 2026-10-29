export type InputChannel = 'touch' | 'keyboard' | 'voice' | 'agent' | 'api';
export type RiskTier = 'low' | 'medium' | 'high' | 'critical';

export interface UICommand {
  commandId: string;
  correlationId: string;
  idempotencyKey: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  channel: InputChannel;
  risk: RiskTier;
  args: Record<string, string>;
}

export interface CommandDecision {
  allowed: boolean;
  requiresConfirmation: boolean;
  reasonCode?: string;
}

export interface CommandExecutor {
  authorize(command: UICommand): Promise<CommandDecision>;
  execute(command: UICommand): Promise<void>;
}

export async function executeAuthorized(executor: CommandExecutor, command: UICommand): Promise<void> {
  const decision = await executor.authorize(command);
  if (!decision.allowed) throw new Error('ACTION_NOT_AUTHORIZED');
  if (decision.requiresConfirmation) throw new Error('STEP_UP_CONFIRMATION_REQUIRED');
  await executor.execute(command);
}
