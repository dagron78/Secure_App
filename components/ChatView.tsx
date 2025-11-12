import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Message, User, AuditEvent, LocalLLM, LLMGatewayState } from '../types';
import { ChatMessage } from './ChatMessage';
import { SendIcon, ArrowDownOnSquareIcon } from './icons';

interface ChatViewProps {
    currentUser: User;
    messages: Message[];
    onSendMessage: (input: string) => void;
    isLoading: boolean;
    isPendingApproval: boolean;
    auditLog: AuditEvent[];
    activeModel: LocalLLM;
    isDemoMode: boolean;
    llmGatewayState: LLMGatewayState;
}

export const ChatView: React.FC<ChatViewProps> = ({ currentUser, messages, onSendMessage, isLoading, isPendingApproval, auditLog, activeModel, isDemoMode, llmGatewayState }) => {
  const [userInput, setUserInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);
  
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userInput.trim() || isLoading) return;
    onSendMessage(userInput.trim());
    setUserInput('');
  }, [userInput, isLoading, onSendMessage]);
  
  const handleExport = useCallback(() => {
    const sessionData = {
        exportedAt: new Date().toISOString(),
        exportedBy: currentUser,
        messages: messages,
        auditLog: auditLog,
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(sessionData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    const date = new Date().toISOString().split('T')[0];
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `cdsa-session-${currentUser.id}-${date}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  }, [messages, auditLog, currentUser]);

  const isLiveModeAndDisconnected = !isDemoMode && !llmGatewayState.isConnected;
  const isChatLocked = isLoading || isPendingApproval || isLiveModeAndDisconnected;

  const getPlaceholderText = () => {
      if (isPendingApproval) return 'Agent is waiting for approval...';
      if (isLiveModeAndDisconnected) return 'Gateway is disconnected. Cannot send messages.';
      if (isLoading) return 'Processing...';
      return 'Ask the agent...';
  }

  return (
    <div className="flex flex-col h-full bg-background">
        <header className="p-4 border-b border-gray-700 flex justify-between items-center">
            <div>
                <h2 className="text-xl font-semibold text-white">Agent Chat</h2>
                <p className="text-sm text-gray-400">
                    Chatting as: <span className="font-medium text-accent">{currentUser.name} ({currentUser.role})</span>
                </p>
                 <p className="text-sm text-gray-400">
                    Active Model: <span className="font-medium text-accent">{activeModel.name}</span>
                </p>
            </div>
            <div className="flex items-center space-x-4">
                 <div className={`text-sm font-bold px-3 py-1 rounded-full ${isDemoMode ? 'bg-purple-500/20 text-purple-300' : 'bg-green-500/20 text-green-300'}`}>
                    Mode: {isDemoMode ? 'Demo' : 'Live'}
                 </div>
                <button
                    onClick={handleExport}
                    disabled={messages.length === 0}
                    className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-accent bg-surface rounded-lg hover:bg-gray-600 focus:outline-none focus-visible:focus-visible-ring disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    aria-label="Export chat session"
                >
                    <ArrowDownOnSquareIcon className="h-5 w-5" />
                    <span>Export Session</span>
                </button>
            </div>
        </header>
        <div className="flex-1 overflow-y-auto p-6 space-y-6" ref={scrollRef}>
            {messages.length === 0 && !isLoading && (
                <div className="text-center text-gray-500">
                    <p>Start a conversation with the agent.</p>
                    <p className="text-sm mt-2">Try: "Analyze sales data" or "What's the API key?"</p>
                </div>
            )}
            {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
            ))}
            {isLoading && messages.length > 0 && (
                 <div className="flex items-start space-x-3 self-start max-w-2xl">
                    <div className="w-8 h-8 rounded-full bg-surface p-1.5 text-white flex-shrink-0"><div className="w-full h-full rounded-full bg-primary animate-pulse"></div></div>
                    <div className="px-4 py-3 rounded-lg bg-surface">
                        <p className="text-sm font-bold text-primary">Agent</p>
                        <p className="mt-1 text-base text-on-surface animate-pulse">
                            {isPendingApproval ? 'Waiting for approval...' : 'Thinking...'}
                        </p>
                    </div>
                </div>
            )}
        </div>
        <div className="p-4 border-t border-gray-700">
            <form onSubmit={handleSubmit} className="flex items-center space-x-4">
                <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    placeholder={getPlaceholderText()}
                    disabled={isChatLocked}
                    aria-label="User input"
                    className="flex-1 bg-surface px-4 py-3 rounded-lg border border-gray-600 focus:outline-none focus-visible:focus-visible-ring transition-shadow text-white disabled:opacity-50"
                />
                <button
                    type="submit"
                    disabled={isChatLocked || !userInput.trim()}
                    aria-label="Send message"
                    className="bg-primary text-white p-3 rounded-full hover:bg-indigo-500 focus:outline-none focus-visible:focus-visible-ring disabled:bg-gray-500 disabled:cursor-not-allowed transition-colors"
                >
                    <SendIcon className="h-6 w-6" />
                </button>
            </form>
        </div>
    </div>
  );
};