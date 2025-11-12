import React from 'react';
import { AgentIcon, ChatIcon, ToolsIcon, UserCircleIcon, ShieldCheckIcon, DocumentIcon, ChartBarIcon, LockIcon, ChipIcon, BeakerIcon } from './icons';
import { AppView, User } from '../types';

interface SidebarProps {
  currentView: AppView;
  onViewChange: (view: AppView) => void;
  currentUser: User;
  onUserChange: () => void;
  pendingApprovalCount: number;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
}

const NavItem: React.FC<{
  icon: React.ReactNode;
  label: string;
  isActive: boolean;
  onClick: () => void;
  badgeCount?: number;
}> = ({ icon, label, isActive, onClick, badgeCount }) => (
  <button
    onClick={onClick}
    aria-label={`Navigate to ${label}`}
    className={`flex items-center justify-between w-full px-4 py-3 text-sm font-medium rounded-lg transition-colors duration-200 focus-visible:focus-visible-ring ${
      isActive
        ? 'bg-primary text-white'
        : 'text-gray-400 hover:bg-surface hover:text-white'
    }`}
  >
    <div className="flex items-center">
        {icon}
        <span className="ml-3">{label}</span>
    </div>
    {badgeCount > 0 && (
        <span className="bg-accent text-secondary text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
            {badgeCount}
        </span>
    )}
  </button>
);

const DemoModeToggle: React.FC<{ isDemoMode: boolean, onToggle: () => void }> = ({ isDemoMode, onToggle }) => (
    <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700/50">
        <div className="flex items-center space-x-2">
            <BeakerIcon className="w-5 h-5 text-purple-400" />
            <span className="text-sm font-medium text-white">Demo Mode</span>
        </div>
        <button
            onClick={onToggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:focus-visible-ring ${
                isDemoMode ? 'bg-primary' : 'bg-gray-600'
            }`}
        >
            <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isDemoMode ? 'translate-x-6' : 'translate-x-1'
                }`}
            />
        </button>
    </div>
);


export const Sidebar: React.FC<SidebarProps> = ({ currentView, onViewChange, currentUser, onUserChange, pendingApprovalCount, isDemoMode, onToggleDemoMode }) => {
  return (
    <aside className="w-64 flex-shrink-0 bg-secondary p-4 flex flex-col">
      <div className="flex items-center mb-8">
        <AgentIcon className="h-8 w-8 text-primary" />
        <h1 className="ml-2 text-xl font-bold text-white">CDSA</h1>
      </div>
      <nav className="flex flex-col space-y-2">
        <NavItem
          icon={<ChatIcon className="h-5 w-5" />}
          label="Agent Chat"
          isActive={currentView === AppView.CHAT}
          onClick={() => onViewChange(AppView.CHAT)}
        />
        <NavItem
          icon={<ToolsIcon className="h-5 w-5" />}
          label="Tool Registry"
          isActive={currentView === AppView.TOOLS}
          onClick={() => onViewChange(AppView.TOOLS)}
        />
        <NavItem
          icon={<ChipIcon className="h-5 w-5" />}
          label="LLM Gateway"
          isActive={currentView === AppView.LLM_GATEWAY}
          onClick={() => onViewChange(AppView.LLM_GATEWAY)}
        />
        <NavItem
          icon={<DocumentIcon className="h-5 w-5" />}
          label="Documents"
          isActive={currentView === AppView.DOCUMENTS}
          onClick={() => onViewChange(AppView.DOCUMENTS)}
        />
        <NavItem
          icon={<LockIcon className="h-5 w-5" />}
          label="Secure Vault"
          isActive={currentView === AppView.VAULT}
          onClick={() => onViewChange(AppView.VAULT)}
        />
         <NavItem
          icon={<ShieldCheckIcon className="h-5 w-5" />}
          label="Approvals"
          isActive={currentView === AppView.APPROVALS}
          onClick={() => onViewChange(AppView.APPROVALS)}
          badgeCount={pendingApprovalCount}
        />
        <NavItem
          icon={<ChartBarIcon className="h-5 w-5" />}
          label="Audit Log"
          isActive={currentView === AppView.AUDIT}
          onClick={() => onViewChange(AppView.AUDIT)}
        />
      </nav>

      <div className="mt-auto space-y-4">
        <div className="p-3 bg-surface rounded-lg">
            <h3 className="text-xs font-semibold text-gray-400 mb-2">SESSION CONTROL</h3>
            <div className="flex items-center space-x-2">
                <UserCircleIcon className="w-8 h-8 text-accent"/>
                <div>
                    <p className="text-sm font-medium text-white">{currentUser.name}</p>
                    <p className="text-xs text-gray-400">{currentUser.role}</p>
                </div>
            </div>
            <button 
                onClick={onUserChange}
                className="w-full mt-3 px-3 py-1.5 text-xs bg-primary/20 text-accent rounded hover:bg-primary/40 transition-colors focus-visible:focus-visible-ring">
                Switch User
            </button>
            <DemoModeToggle isDemoMode={isDemoMode} onToggle={onToggleDemoMode} />
        </div>

        <div className="text-xs text-gray-500">
          <p>&copy; 2024 Confidential Data Steward Agent</p>
          <p>v0.11.0 (Sprint 11)</p>
        </div>
      </div>
    </aside>
  );
};