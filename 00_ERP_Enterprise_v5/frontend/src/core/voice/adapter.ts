import type { InputChannel, UICommand } from '../interaction/command';

export interface Transcript {
  transcriptId: string;
  text: string;
  locale: string;
  confidence: number;
  startedAtEpoch: number;
  endedAtEpoch: number;
}

export interface VoiceIntent {
  action: string;
  args: Record<string, string>;
  risk: 'low' | 'medium' | 'high' | 'critical';
  requiresConfirmation: boolean;
}

export interface VoiceProvider {
  start(): Promise<void>;
  stop(): Promise<void>;
  onTranscript(listener: (transcript: Transcript) => void): () => void;
}

export interface VoiceIntentResolver {
  resolve(transcript: Transcript): Promise<VoiceIntent>;
}

export function intentToCommand(intent: VoiceIntent, base: Omit<UICommand, 'action' | 'args' | 'risk' | 'channel'>): UICommand {
  return { ...base, action: intent.action, args: intent.args, risk: intent.risk, channel: 'voice' as InputChannel };
}
