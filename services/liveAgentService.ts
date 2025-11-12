import { Message, MessageAuthor, User, ApprovalRequest, AuditEvent, AuditEventType, Secret, LocalLLM, ApprovalStatus } from '../types';

const AGENT_BACKEND_URL = 'http://localhost:8000/chat/stream';
const CONTINUE_BACKEND_URL = 'http://localhost:8000/chat/continue';


interface AgentStreamChunk {
    message?: Message;
    auditEvent?: AuditEvent;
    historyRewrite?: Message[];
}

async function* processStream(response: Response, user: User): AsyncGenerator<AgentStreamChunk> {
    const reader = response.body?.getReader();
    if (!reader) {
        throw new Error('Failed to get response reader');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            // Process any remaining data in the buffer
            if (buffer.trim()) {
                try {
                    const chunk = JSON.parse(buffer);
                    yield chunk;
                } catch (e) {
                    console.error('Failed to parse final stream chunk:', buffer);
                }
            }
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last partial line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.trim() === '') continue;
            try {
                const chunk: AgentStreamChunk = JSON.parse(line);
                yield chunk;
            } catch (e) {
                console.error('Failed to parse stream chunk:', line, e);
            }
        }
    }
}


export async function* getAgentResponse(userInput: string, user: User, history: Message[], secrets: Secret[], activeModel: LocalLLM): AsyncGenerator<AgentStreamChunk> {
    
    yield {
      auditEvent: {
          id: crypto.randomUUID(),
          type: AuditEventType.USER_QUERY,
          timestamp: new Date().toISOString(),
          user,
          details: { query: userInput, modelName: activeModel.name, mode: 'Live' },
      }
    }

    try {
        const response = await fetch(AGENT_BACKEND_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify({
                userInput,
                history,
                userContext: user,
                activeModelId: activeModel.id,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        yield* processStream(response, user);

    } catch (error) {
        const errorMessage = `Connection to local agent service at ${AGENT_BACKEND_URL} failed. Please ensure the backend service is running.`;
        yield {
            message: {
                id: crypto.randomUUID(),
                author: MessageAuthor.SYSTEM,
                text: errorMessage,
                isError: true,
            }
        };
        yield {
             auditEvent: {
                id: crypto.randomUUID(),
                type: AuditEventType.SECURITY_ALERT,
                timestamp: new Date().toISOString(),
                user,
                details: {
                    reason: "Connection Error",
                    message: `Failed to fetch from agent backend: ${error instanceof Error ? error.message : String(error)}`,
                }
            }
        }
    }
}

export async function* continueAgentResponse(request: ApprovalRequest, user: User, history: Message[], secrets: Secret[], activeModel: LocalLLM): AsyncGenerator<AgentStreamChunk> {
    
    // The audit event for the decision is already created in ApprovalView.
    // A live system might create a "CONTINUATION_INITIATED" event here.

    try {
        const response = await fetch(CONTINUE_BACKEND_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify({
                approvalRequest: request,
                history,
                userContext: user,
                activeModelId: activeModel.id,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        yield* processStream(response, user);

    } catch (error) {
        const errorMessage = `Connection to local agent service at ${CONTINUE_BACKEND_URL} failed while processing approval. Please ensure the backend service is running.`;
        yield {
            message: {
                id: crypto.randomUUID(),
                author: MessageAuthor.SYSTEM,
                text: errorMessage,
                isError: true,
            }
        };
        yield {
             auditEvent: {
                id: crypto.randomUUID(),
                type: AuditEventType.SECURITY_ALERT,
                timestamp: new Date().toISOString(),
                user,
                details: {
                    reason: "Connection Error",
                    message: `Failed to continue agent task: ${error instanceof Error ? error.message : String(error)}`,
                }
            }
        }
    }
}
