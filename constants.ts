import { Tool, User, Role, Document, Secret, Message, MessageAuthor, LocalLLM } from './types';

export const CONTEXT_WINDOW_LIMIT_CHARS = 4096;

export const SYSTEM_PROMPT: Message = {
    id: 'system-prompt-001',
    author: MessageAuthor.SYSTEM,
    text: 'You are the Confidential Data Steward Agent (CDSA). You must operate under strict security and compliance protocols. All actions are audited. You must request approval for high-risk operations.',
};


export const MOCK_USERS: User[] = [
    { id: 'user-1', name: 'Alex (Analyst)', role: Role.ANALYST },
    { id: 'user-2', name: 'Sam (Manager)', role: Role.MANAGER },
];

export const MOCK_LOCAL_LLMS: LocalLLM[] = [
    { id: 'llm-1', name: 'Llama3-8B-Instruct-Q5', family: 'Llama3', quantization: 'Q5_K_M', sizeGB: 5.6 },
    { id: 'llm-2', name: 'Mistral-7B-Instruct-v0.2-Q6', family: 'Mistral', quantization: 'Q6_K', sizeGB: 5.8 },
    { id: 'llm-3', name: 'Phi3-Mini-4k-Instruct-Q8', family: 'Phi3', quantization: 'Q8_0', sizeGB: 4.1 },
];

export const MOCK_DOCUMENTS: Document[] = [
    { 
        id: 'doc-001', 
        title: 'Data Handling & Classification Policy', 
        type: 'Policy', 
        summary: 'Defines the procedures for classifying, handling, and storing sensitive company and customer data. Outlines access control measures and incident response protocols.',
        classification: 'Confidential',
        indexed: false,
    },
    { 
        id: 'doc-002', 
        title: 'Agent Tool Usage Guide', 
        type: 'Guide', 
        summary: 'A technical guide for developers and analysts on how to register, secure, and use tools within the CDSA environment. Includes best practices for RBAC and approval workflows.',
        classification: 'Internal',
        indexed: false,
    },
    { 
        id: 'doc-003', 
        title: 'Q2 2024 Compliance Audit Report', 
        type: 'Report', 
        summary: 'The official audit report for the second quarter of 2024. Details compliance with internal policies and external regulations. All audit checks passed successfully.',
        classification: 'Confidential',
        indexed: false,
    }
];

export const MOCK_SECURE_VAULT: Secret[] = [
    {
        id: 'secret-001',
        name: 'EXTERNAL_REPORTING_API_KEY',
        description: 'API Key for the external financial reporting service.',
        value: 'sk_live_123abc456def789ghi [REDACTED]',
    },
    {
        id: 'secret-002',
        name: 'DB_CONNECTION_STRING',
        description: 'Connection string for the primary analytics database.',
        value: 'postgresql://user:password@host:port/db [REDACTED]',
    }
];

export const REGISTERED_TOOLS: Tool[] = [
  {
    name: 'current_datetime_tool',
    description: 'Returns the current date and time in ISO format.',
    inputSchema: {},
    outputSchema: { type: 'string', format: 'date-time' },
  },
  {
    name: 'simple_calculator_tool',
    description: 'Performs basic arithmetic operations (+, -, *, /).',
    inputSchema: {
      type: 'object',
      properties: {
        expression: { type: 'string', description: 'e.g., "5 * 2"' },
      },
      required: ['expression'],
    },
    outputSchema: { type: 'number' },
  },
  {
    name: 'read_mock_patient_data',
    description: 'Reads mock patient data for a given patient ID.',
    inputSchema: {
      type: 'object',
      properties: {
        patientId: { type: 'string' },
      },
      required: ['patientId'],
    },
    outputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        dob: { type: 'string' },
        condition: { type: 'string' },
      },
    },
    requiredRole: Role.MANAGER,
  },
  {
      name: 'generate_financial_report',
      description: 'Generates a financial report for a specific quarter.',
      inputSchema: {
          type: 'object',
          properties: {
              quarter: {type: 'string', description: 'e.g., "Q3 2024"'}
          },
          required: ['quarter']
      },
      outputSchema: {
          type: 'object',
          properties: {
              reportUrl: { type: 'string' },
              summary: { type: 'string' }
          }
      },
      requiredRole: Role.MANAGER,
      requiresApproval: true,
  },
  {
    name: 'query_document_store',
    description: 'Searches the internal document knowledge base to answer questions about policies, guides, and reports.',
    inputSchema: {
        type: 'object',
        properties: {
            query: {type: 'string', description: 'The question to ask the document store.'}
        },
        required: ['query']
    },
    outputSchema: {
        type: 'object',
        properties: {
            answer: { type: 'string' },
            source_document_id: { type: 'string' }
        }
    },
  },
  {
    name: 'analyze_sales_data',
    description: 'Analyzes a provided sales data file (e.g., CSV) and returns key metrics and a summary table.',
    inputSchema: {
        type: 'object',
        properties: {
            data_source: {type: 'string', description: 'e.g., "sales_q3_2024.csv"'}
        },
        required: ['data_source']
    },
    outputSchema: {
        type: 'object'
    },
    requiredRole: Role.MANAGER,
  },
  {
    name: 'retrieve_secret_from_vault',
    description: 'Retrieves a secret (e.g., API key) from the secure vault by its name.',
    inputSchema: {
        type: 'object',
        properties: {
            secret_name: {type: 'string', description: 'The name of the secret, e.g., "EXTERNAL_REPORTING_API_KEY"'}
        },
        required: ['secret_name']
    },
    outputSchema: {
        type: 'object',
        properties: {
            secret_value: { type: 'string' }
        }
    },
    requiredRole: Role.MANAGER,
  }
];