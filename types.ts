export enum MessageAuthor {
  USER = 'user',
  AGENT = 'agent',
  SYSTEM = 'system',
}

export enum Role {
    ANALYST = 'Analyst',
    MANAGER = 'Manager',
}

export interface User {
    id: string;
    name: string;
    role: Role;
}

export interface ToolCall {
  toolName: string;
  args: Record<string, any>;
}

export interface ToolResult {
  toolName: string;
  output: any;
  isCached?: boolean;
}

export enum ApprovalStatus {
    PENDING = 'Pending',
    APPROVED = 'Approved',
    REJECTED = 'Rejected',
}

export interface ApprovalRequest {
    id: string;
    requester: User;
    toolCall: ToolCall;
    status: ApprovalStatus;
    timestamp: string;
}

export interface DataAnalysisResult {
    title: string;
    headers: string[];
    rows: (string | number)[][];
}

export interface Message {
  id: string;
  author: MessageAuthor;
  text?: string;
  toolCall?: ToolCall;
  toolResult?: ToolResult;
  isError?: boolean;
  approvalRequest?: ApprovalRequest;
  dataAnalysisResult?: DataAnalysisResult;
  isSummary?: boolean;
}

export interface Tool {
  name: string;
  description: string;
  inputSchema: Record<string, any>;
  outputSchema: Record<string, any>;
  requiredRole?: Role;
  requiresApproval?: boolean;
}

export interface Document {
    id: string;
    title: string;
    type: 'Policy' | 'Guide' | 'Report';
    summary: string;
    classification: 'Confidential' | 'Internal' | 'Public';
    indexed: boolean;
    vectorPosition?: { x: number; y: number };
}

export interface Secret {
    id: string;
    name: string;
    description: string;
    value: string;
}

export enum AppView {
    CHAT = 'chat',
    TOOLS = 'tools',
    APPROVALS = 'approvals',
    DOCUMENTS = 'documents',
    AUDIT = 'audit',
    VAULT = 'vault',
    LLM_GATEWAY = 'llm_gateway',
    VECTOR_STORE = 'vector_store',
}

export enum AuditEventType {
    USER_QUERY = 'USER_QUERY',
    TOOL_CALL_INITIATED = 'TOOL_CALL_INITIATED',
    TOOL_CALL_COMPLETED = 'TOOL_CALL_COMPLETED',
    SECURITY_ALERT = 'SECURITY_ALERT',
    APPROVAL_REQUESTED = 'APPROVAL_REQUESTED',
    APPROVAL_DECISION = 'APPROVAL_DECISION',
    CACHED_RESULT_USED = 'CACHED_RESULT_USED',
    CONTEXT_WINDOW_PRUNED = 'CONTEXT_WINDOW_PRUNED',
    VAULT_SECRET_ADDED = 'VAULT_SECRET_ADDED',
    VAULT_SECRET_UPDATED = 'VAULT_SECRET_UPDATED',
    VAULT_SECRET_DELETED = 'VAULT_SECRET_DELETED',
    VAULT_SECRET_VIEWED = 'VAULT_SECRET_VIEWED',
    LLM_GATEWAY_STATUS_CHANGED = 'LLM_GATEWAY_STATUS_CHANGED',
    LLM_MODEL_CHANGED = 'LLM_MODEL_CHANGED',
    AGENT_MODE_CHANGED = 'AGENT_MODE_CHANGED',
    DOCUMENT_INDEXED = 'DOCUMENT_INDEXED',
}

export interface AuditEvent {
    id: string;
    type: AuditEventType;
    timestamp: string;
    user: User;
    details: Record<string, any>;
}

export interface LocalLLM {
    id: string;
    name: string;
    family: string;
    quantization: string;
    sizeGB: number;
}

export interface LLMGatewayState {
    isConnected: boolean;
    activeModelId: string;
}

export interface ComplianceReport {
    generatedAt: string;
    generatedBy: User;
    period: { start: string; end: string };
    summary: {
        totalEvents: number;
        toolCalls: number;
        securityAlerts: number;
        approvals: number;
    };
    log: AuditEvent[];
}