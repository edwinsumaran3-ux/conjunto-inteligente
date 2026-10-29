import React from 'react';
import { UserFailureNotice } from '../../components/UserFailureNotice';
import { userFailureMessage } from '../errors/userFailure';

type Props = { children: React.ReactNode };
type State = { failure: ReturnType<typeof userFailureMessage> | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { failure: null };

  static getDerivedStateFromError(): State {
    return { failure: userFailureMessage(500) };
  }

  componentDidCatch(error: unknown) {
    // Intentionally no console/log payload here: internal telemetry belongs to the backend/agent plane.
    void error;
  }

  render() {
    if (this.state.failure) return <UserFailureNotice failure={this.state.failure} />;
    return this.props.children;
  }
}
