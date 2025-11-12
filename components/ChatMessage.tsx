import React, { useState } from 'react';
import { Message, MessageAuthor, DataAnalysisResult } from '../types';
import { AgentIcon, ShieldCheckIcon, TableIcon, ToolsIcon, UserIcon, WarningIcon, ClipboardIcon, ZapIcon, InformationCircleIcon } from './icons';

const AuthorAvatar: React.FC<{ author: MessageAuthor, isError?: boolean, isApproval?: boolean, isSummary?: boolean }> = ({ author, isError, isApproval, isSummary }) => {
    const baseClass = "w-8 h-8 rounded-full flex-shrink-0";
    if (author === MessageAuthor.USER) {
        return <div className={`bg-blue-500 p-1.5 text-white ${baseClass}`}><UserIcon /></div>;
    }
    if (author === MessageAuthor.AGENT) {
        return <div className={`bg-primary p-1.5 text-white ${baseClass}`}><AgentIcon /></div>;
    }
    // System message
    if (isError) {
        return <div className={`bg-red-500 p-1.5 text-white ${baseClass}`}><WarningIcon /></div>;
    }
     if (isApproval) {
        return <div className={`bg-yellow-500 p-1.5 text-white ${baseClass}`}><ShieldCheckIcon /></div>;
    }
    if (isSummary) {
        return <div className={`bg-sky-500 p-1.5 text-white ${baseClass}`}><InformationCircleIcon /></div>
    }
    return <div className={`bg-gray-500 p-1.5 text-white ${baseClass}`}><ToolsIcon /></div>;
}

const AuthorLabel: React.FC<{ author: MessageAuthor, isError?: boolean, isApproval?: boolean, isSummary?: boolean }> = ({ author, isError, isApproval, isSummary }) => {
    const text = author === MessageAuthor.SYSTEM 
        ? (isError ? 'System Error' : isApproval ? 'Approval Required' : isSummary ? 'Context Summary' : 'System') 
        : (author.charAt(0).toUpperCase() + author.slice(1));
    
    let colorClass = 'text-gray-400';
    if (isError) {
        colorClass = 'text-red-400';
    } else if (isApproval) {
        colorClass = 'text-yellow-400';
    } else if (isSummary) {
        colorClass = 'text-sky-400';
    }
    else if (author === MessageAuthor.USER) {
        colorClass = 'text-blue-400';
    } else if (author === MessageAuthor.AGENT) {
        colorClass = 'text-primary';
    }
    
    return <span className={`font-bold text-sm ${colorClass}`}>{text}</span>
}

const CodeBlock: React.FC<{ content: string }> = ({ content }) => {
    const [copied, setCopied] = useState(false);
    
    const handleCopy = () => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative">
            <pre className="text-xs bg-background/50 px-2 py-1 rounded-md overflow-x-auto whitespace-pre-wrap break-all pr-10">
                {content}
            </pre>
            <button 
                onClick={handleCopy}
                className="absolute top-1 right-1 p-1 text-gray-400 bg-surface rounded hover:bg-gray-600 hover:text-white"
                aria-label="Copy to clipboard"
            >
                {copied ? <ShieldCheckIcon className="w-4 h-4 text-green-400"/> : <ClipboardIcon className="w-4 h-4"/>}
            </button>
        </div>
    )
}

const DataAnalysisView: React.FC<{ result: DataAnalysisResult }> = ({ result }) => (
    <div className="mt-2 border-t border-gray-600 pt-2">
        <div className="flex items-center mb-2">
            <TableIcon className="w-5 h-5 text-accent mr-2" />
            <h4 className="font-semibold text-base text-white">{result.title}</h4>
        </div>
        <div className="overflow-x-auto rounded-lg border border-gray-700">
            <table className="w-full text-sm text-left text-gray-300">
                <thead className="bg-gray-800 text-xs text-gray-400 uppercase">
                    <tr>
                        {result.headers.map(header => <th key={header} scope="col" className="px-4 py-2">{header}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {result.rows.map((row, rowIndex) => (
                        <tr key={rowIndex} className="bg-surface border-b border-gray-700 last:border-b-0 hover:bg-gray-700/50">
                            {row.map((cell, cellIndex) => (
                                <td key={cellIndex} className="px-4 py-2">{cell}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    </div>
);


export const ChatMessage: React.FC<{ message: Message }> = ({ message }) => {
  const { author, text, toolCall, toolResult, isError, approvalRequest, dataAnalysisResult, isSummary } = message;

  const isUser = author === MessageAuthor.USER;
  const alignmentClass = isUser ? 'items-end' : 'items-start';

  return (
    <div className={`flex flex-col ${alignmentClass}`}>
        <div className={`flex items-start space-x-3 max-w-2xl ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
            <AuthorAvatar author={author} isError={isError} isApproval={!!approvalRequest} isSummary={isSummary} />
            <div className={`px-4 py-3 rounded-lg ${isUser ? 'bg-primary text-white' : 'bg-surface text-on-surface'} ${isError ? 'border border-red-500/50' : ''} ${approvalRequest ? 'border border-yellow-500/50' : ''} ${isSummary ? 'border border-sky-500/50' : ''}`}>
                <AuthorLabel author={author} isError={isError} isApproval={!!approvalRequest} isSummary={isSummary} />
                {text && <p className="mt-1 text-base whitespace-pre-wrap">{text}</p>}
                {approvalRequest && (
                    <div className="mt-1">
                        <p className="text-sm font-semibold">Action requires approval:</p>
                        <code className="text-sm bg-background/50 px-2 py-1 rounded-md block mt-1 text-accent">
                            {approvalRequest.toolCall.toolName}
                        </code>
                        <p className="text-xs text-gray-400 mt-2">Requested by:</p>
                        <p className="text-xs text-on-surface">{approvalRequest.requester.name}</p>
                        <p className="text-xs text-gray-400 mt-2">Arguments:</p>
                        <CodeBlock content={JSON.stringify(approvalRequest.toolCall.args, null, 2)} />
                        <p className="mt-2 text-sm text-yellow-400 font-semibold">Agent is paused until this request is approved or rejected.</p>
                    </div>
                )}
                {toolCall && (
                    <div className="mt-1">
                        <p className="text-sm font-semibold">Calling Tool:</p>
                        <code className="text-sm bg-background/50 px-2 py-1 rounded-md block mt-1 text-accent">
                            {toolCall.toolName}
                        </code>
                        <p className="text-xs text-gray-400 mt-2">Arguments:</p>
                        <CodeBlock content={JSON.stringify(toolCall.args, null, 2)} />
                    </div>
                )}
                {toolResult && (
                    <div className="mt-1">
                        <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold">Tool Result:</p>
                            {toolResult.isCached && (
                                <div className="flex items-center text-xs text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded-full">
                                    <ZapIcon className="w-3 h-3 mr-1"/>
                                    Cached
                                </div>
                            )}
                        </div>
                        <code className="text-sm bg-background/50 px-2 py-1 rounded-md block mt-1 text-accent">
                            {toolResult.toolName}
                        </code>
                        <p className="text-xs text-gray-400 mt-2">Output:</p>
                        <CodeBlock content={JSON.stringify(toolResult.output, null, 2)} />
                    </div>
                )}
                {dataAnalysisResult && <DataAnalysisView result={dataAnalysisResult} />}
            </div>
        </div>
    </div>
  );
};