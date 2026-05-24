/// <reference types="react-scripts" />

declare namespace NodeJS {
  interface ProcessEnv {
    readonly NODE_ENV: 'development' | 'production' | 'test';
    readonly PUBLIC_URL: string;
    
    // Application Environment Variables
    readonly REACT_APP_BACKEND_URL: string;
    readonly REACT_APP_ORCHESTRATOR_API_URL: string;
    readonly REACT_APP_GEMINI_API_KEY?: string;
    readonly REACT_APP_JWT_SECRET?: string;
    readonly REACT_APP_ENABLE_VISUAL_EDITS?: string;
    readonly REACT_APP_OLLAMA_URL?: string;
    readonly REACT_APP_WS_URL?: string;
    readonly REACT_APP_LOG_LEVEL?: 'debug' | 'info' | 'warn' | 'error';
    readonly REACT_APP_VERSION?: string;
    readonly REACT_APP_SENTRY_DSN?: string;
    readonly REACT_APP_ANALYTICS_ID?: string;
    
    // Build-time variables
    readonly REACT_APP_BUILD_TIME?: string;
    readonly REACT_APP_BUILD_HASH?: string;
    readonly REACT_APP_BUILD_BRANCH?: string;
    
    // Feature flags
    readonly REACT_APP_FEATURE_AUTH?: string;
    readonly REACT_APP_FEATURE_AI?: string;
    readonly REACT_APP_FEATURE_ANALYTICS?: string;
    
    // Third-party integrations
    readonly REACT_APP_STRIPE_PUBLIC_KEY?: string;
    readonly REACT_APP_GOOGLE_CLIENT_ID?: string;
    readonly REACT_APP_FACEBOOK_APP_ID?: string;
  }
}

// Global type extensions
interface Window {
  __REDUX_DEVTOOLS_EXTENSION__?: Function;
  __INITIAL_STATE__?: Record<string, any>;
  gtag?: (...args: any[]) => void;
  dataLayer?: any[];
  ENV?: NodeJS.ProcessEnv;
}

// CSS Modules
declare module '*.module.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module '*.module.scss' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module '*.module.sass' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

// Images and assets
declare module '*.svg' {
  import * as React from 'react';
  
  export const ReactComponent: React.FunctionComponent<
    React.SVGProps<SVGSVGElement> & { title?: string }
  >;
  
  const src: string;
  export default src;
}

declare module '*.png' {
  const value: string;
  export default value;
}

declare module '*.jpg' {
  const value: string;
  export default value;
}

declare module '*.jpeg' {
  const value: string;
  export default value;
}

declare module '*.gif' {
  const value: string;
  export default value;
}

declare module '*.webp' {
  const value: string;
  export default value;
}

declare module '*.ico' {
  const value: string;
  export default value;
}

declare module '*.bmp' {
  const value: string;
  export default value;
}

// Fonts
declare module '*.woff' {
  const value: string;
  export default value;
}

declare module '*.woff2' {
  const value: string;
  export default value;
}

declare module '*.eot' {
  const value: string;
  export default value;
}

declare module '*.ttf' {
  const value: string;
  export default value;
}

declare module '*.otf' {
  const value: string;
  export default value;
}

// Documents
declare module '*.md' {
  const value: string;
  export default value;
}

declare module '*.mdx' {
  const value: React.ComponentType;
  export default value;
}

declare module '*.json' {
  const value: any;
  export default value;
}

declare module '*.yaml' {
  const value: any;
  export default value;
}

declare module '*.yml' {
  const value: any;
  export default value;
}

// Custom types
type DeepPartial<T> = T extends object ? {
  [P in keyof T]?: DeepPartial<T[P]>;
} : T;

type Nullable<T> = T | null;
type Optional<T> = T | undefined;
type Maybe<T> = T | null | undefined;

// Utility types for React
type ReactFC<T = {}> = React.FC<React.PropsWithChildren<T>>;
type ReactComponentProps<T extends keyof JSX.IntrinsicElements | React.JSXElementConstructor<any>> = 
  React.ComponentProps<T>;

// Holographic theme types
interface HolographicTheme {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  surface: string;
  error: string;
  warning: string;
  success: string;
  info: string;
}

// API Response types
interface ApiResponse<T = any> {
  data: T;
  message?: string;
  success: boolean;
  timestamp: string;
  requestId?: string;
}

interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    total: number;
    page: number;
    limit: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: any;
    timestamp: string;
    path?: string;
  };
}

// User and Auth types
interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'user' | 'admin' | 'editor';
  preferences?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
}

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

// Component Props
interface WithClassName {
  className?: string;
}

interface WithChildren {
  children: React.ReactNode;
}

interface WithStyle {
  style?: React.CSSProperties;
}

interface WithTestId {
  'data-testid'?: string;
}

// Event Handlers
type MouseEventHandler<T = Element> = React.MouseEventHandler<T>;
type ChangeEventHandler<T = Element> = React.ChangeEventHandler<T>;
type KeyboardEventHandler<T = Element> = React.KeyboardEventHandler<T>;
type FocusEventHandler<T = Element> = React.FocusEventHandler<T>;
type FormEventHandler<T = Element> = React.FormEventHandler<T>;

// Custom hooks return types
type UseStateReturn<T> = [T, React.Dispatch<React.SetStateAction<T>>];
type UseReducerReturn<S, A> = [S, React.Dispatch<A>];
type UseToggleReturn = [boolean, () => void, (value: boolean) => void];

// API Client types
interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
  withCredentials?: boolean;
}

interface ApiRequestConfig {
  params?: Record<string, any>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

// Environment-specific config
interface AppConfig {
  api: {
    baseURL: string;
    wsURL: string;
    ollamaURL: string;
  };
  features: {
    auth: boolean;
    ai: boolean;
    visualEdits: boolean;
    analytics: boolean;
  };
  thirdParty: {
    sentryDsn?: string;
    analyticsId?: string;
    stripeKey?: string;
  };
  version: string;
  build: {
    time: string;
    hash: string;
    branch: string;
  };
}

// Global declaration for app config
declare const APP_CONFIG: AppConfig;