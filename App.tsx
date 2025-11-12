import React, { useState, useCallback, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatView } from './components/ChatView';
import { ToolRegistryView } from './components/ToolRegistryView';
import { ApprovalView } from './components/ApprovalView';
import { DocumentView } from './components/DocumentView';
import { AuditView } from './components/AuditView';
import { SecureVaultView } from './components/SecureVaultView';
import { LLMGatewayView } from './components/LLMGatewayView';
import { AppView, User, ApprovalRequest, ApprovalStatus, AuditEvent, Message, MessageAuthor, Secret, AuditEventType, LLMGatewayState, LocalLLM, Document } from './types';
import { MOCK_USERS, SYSTEM_PROMPT, MOCK_SECURE_VAULT, MOCK_LOCAL_LLMS, MOCK_DOCUMENTS } from './constants';
import { getAgentResponse as getDemoAgentResponse, continueAgentResponse as continueDemoAgentResponse } from './services/demoAgentService';
import { getAgentResponse as getLiveAgentResponse, continueAgentResponse as continueLiveAgentResponse } from './services/liveAgentService';


const LOCAL_STORAGE_KEY = 'cdsa_session_state';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>(AppView.CHAT);
  const [currentUser, setCurrentUser] = useState<User>(MOCK_USERS[0]);
  const [messages, setMessages] = useState<Message[]>([SYSTEM_PROMPT]);
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEvent[]>([]);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDemoMode, setIsDemoMode] = useState(true);
  const [llmGatewayState, setLlmGatewayState] = useState<LLMGatewayState>({
    isConnected: true,
    activeModelId: MOCK_LOCAL_LLMS[0].id,
  });

  // Load state from localStorage on initial render
  useEffect(() => {
    try {
      const savedState = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (savedState) {
        const { messages, approvalRequests, auditLog, currentUser, secrets, llmGatewayState, isDemoMode, documents } = JSON.parse(savedState);
        setMessages(messages && messages.length > 0 ? messages : [SYSTEM_PROMPT]);
        setApprovalRequests(approvalRequests || []);
        setAuditLog(auditLog || []);
        setCurrentUser(currentUser || MOCK_USERS[0]);
        setSecrets(secrets || MOCK_SECURE_VAULT);
        setDocuments(documents || MOCK_DOCUMENTS);
        setLlmGatewayState(llmGatewayState || { isConnected: true, activeModelId: MOCK_LOCAL_LLMS[0].id });
        setIsDemoMode(isDemoMode !== undefined ? isDemoMode : true);
      } else {
        setSecrets(MOCK_SECURE_VAULT);
        setDocuments(MOCK_DOCUMENTS);
      }
    } catch (error) {
      console.error("Failed to load state from localStorage", error);
      setSecrets(MOCK_SECURE_VAULT);
      setDocuments(MOCK_DOCUMENTS);
    }
  }, []);

  // Save state to localStorage whenever it changes
  useEffect(() => {
    try {
      const stateToSave = JSON.stringify({ messages, approvalRequests, auditLog, currentUser, secrets, llmGatewayState, isDemoMode, documents });
      localStorage.setItem(LOCAL_STORAGE_KEY, stateToSave);
    } catch (error) {
      console.error("Failed to save state to localStorage", error);
    }
  }, [messages, approvalRequests, auditLog, currentUser, secrets, llmGatewayState, isDemoMode, documents]);

  const handleViewChange = useCallback((view: AppView) => {
    setCurrentView(view);
  }, []);
  
  const addAuditEvent = useCallback((event: AuditEvent) => {
    setAuditLog(prev => [...prev, event]);
  }, []);

  const handleUserChange = useCallback(() => {
    setCurrentUser(prevUser => {
        const currentIndex = MOCK_USERS.findIndex(u => u.id === prevUser.id);
        const nextIndex = (currentIndex + 1) % MOCK_USERS.length;
        return MOCK_USERS[nextIndex];
    });
    // Clear session state for new user
    setMessages([SYSTEM_PROMPT]);
    setApprovalRequests([]);
    setAuditLog([]);
    setSecrets(MOCK_SECURE_VAULT);
    setDocuments(MOCK_DOCUMENTS);
    setLlmGatewayState({ isConnected: true, activeModelId: MOCK_LOCAL_LLMS[0].id });
    setIsDemoMode(true);
    localStorage.removeItem(LOCAL_STORAGE_KEY);
  }, []);

  const addApprovalRequest = useCallback((request: ApprovalRequest) => {
      setApprovalRequests(prev => [...prev, request]);
  }, []);

  const handleApprovalDecision = useCallback((requestId: string, newStatus: ApprovalStatus) => {
    setApprovalRequests(prev => prev.map(req => 
        req.id === requestId ? { ...req, status: newStatus } : req
    ));
  }, []);

  const processAgentStream = useCallback(async (stream: AsyncGenerator<{ message?: Message; auditEvent?: AuditEvent; historyRewrite?: Message[] }>) => {
      for await (const chunk of stream) {
        if (chunk.historyRewrite) {
            setMessages(chunk.historyRewrite);
        }
        if (chunk.message) {
            if (chunk.message.approvalRequest) {
                addApprovalRequest(chunk.message.approvalRequest);
            }
            setMessages(prev => [...prev, chunk.message!]);
        }
        if (chunk.auditEvent) {
            addAuditEvent(chunk.auditEvent);
        }
      }
  }, [addApprovalRequest, addAuditEvent]);

  const activeModel = MOCK_LOCAL_LLMS.find(m => m.id === llmGatewayState.activeModelId) || MOCK_LOCAL_LLMS[0];

  const handleSendMessage = useCallback(async (userInput: string) => {
    setIsLoading(true);
    
    const userMessage: Message = {
      id: crypto.randomUUID(),
      author: MessageAuthor.USER,
      text: userInput,
    };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    
    try {
        const getResponse = isDemoMode ? getDemoAgentResponse : getLiveAgentResponse;
        const responseGenerator = getResponse(userInput, currentUser, newMessages, secrets, activeModel);
        await processAgentStream(responseGenerator);
    } catch (error) {
        console.error("Error getting agent response:", error);
        const errorMessage: Message = {
            id: crypto.randomUUID(),
            author: MessageAuthor.SYSTEM,
            text: "Sorry, an unexpected error occurred while processing your request.",
            isError: true,
        };
        setMessages(prev => [...prev, errorMessage]);
    } finally {
        setIsLoading(false);
    }
  }, [currentUser, messages, processAgentStream, secrets, activeModel, isDemoMode]);

  // Effect to handle resuming conversation after approval decision
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.approvalRequest) {
        const correspondingRequest = approvalRequests.find(req => req.id === lastMessage.approvalRequest!.id);
        if (correspondingRequest && correspondingRequest.status !== ApprovalStatus.PENDING) {
            setIsLoading(true);
            const continueResponse = isDemoMode ? continueDemoAgentResponse : continueLiveAgentResponse;
            const continueStream = continueResponse(correspondingRequest, currentUser, messages, secrets, activeModel);
            processAgentStream(continueStream).finally(() => setIsLoading(false));
            // To prevent re-triggering, create a new message array without the request object
            setMessages(prev => prev.map(msg => msg.id === lastMessage.id ? { ...msg, approvalRequest: undefined } : msg));
        }
    }
  }, [approvalRequests, messages, processAgentStream, currentUser, secrets, activeModel, isDemoMode]);

  const handleAddSecret = useCallback((secret: Omit<Secret, 'id'>) => {
    const newSecret = { ...secret, id: `secret-${crypto.randomUUID()}`};
    setSecrets(prev => [...prev, newSecret]);
    addAuditEvent({
        id: crypto.randomUUID(),
        type: AuditEventType.VAULT_SECRET_ADDED,
        timestamp: new Date().toISOString(),
        user: currentUser,
        details: { secretName: newSecret.name },
    });
  }, [addAuditEvent, currentUser]);

  const handleUpdateSecret = useCallback((updatedSecret: Secret) => {
    setSecrets(prev => prev.map(s => s.id === updatedSecret.id ? updatedSecret : s));
    addAuditEvent({
        id: crypto.randomUUID(),
        type: AuditEventType.VAULT_SECRET_UPDATED,
        timestamp: new Date().toISOString(),
        user: currentUser,
        details: { secretId: updatedSecret.id, secretName: updatedSecret.name },
    });
  }, [addAuditEvent, currentUser]);

  const handleDeleteSecret = useCallback((secretId: string) => {
    const secretToDelete = secrets.find(s => s.id === secretId);
    if(secretToDelete) {
        setSecrets(prev => prev.filter(s => s.id !== secretId));
        addAuditEvent({
            id: crypto.randomUUID(),
            type: AuditEventType.VAULT_SECRET_DELETED,
            timestamp: new Date().toISOString(),
            user: currentUser,
            details: { secretId: secretToDelete.id, secretName: secretToDelete.name },
        });
    }
  }, [secrets, addAuditEvent, currentUser]);
  
  const handleLlmGatewayToggle = useCallback(() => {
    setLlmGatewayState(prev => {
        const newState = !prev.isConnected;
        addAuditEvent({
            id: crypto.randomUUID(),
            type: AuditEventType.LLM_GATEWAY_STATUS_CHANGED,
            timestamp: new Date().toISOString(),
            user: currentUser,
            details: { status: newState ? 'Connected' : 'Disconnected' },
        });
        return { ...prev, isConnected: newState };
    });
  }, [addAuditEvent, currentUser]);

  const handleChangeActiveModel = useCallback((modelId: string) => {
    const model = MOCK_LOCAL_LLMS.find(m => m.id === modelId);
    if (model) {
        setLlmGatewayState(prev => ({ ...prev, activeModelId: modelId }));
        addAuditEvent({
            id: crypto.randomUUID(),
            type: AuditEventType.LLM_MODEL_CHANGED,
            timestamp: new Date().toISOString(),
            user: currentUser,
            details: { newModelName: model.name },
        });
    }
  }, [addAuditEvent, currentUser]);

  const handleToggleDemoMode = useCallback(() => {
      setIsDemoMode(prev => {
          const newMode = !prev;
          addAuditEvent({
              id: crypto.randomUUID(),
              type: AuditEventType.AGENT_MODE_CHANGED,
              timestamp: new Date().toISOString(),
              user: currentUser,
              details: { newMode: newMode ? 'Demo' : 'Live' },
          });
          return newMode;
      });
  }, [addAuditEvent, currentUser]);

  const handleIndexDocument = useCallback((docId: string) => {
    const docToIndex = documents.find(d => d.id === docId);
    if (docToIndex) {
      setDocuments(prev => prev.map(d => d.id === docId ? { ...d, indexed: true } : d));
      addAuditEvent({
        id: crypto.randomUUID(),
        type: AuditEventType.DOCUMENT_INDEXED,
        timestamp: new Date().toISOString(),
        user: currentUser,
        details: { documentId: docId, documentTitle: docToIndex.title },
      });
    }
  }, [documents, addAuditEvent, currentUser]);

  const pendingApprovals = approvalRequests.filter(req => req.status === ApprovalStatus.PENDING);
  const isPendingApproval = messages[messages.length - 1]?.approvalRequest?.id ? approvalRequests.some(req => req.id === messages[messages.length - 1]?.approvalRequest!.id && req.status === ApprovalStatus.PENDING) : false;

  return (
    <div className="flex h-screen w-full bg-background text-on-surface font-sans">
      <Sidebar 
        currentView={currentView} 
        onViewChange={handleViewChange}
        currentUser={currentUser}
        onUserChange={handleUserChange}
        pendingApprovalCount={pendingApprovals.length}
        isDemoMode={isDemoMode}
        onToggleDemoMode={handleToggleDemoMode}
      />
      <main className="flex-1 flex flex-col h-screen">
        {currentView === AppView.CHAT && (
            <ChatView 
                currentUser={currentUser} 
                messages={messages}
                onSendMessage={handleSendMessage}
                isLoading={isLoading}
                isPendingApproval={isPendingApproval}
                auditLog={auditLog}
                activeModel={activeModel}
                isDemoMode={isDemoMode}
                llmGatewayState={llmGatewayState}
            />
        )}
        {currentView === AppView.TOOLS && <ToolRegistryView />}
        {currentView === AppView.DOCUMENTS && (
          <DocumentView 
            documents={documents}
            onIndexDocument={handleIndexDocument}
            currentUser={currentUser}
          />
        )}
        {currentView === AppView.VAULT && (
            <SecureVaultView 
                currentUser={currentUser}
                secrets={secrets}
                onAddSecret={handleAddSecret}
                onUpdateSecret={handleUpdateSecret}
                onDeleteSecret={handleDeleteSecret}
                onNewAuditEvent={addAuditEvent}
            />
        )}
        {currentView === AppView.APPROVALS && (
            <ApprovalView
                requests={pendingApprovals}
                onApprovalDecision={handleApprovalDecision}
                currentUser={currentUser}
                onNewAuditEvent={addAuditEvent}
            />
        )}
        {currentView === AppView.AUDIT && (
            <AuditView
                auditLog={auditLog}
                currentUser={currentUser}
            />
        )}
        {currentView === AppView.LLM_GATEWAY && (
            <LLMGatewayView
                currentUser={currentUser}
                gatewayState={llmGatewayState}
                onToggleConnection={handleLlmGatewayToggle}
                onChangeActiveModel={handleChangeActiveModel}
            />
        )}
      </main>
    </div>
  );
};

export default App;