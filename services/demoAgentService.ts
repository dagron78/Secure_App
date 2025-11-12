import { Message, MessageAuthor, User, Role, Tool, ApprovalRequest, ApprovalStatus, ToolCall, DataAnalysisResult, AuditEvent, AuditEventType, ComplianceReport, Secret, LocalLLM } from '../types';
import { REGISTERED_TOOLS, MOCK_DOCUMENTS, CONTEXT_WINDOW_LIMIT_CHARS, SYSTEM_PROMPT } from '../constants';

const delay = (ms: number) => new Promise(res => setTimeout(res, ms));

// --- Caching Mechanism ---
interface CacheEntry {
    result: any;
    dataAnalysisResult?: DataAnalysisResult;
    timestamp: number;
}
const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

function getCacheKey(toolName: string, args: any): string {
    return `${toolName}:${JSON.stringify(args)}`;
}
// -------------------------

function findTool(name: string): Tool | undefined {
    return REGISTERED_TOOLS.find(t => t.name === name);
}

interface AgentStreamChunk {
    message?: Message;
    auditEvent?: AuditEvent;
    historyRewrite?: Message[];
}

async function* manageContextWindow(history: Message[], user: User): AsyncGenerator<AgentStreamChunk> {
    const currentSize = JSON.stringify(history).length;

    if (currentSize > CONTEXT_WINDOW_LIMIT_CHARS) {
        const messagesToPruneCount = history.length - 6; // Keep system prompt + last 5
        const prunedMessages = history.slice(1, messagesToPruneCount); // Don't prune system prompt
        
        const summaryMessage: Message = {
            id: crypto.randomUUID(),
            author: MessageAuthor.SYSTEM,
            text: `[Context window limit reached. Summarizing and pruning ${prunedMessages.length} oldest message(s) to maintain conversation history.]`,
            isSummary: true,
        };

        const newHistory = [
            SYSTEM_PROMPT,
            summaryMessage,
            ...history.slice(messagesToPruneCount)
        ];

        yield { historyRewrite: newHistory };
        yield { 
            auditEvent: {
                id: crypto.randomUUID(),
                type: AuditEventType.CONTEXT_WINDOW_PRUNED,
                timestamp: new Date().toISOString(),
                user,
                details: {
                    previousSize: currentSize,
                    newSize: JSON.stringify(newHistory).length,
                    messagesPruned: prunedMessages.length,
                }
            }
        };
    }
}


