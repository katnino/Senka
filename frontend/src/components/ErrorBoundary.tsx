"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { UiLanguageContext } from "@/lib/uiLanguage";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    name?: string;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error(`[ErrorBoundary${this.props.name ? `: ${this.props.name}` : ""}]`, error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback;
            return (
                <UiLanguageContext.Consumer>
                    {(value) => {
                        const t = value?.t ?? ((key: string) => key);
                        return (
                            <div className="flex items-center justify-center p-4 bg-red-950/40 border border-red-800 rounded-lg m-2">
                                <div className="text-center font-mono">
                                    <div className="text-red-400 text-xs tracking-widest mb-1">⚠ {t("ui.systemError")}</div>
                                    <div className="text-gray-400 text-[10px]">{this.props.name || "Component"} {t("ui.componentFailedToRender")}</div>
                                    <button
                                        onClick={() => this.setState({ hasError: false, error: null })}
                                        className="mt-2 px-3 py-1 text-[10px] bg-red-900/60 hover:bg-red-800/60 text-red-300 rounded border border-red-700 transition-colors"
                                    >
                                        {t("ui.retry")}
                                    </button>
                                </div>
                            </div>
                        );
                    }}
                </UiLanguageContext.Consumer>
            );
        }
        return this.props.children;
    }
}

export default ErrorBoundary;
