// /frontend/src/components/ErrorBoundary.jsx - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React from 'react';
import { theme as tokens } from '../theme';
import { AlertTriangle, Home, Zap } from 'lucide-react';

/**
 * Global error boundary component using the componentDidCatch lifecycle method.
 * Catches errors within its children tree and displays a fallback UI.
 */
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { 
            hasError: false, 
            error: null, 
            errorInfo: null 
        };
    }

    // CRITICAL: This lifecycle method is called after an error has been thrown by a descendant component.
    static getDerivedStateFromError(error) {
        // Update state so the next render will show the fallback UI.
        return { hasError: true };
    }

    // CRITICAL: This lifecycle method logs the error information.
    componentDidCatch(error, errorInfo) {
        // You can also log the error to an error reporting service
        console.error("Uncaught error caught by ErrorBoundary:", error, errorInfo);
        this.setState({
            error: error,
            errorInfo: errorInfo
        });
    }

    render() {
        if (this.state.hasError) {
            // CRITICAL FIX: Render a visually distinct, themed error fallback UI
            return (
                <div style={{ 
                    minHeight: '100vh', 
                    background: tokens.color?.['bg-900'], 
                    display: 'flex', 
                    flexDirection: 'column',
                    justifyContent: 'center', 
                    alignItems: 'center',
                    padding: tokens.spacing?.xl
                }}>
                    <Zap size={64} color={tokens.color?.danger} style={{ marginBottom: tokens.spacing?.lg }} />
                    <h1 style={{ color: tokens.color?.danger, marginBottom: tokens.spacing?.md }}>
                        Critical UI Failure Detected
                    </h1>
                    <p style={{ 
                        color: tokens.color?.['text-100'], 
                        // --- FIX: Added optional chaining ---
                        fontSize: tokens.typography?.h3?.fontSize // FIX: Safe access
                        // ------------------------------------
                    }}>
                        The AI Kernel detected an instability in a core rendering thread.
                    </p>
                    <p style={{ color: tokens.color?.warning }}>
                        Please try navigating to the Dashboard or refreshing the page.
                    </p>
                    
                    <button
                        onClick={() => window.location.href = '/dashboard'}
                        style={{
                            marginTop: tokens.spacing?.xl,
                            padding: '12px 24px',
                            background: tokens.color?.['accent-primary'],
                            color: tokens.color?.['bg-deep'],
                            border: 'none',
                            borderRadius: tokens.border?.radius?.button,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: tokens.spacing?.xs
                        }}
                        className="error-go-home-hover"
                    >
                        <Home size={18} /> Go to Dashboard
                    </button>

                    {/* Optional: Show detailed error trace for admins/devs */}
                    {process.env.NODE_ENV === 'development' && this.state.error && (
                        <details style={{ marginTop: tokens.spacing?.xl, background: tokens.color?.['panel-800'], padding: tokens.spacing?.md, borderRadius: tokens.border?.radius?.card, maxWidth: '80%', color: tokens.color?.['muted-500'] }}>
                            <summary style={{ color: tokens.color?.warning, cursor: 'pointer' }}><AlertTriangle size={16} style={{marginRight: tokens.spacing?.xs}}/> View Technical Details</summary>
                            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                {this.state.error.toString()}
                                <br />
                                {this.state.errorInfo.componentStack}
                            </pre>
                        </details>
                    )}
                </div>
            );
        }

        return this.props.children; 
    }
}

export default ErrorBoundary;