async function* executeTool(toolCall: ToolCall, user: User, secrets: Secret[]): AsyncGenerator<AgentStreamChunk> {
    const { toolName, args } = toolCall;
    
    // Check cache first
    const cacheKey = getCacheKey(toolName, args);
    const cachedEntry = cache.get(cacheKey);
    if (cachedEntry && (Date.now() - cachedEntry.timestamp < CACHE_TTL_MS)) {
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, toolResult: { toolName, output: cachedEntry.result, isCached: true } }};
        yield { auditEvent: { id: crypto.randomUUID(), type: AuditEventType.CACHED_RESULT_USED, timestamp: new Date().toISOString(), user, details: { toolName, args } }};
        await delay(500);
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.AGENT, text: "I have a cached result for this request. Here it is:", dataAnalysisResult: cachedEntry.dataAnalysisResult } };
        return;
    }
    
    yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, toolCall: toolCall } };
    yield { auditEvent: { id: crypto.randomUUID(), type: AuditEventType.TOOL_CALL_INITIATED, timestamp: new Date().toISOString(), user, details: { toolName, args } } };
    await delay(1500);

    let output: any;
    let dataAnalysisResult: DataAnalysisResult | undefined;

    if (toolName === 'read_mock_patient_data') {
        output = { patientId: args.patientId, name: 'John Doe [REDACTED]', dob: '1980-01-01 [REDACTED]', condition: 'Hypertension [REDACTED]' };
    } else if (toolName === 'generate_financial_report') {
        output = { reportUrl: '/reports/q3-2024.pdf', summary: 'Q3 profits are up by 15%.' };
    } else if (toolName === 'current_datetime_tool') {
        output = new Date().toISOString();
    } else if (toolName === 'simple_calculator_tool') {
        try {
            output = new Function(`return ${args.expression}`)();
        } catch (e) {
            output = 'Error: Invalid expression';
        }
    } else if (toolName === 'query_document_store') {
        const query = args.query.toLowerCase();
        const foundDoc = MOCK_DOCUMENTS.find(doc => doc.title.toLowerCase().includes(query) || doc.summary.toLowerCase().includes(query));
        if (foundDoc) {
            output = { answer: `Based on the document "${foundDoc.title}", here is the relevant information: ${foundDoc.summary}`, source_document_id: foundDoc.id };
        } else {
            output = { answer: "Sorry, I couldn't find any relevant documents matching your query.", source_document_id: null };
        }
    } else if (toolName === 'analyze_sales_data') {
        output = { summary: `Analysis of ${args.data_source} is complete.` };
        dataAnalysisResult = {
            title: `Sales Analysis: ${args.data_source}`,
            headers: ['Product Category', 'Units Sold', 'Revenue', 'Profit Margin'],
            rows: [
                ['Electronics', 1200, '$550,000', '18%'],
                ['Appliances', 850, '$320,000', '15%'],
                ['Software', 3500, '$1,200,000', '65%'],
            ]
        };
    } else if (toolName === 'retrieve_secret_from_vault') {
        const secret = secrets.find(s => s.name === args.secret_name);
        if (secret) {
            output = { secret_value: secret.value.replace(/\[REDACTED\].*$/, '[REDACTED]') };
        } else {
            output = { secret_value: `Error: Secret with name "${args.secret_name}" not found.` };
        }
    }
    
    // Store in cache
    cache.set(cacheKey, { result: output, dataAnalysisResult, timestamp: Date.now() });

    const toolResult = { toolName: toolName, output, isCached: false };
    yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, toolResult: toolResult } };
    yield { auditEvent: { id: crypto.randomUUID(), type: AuditEventType.TOOL_CALL_COMPLETED, timestamp: new Date().toISOString(), user, details: { toolName, result: output } } };
    await delay(500);

    let agentResponseText = '';
    if (toolName === 'current_datetime_tool') {
        agentResponseText = `The current date and time is ${new Date(output).toLocaleString()}.`;
    } else if (toolName === 'simple_calculator_tool') {
        agentResponseText = `The result of \`${args.expression}\` is ${output}.`;
    } else if (toolName === 'query_document_store') {
        agentResponseText = output.answer;
    } else {
        agentResponseText = `Task complete. Here is the result from the tool:\n\`\`\`json\n${JSON.stringify(output, null, 2)}\n\`\`\``;
    }

    yield { message: { id: crypto.randomUUID(), author: MessageAuthor.AGENT, text: agentResponseText, dataAnalysisResult }};
}


async function* processToolCall(toolName: string, args: any, user: User, thinkingMessage: string, secrets: Secret[]): AsyncGenerator<AgentStreamChunk> {
    const tool = findTool(toolName);
    if (!tool) {
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, text: `Error: Tool "${toolName}" not found.`, isError: true } };
        return;
    }

    // 1. Check permissions
    if (tool.requiredRole && user.role !== tool.requiredRole) {
        const messageText = `Permission Denied. Role '${tool.requiredRole}' is required to use the '${tool.name}' tool.`;
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, text: messageText, isError: true } };
        yield { auditEvent: { id: crypto.randomUUID(), type: AuditEventType.SECURITY_ALERT, timestamp: new Date().toISOString(), user, details: { reason: 'RBAC', message: messageText } } };
        return;
    }

    yield { message: { id: crypto.randomUUID(), author: MessageAuthor.AGENT, text: thinkingMessage } };
    await delay(1000);

    const toolCall = { toolName: tool.name, args: args };

    // 2. Check for approval
    if (tool.requiresApproval) {
         if (user.role !== Role.MANAGER) {
            const approvalRequest: ApprovalRequest = {
                id: crypto.randomUUID(),
                requester: user,
                toolCall: toolCall,
                status: ApprovalStatus.PENDING,
                timestamp: new Date().toISOString(),
            };
            yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, approvalRequest: approvalRequest, text: "This action requires approval from a Manager." } };
            yield { auditEvent: { id: crypto.randomUUID(), type: AuditEventType.APPROVAL_REQUESTED, timestamp: new Date().toISOString(), user, details: { toolName, args } } };
            return; // Stop execution until approval is granted
        } else {
             yield { message: { id: crypto.randomUUID(), author: MessageAuthor.AGENT, text: "As a Manager, you can approve your own high-risk actions. Proceeding..." } };
             await delay(1000);
        }
    }

    // 3. Execute
    yield* executeTool(toolCall, user, secrets);
}

