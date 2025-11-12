import React from 'react';
import { REGISTERED_TOOLS } from '../constants';
import { Tool } from '../types';
import { LockIcon } from './icons';

const ToolCard: React.FC<{ tool: Tool }> = ({ tool }) => {
    return (
        <div className="bg-surface rounded-lg shadow-lg p-6 border border-gray-700 hover:border-primary transition-all duration-300 flex flex-col">
            <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-accent break-all">{tool.name}</h3>
                {(tool.requiredRole || tool.requiresApproval) && <LockIcon className="w-5 h-5 text-yellow-400 flex-shrink-0 ml-2" />}
            </div>
            
            <div className="flex flex-wrap gap-2 mt-2">
                 {tool.requiredRole && (
                    <div className="text-xs font-semibold text-yellow-500 bg-yellow-400/10 px-2 py-1 rounded-full">
                        Requires: {tool.requiredRole}
                    </div>
                )}
                {tool.requiresApproval && (
                     <div className="text-xs font-semibold text-orange-500 bg-orange-400/10 px-2 py-1 rounded-full">
                        Needs Approval
                    </div>
                )}
            </div>

            <p className="mt-2 text-sm text-gray-300 flex-grow">{tool.description}</p>
            
            <div className="mt-4">
                <h4 className="font-semibold text-gray-400 text-sm">Input Schema:</h4>
                <pre className="mt-1 text-xs bg-background p-3 rounded-md overflow-x-auto text-gray-400">
                    {JSON.stringify(tool.inputSchema, null, 2)}
                </pre>
            </div>
            <div className="mt-2">
                <h4 className="font-semibold text-gray-400 text-sm">Output Schema:</h4>
                <pre className="mt-1 text-xs bg-background p-3 rounded-md overflow-x-auto text-gray-400">
                    {JSON.stringify(tool.outputSchema, null, 2)}
                </pre>
            </div>
        </div>
    );
}

export const ToolRegistryView: React.FC = () => {
  return (
    <div className="flex flex-col h-full bg-background p-6">
        <header className="mb-6">
            <h2 className="text-2xl font-bold text-white">Tool Registry</h2>
            <p className="text-md text-gray-400">List of currently registered and available tools for the agent.</p>
        </header>
        <div className="flex-1 overflow-y-auto pr-2">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {REGISTERED_TOOLS.map(tool => (
                    <ToolCard key={tool.name} tool={tool} />
                ))}
            </div>
        </div>
    </div>
  );
};