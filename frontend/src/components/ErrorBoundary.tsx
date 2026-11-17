import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/* App-level error boundary: a fault in one page must never blank the whole
   application. Shows a plain-language recovery panel instead. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("ThreatLens UI error boundary:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center px-4">
          <div className="panel max-w-md p-6 text-center" role="alert">
            <h1 className="text-lg font-semibold text-text">
              This page could not be rendered
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-text-dim">
              An unexpected error occurred while displaying this page. The rest
              of the application remains available.
            </p>
            <p className="mt-2 font-mono text-[11px] text-text-faint">
              {this.state.error.message}
            </p>
            <a
              href="#/"
              className="mt-5 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
            >
              Return to home
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
