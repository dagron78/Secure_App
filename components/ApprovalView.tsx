import React from 'react';
import { ApprovalRequest, ApprovalStatus, User, Role, AuditEvent, AuditEventType } from '../types';
import { ShieldCheckIcon } from './icons';

interface ApprovalViewProps {
    requests: ApprovalRequest[];
    onApprovalDecision: (requestId: string, newStatus: ApprovalStatus) => void;
    currentUser: User;
    onNewAuditEvent: (event: AuditEvent) => void;
}

const ApprovalCard: React.FC<{
    request: ApprovalRequest;
    onApprove: () => void;
    onReject: () => void;
}> = ({ request, onApprove, onReject }) => {
    return (
        <div className="bg-surface rounded-lg shadow-lg p-6 border border-gray-700">
            <div className="flex justify-between items-start">
                <div>
                    <h3 className="text-lg font-bold text-accent break-all">{request.toolCall.toolName}</h3>
                    <p className="text-xs text-gray-400">Request ID: {request.id}</p>
                </div>
                <div className="text-sm font-semibold text-yellow-500 bg-yellow-400/10 px-3 py-1 rounded-full">
                    {request.status}
                </div>
            </div>

            <div className="mt-4 border-t border-gray-700 pt-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <p className="text-gray-400 font-semibold">Requester</p>
                        <p className="text-white">{request.requester.name} ({request.requester.role})</p>
                    </div>
                    <div>
                        <p className="text-gray-400 font-semibold">Timestamp</p>
                        <p className="text-white">{new Date(request.timestamp).toLocaleString()}</p>
                    </div>
                </div>
                 <div className="mt-4">
                    <p className="text-gray-400 font-semibold">Arguments</p>
                    <pre className="mt-1 text-xs bg-background p-3 rounded-md overflow-x-auto text-gray-400">
                        {JSON.stringify(request.toolCall.args, null, 2)}
                    </pre>
                </div>
            </div>

            <div className="mt-6 flex items-center justify-end space-x-3">
                <button 
                    onClick={onReject}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600/20 border border-red-500 rounded-lg hover:bg-red-500/40 transition-colors">
                    Reject
                </button>
                 <button 
                    onClick={onApprove}
                    className="px-4 py-2 text-sm font-medium text-white bg-green-600/20 border border-green-500 rounded-lg hover:bg-green-500/40 transition-colors">
                    Approve
                </button>
            </div>
        </div>
    )
}

export const ApprovalView: React.FC<ApprovalViewProps> = ({ requests, onApprovalDecision, currentUser, onNewAuditEvent }) => {
    const canApprove = currentUser.role === Role.MANAGER;
    
    const handleDecision = (requestId: string, newStatus: ApprovalStatus) => {
        onApprovalDecision(requestId, newStatus);
        const request = requests.find(r => r.id === requestId);
        if (request) {
            onNewAuditEvent({
                id: crypto.randomUUID(),
                type: AuditEventType.APPROVAL_DECISION,
                timestamp: new Date().toISOString(),
                user: currentUser,
                details: {
                    requestId: request.id,
                    toolName: request.toolCall.toolName,
                    decision: newStatus,
                },
            });
        }
    };

    return (
        <div className="flex flex-col h-full bg-background p-6">
            <header className="mb-6">
                <h2 className="text-2xl font-bold text-white">Approval Dashboard</h2>
                <p className="text-md text-gray-400">Review and decide on pending agent actions.</p>
            </header>
            <div className="flex-1 overflow-y-auto pr-2">
                {!canApprove ? (
                    <div className="flex flex-col items-center justify-center h-full text-center bg-surface rounded-lg p-8">
                        <ShieldCheckIcon className="w-16 h-16 text-red-500" />
                        <h3 className="mt-4 text-xl font-bold text-white">Access Denied</h3>
                        <p className="mt-2 text-gray-400">You do not have the required permissions to approve requests. This view is only available to users with the 'Manager' role.</p>
                    </div>
                ) : requests.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center bg-surface rounded-lg p-8">
                        <ShieldCheckIcon className="w-16 h-16 text-green-500" />
                        <h3 className="mt-4 text-xl font-bold text-white">All Clear!</h3>
                        <p className="mt-2 text-gray-400">There are no pending approval requests.</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {requests.map(req => (
                            <ApprovalCard
                                key={req.id}
                                request={req}
                                onApprove={() => handleDecision(req.id, ApprovalStatus.APPROVED)}
                                onReject={() => handleDecision(req.id, ApprovalStatus.REJECTED)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};