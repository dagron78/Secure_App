import React from 'react';
import { User, LLMGatewayState, Role } from '../types';
import { ChipIcon, ShieldCheckIcon } from './icons';
import { MOCK_LOCAL_LLMS } from '../constants';

interface LLMGatewayViewProps {
    currentUser: User;
    gatewayState: LLMGatewayState;
    onToggleConnection: () => void;
    onChangeActiveModel: (modelId: string) => void;
}

export const LLMGatewayView: React.FC<LLMGatewayViewProps> = ({ currentUser, gatewayState, onToggleConnection, onChangeActiveModel }) => {
    const canManage = currentUser.role === Role.MANAGER;
    const activeModel = MOCK_LOCAL_LLMS.find(m => m.id === gatewayState.activeModelId) || MOCK_LOCAL_LLMS[0];

    return (
        <div className="flex flex-col h-full bg-background p-6">
            <header className="mb-6 flex items-center space-x-3">
                <ChipIcon className="w-8 h-8 text-primary"/>
                <div>
                    <h2 className="text-2xl font-bold text-white">Local LLM Gateway</h2>
                    <p className="text-md text-gray-400">Manage connection and select models for the agent.</p>
                </div>
            </header>
            
            <div className="space-y-8 max-w-4xl mx-auto w-full">
                {/* Connection Status Section */}
                <div className="bg-surface p-6 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold text-white mb-4">Gateway Status</h3>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                            <div className={`w-4 h-4 rounded-full ${gatewayState.isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                            <div>
                                <p className="font-medium text-white">{gatewayState.isConnected ? 'Connected' : 'Disconnected'}</p>
                                <p className="text-sm text-gray-400">The agent {gatewayState.isConnected ? 'can' : 'cannot'} process requests.</p>
                            </div>
                        </div>
                        {canManage ? (
                            <button
                                onClick={onToggleConnection}
                                className={`px-4 py-2 rounded-lg text-sm font-medium ${
                                    gatewayState.isConnected 
                                    ? 'bg-red-600/20 text-red-400 hover:bg-red-600/40' 
                                    : 'bg-green-600/20 text-green-400 hover:bg-green-600/40'
                                }`}
                            >
                                {gatewayState.isConnected ? 'Disconnect' : 'Connect'}
                            </button>
                        ) : (
                             <p className="text-sm text-gray-500 italic">Read-only for Analyst role</p>
                        )}
                    </div>
                </div>

                {/* Model Management Section */}
                <div className="bg-surface p-6 rounded-lg border border-gray-700">
                     <h3 className="text-lg font-semibold text-white mb-4">Model Configuration</h3>
                    {!canManage && (
                         <div className="bg-background/50 border border-yellow-500/30 text-yellow-300 text-sm p-3 rounded-lg mb-4 flex items-center space-x-3">
                            <ShieldCheckIcon className="w-5 h-5 flex-shrink-0" />
                            <p>Only Managers can change the active model. Your current active model is <span className="font-bold">{activeModel.name}</span>.</p>
                        </div>
                    )}
                    <div className="space-y-3">
                        {MOCK_LOCAL_LLMS.map(model => (
                            <div
                                key={model.id}
                                className={`p-4 rounded-lg border-2 flex items-center justify-between transition-all ${
                                    gatewayState.activeModelId === model.id
                                    ? 'border-primary bg-primary/10'
                                    : 'border-gray-700 bg-background/50'
                                }`}
                            >
                                <div>
                                    <p className="font-bold text-white">{model.name}</p>
                                    <div className="flex items-center space-x-4 text-xs text-gray-400 mt-1">
                                        <span>Family: <span className="font-semibold text-gray-300">{model.family}</span></span>
                                        <span>Quantization: <span className="font-semibold text-gray-300">{model.quantization}</span></span>
                                        <span>Size: <span className="font-semibold text-gray-300">{model.sizeGB} GB</span></span>
                                    </div>
                                </div>
                                {canManage && (
                                    <button
                                        onClick={() => onChangeActiveModel(model.id)}
                                        disabled={gatewayState.activeModelId === model.id}
                                        className="bg-primary text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-indigo-500 focus:outline-none focus-visible:focus-visible-ring disabled:bg-gray-500 disabled:cursor-not-allowed disabled:text-gray-300 transition-colors"
                                    >
                                        {gatewayState.activeModelId === model.id ? 'Active' : 'Set Active'}
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};