export async function* getAgentResponse(userInput: string, user: User, history: Message[], secrets: Secret[], activeModel: LocalLLM): AsyncGenerator<AgentStreamChunk> {
  const currentHistory = [...history];
  yield* manageContextWindow(currentHistory, user);

  yield {
      auditEvent: {
          id: crypto.randomUUID(),
          type: AuditEventType.USER_QUERY,
          timestamp: new Date().toISOString(),
          user,
          details: { query: userInput, modelName: activeModel.name },
      }
  }

  await delay(300);
  const lowerCaseInput = userInput.toLowerCase();

  if (lowerCaseInput.includes('patient')) {
    const patientId = lowerCaseInput.match(/patient\s*(\w+)/)?.[1] || 'P12345';
    yield* processToolCall('read_mock_patient_data', { patientId }, user, "Accessing sensitive patient data...", secrets);
  } else if (lowerCaseInput.includes('report') || lowerCaseInput.includes('financial')) {
    const quarter = lowerCaseInput.match(/(\bQ\d\s*\d{4}\b)/i)?.[0] || 'Q3 2024';
    yield* processToolCall('generate_financial_report', { quarter }, user, "Attempting to generate a financial report...", secrets);
  } else if (lowerCaseInput.includes('time') || lowerCaseInput.includes('date')) {
    yield* processToolCall('current_datetime_tool', {}, user, "Of course. Let me check the current date and time for you.", secrets);
  } else if (lowerCaseInput.includes('calculate') || lowerCaseInput.match(/(\d+\s*[\+\-\*\/]\s*\d+)/)) {
    const match = lowerCaseInput.match(/(\d+(\.\d+)?\s*[\+\-\*\/]\s*\d+(\.\d+)?)/);
    const expression = match ? match[0] : '2+2';
    yield* processToolCall('simple_calculator_tool', { expression }, user, `Sure, I can calculate that.`, secrets);
  } else if (lowerCaseInput.includes('policy') || lowerCaseInput.includes('document') || lowerCaseInput.includes('data handling')) {
      yield* processToolCall('query_document_store', { query: 'data handling' }, user, "Searching the knowledge base for you...", secrets);
  } else if (lowerCaseInput.includes('analyze') && lowerCaseInput.includes('sales')) {
      yield* processToolCall('analyze_sales_data', { data_source: 'sales_q3_2024.csv' }, user, "Performing advanced data analysis...", secrets);
  } else if (lowerCaseInput.includes('secret') || lowerCaseInput.includes('api key')) {
      yield* processToolCall('retrieve_secret_from_vault', { secret_name: 'EXTERNAL_REPORTING_API_KEY' }, user, "Accessing the secure vault...", secrets);
  } else {
    yield {
      message: {
          id: crypto.randomUUID(),
          author: MessageAuthor.AGENT,
          text: `I've received your message: "${userInput}". As a Confidential Data Steward Agent, I am designed to interact with local tools and data sources securely. Try asking me about the "data handling policy" or to "analyze sales data". To test context management, try sending long messages repeatedly.`,
      }
    };
  }
}

export async function* continueAgentResponse(request: ApprovalRequest, user: User, history: Message[], secrets: Secret[], activeModel: LocalLLM): AsyncGenerator<AgentStreamChunk> {
    yield* manageContextWindow(history, user);

    if (request.status === ApprovalStatus.APPROVED) {
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, text: `Request to run '${request.toolCall.toolName}' has been approved. Resuming task.` } };
        await delay(500);
        yield* executeTool(request.toolCall, user, secrets);
    } else {
        yield { message: { id: crypto.randomUUID(), author: MessageAuthor.SYSTEM, text: `Request to run '${request.toolCall.toolName}' was rejected. The task has been cancelled.`, isError: true } };
    }
}


export function generateComplianceReport(log: AuditEvent[], user: User): ComplianceReport {
    if (log.length === 0) {
        return {
            generatedAt: new Date().toISOString(),
            generatedBy: user,
            period: { start: 'N/A', end: 'N/A' },
            summary: { totalEvents: 0, toolCalls: 0, securityAlerts: 0, approvals: 0 },
            log: [],
        };
    }

    const report: ComplianceReport = {
        generatedAt: new Date().toISOString(),
        generatedBy: user,
        period: {
            start: log[0].timestamp,
            end: log[log.length - 1].timestamp,
        },
        summary: {
            totalEvents: log.length,
            toolCalls: log.filter(e => e.type === AuditEventType.TOOL_CALL_INITIATED).length,
            securityAlerts: log.filter(e => e.type === AuditEventType.SECURITY_ALERT).length,
            approvals: log.filter(e => e.type === AuditEventType.APPROVAL_DECISION).length,
        },
        log: [...log].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()), // Most recent first
    };

    return report;
}