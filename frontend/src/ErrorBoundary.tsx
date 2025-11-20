import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
	children: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
	error: Error | null;
}

/**
 * Error Boundary component to catch and display React errors gracefully.
 * Prevents the entire app from crashing when a component throws an error.
 */
export class ErrorBoundary extends Component<
	ErrorBoundaryProps,
	ErrorBoundaryState
> {
	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): ErrorBoundaryState {
		// Update state so the next render will show the fallback UI
		return { hasError: true, error };
	}

	componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
		// Log error details to console for debugging
		console.error("Error caught by ErrorBoundary:", error, errorInfo);
	}

	render(): ReactNode {
		if (this.state.hasError && this.state.error) {
			return (
				<div
					style={{
						padding: "2rem",
						backgroundColor: "#141414",
						minHeight: "100vh",
						color: "#e8e8e8",
						fontFamily: "monospace",
					}}
				>
					<div
						style={{
							maxWidth: "800px",
							margin: "0 auto",
							padding: "2rem",
							border: "1px solid #ff3366",
							backgroundColor: "rgba(255, 51, 102, 0.1)",
						}}
					>
						<h1 style={{ color: "#ff3366", marginBottom: "1rem" }}>
							Something went wrong
						</h1>
						<p style={{ marginBottom: "1rem" }}>
							The application encountered an unexpected error.
						</p>
						<details
							style={{
								padding: "1rem",
								backgroundColor: "#0a0a0a",
								border: "1px solid #2a2a2a",
							}}
						>
							<summary style={{ cursor: "pointer", marginBottom: "0.5rem" }}>
								Error details
							</summary>
							<pre
								style={{
									whiteSpace: "pre-wrap",
									fontSize: "0.875rem",
									color: "#ff3366",
								}}
							>
								{this.state.error.toString()}
								{"\n\n"}
								{this.state.error.stack}
							</pre>
						</details>
						<button
							type="button"
							onClick={() => window.location.reload()}
							style={{
								marginTop: "1rem",
								padding: "0.75rem 1.5rem",
								backgroundColor: "#e8e8e8",
								color: "#0a0a0a",
								border: "none",
								cursor: "pointer",
								fontFamily: "monospace",
								fontSize: "0.875rem",
								textTransform: "uppercase",
							}}
						>
							Reload Page
						</button>
					</div>
				</div>
			);
		}

		return this.props.children;
	}
}
