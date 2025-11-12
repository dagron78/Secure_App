import React, { useState, useCallback } from 'react';
import { Secret, User, Role, AuditEvent, AuditEventType } from '../types';
import { EyeIcon, EyeSlashIcon, LockIcon, PencilSquareIcon, PlusIcon, ShieldCheckIcon, TrashIcon } from './icons';

interface SecureVaultViewProps {
    currentUser: User;
    secrets: Secret[];
    onAddSecret: (secret: Omit<Secret, 'id'>) => void;
    onUpdateSecret: (secret: Secret) => void;
    onDeleteSecret: (secretId: string) => void;
    onNewAuditEvent: (event: AuditEvent) => void;
}

const SecretModal: React.FC<{
    isOpen: boolean;
    onClose: () => void;
    onSave: (secret: Omit<Secret, 'id'> | Secret) => void;
    secretToEdit: Secret | null;
}> = ({ isOpen, onClose, onSave, secretToEdit }) => {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [value, setValue] = useState('');

    React.useEffect(() => {
        if (secretToEdit) {
            setName(secretToEdit.name);
            setDescription(secretToEdit.description);
            setValue(secretToEdit.value);
        } else {
            setName('');
            setDescription('');
            setValue('');
        }
    }, [secretToEdit, isOpen]);
    
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const secretData = { name, description, value };
        if(secretToEdit) {
            onSave({ ...secretData, id: secretToEdit.id });
        } else {
            onSave(secretData);
        }
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-secondary rounded-lg border border-gray-700 shadow-xl max-w-lg w-full">
                <form onSubmit={handleSubmit}>
                    <header className="p-4 border-b border-gray-700">
                        <h3 className="text-lg font-bold text-white">{secretToEdit ? 'Edit Secret' : 'Add New Secret'}</h3>
                    </header>
                    <div className="p-6 space-y-4">
                        <div>
                            <label htmlFor="secret-name" className="block text-sm font-medium text-gray-300 mb-1">Name</label>
                            <input id="secret-name" type="text" value={name} onChange={e => setName(e.target.value)} required className="w-full bg-surface px-3 py-2 rounded-lg border border-gray-600 focus:outline-none focus-visible:focus-visible-ring text-white" />
                        </div>
                        <div>
                            <label htmlFor="secret-desc" className="block text-sm font-medium text-gray-300 mb-1">Description</label>
                            <textarea id="secret-desc" value={description} onChange={e => setDescription(e.target.value)} required rows={3} className="w-full bg-surface px-3 py-2 rounded-lg border border-gray-600 focus:outline-none focus-visible:focus-visible-ring text-white" />
                        </div>
                        <div>
                            <label htmlFor="secret-value" className="block text-sm font-medium text-gray-300 mb-1">Value</label>
                            <input id="secret-value" type="password" value={value} onChange={e => setValue(e.target.value)} required className="w-full bg-surface px-3 py-2 rounded-lg border border-gray-600 focus:outline-none focus-visible:focus-visible-ring text-white" />
                        </div>
                    </div>
                    <footer className="p-4 border-t border-gray-700 flex justify-end space-x-3">
                        <button type="button" onClick={onClose} className="bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-medium">Cancel</button>
                        <button type="submit" className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium">{secretToEdit ? 'Save Changes' : 'Add Secret'}</button>
                    </footer>
                </form>
            </div>
        </div>
    );
};

const SecretCard: React.FC<{
    secret: Secret;
    onEdit: () => void;
    onDelete: () => void;
    onView: () => void;
}> = ({ secret, onEdit, onDelete, onView }) => {
    const [isRevealed, setIsRevealed] = useState(false);

    const handleReveal = () => {
        setIsRevealed(!isRevealed);
        if (!isRevealed) {
            onView(); // Log the view event only when revealing
        }
    };

    return (
        <div className="bg-surface rounded-lg p-4 border border-gray-700 flex flex-col space-y-3">
            <div className="flex justify-between items-start">
                <h3 className="font-bold text-accent break-all">{secret.name}</h3>
                <div className="flex space-x-2">
                    <button onClick={onEdit} className="text-gray-400 hover:text-white"><PencilSquareIcon className="w-5 h-5"/></button>
                    <button onClick={onDelete} className="text-gray-400 hover:text-red-400"><TrashIcon className="w-5 h-5"/></button>
                </div>
            </div>
            <p className="text-sm text-gray-300 flex-grow min-h-[40px]">{secret.description}</p>
            <div>
                <p className="text-xs text-gray-400 mb-1">Value</p>
                <div className="flex items-center space-x-2 bg-background p-2 rounded-md">
                    <input 
                        type={isRevealed ? 'text' : 'password'}
                        value={secret.value}
                        readOnly
                        className="flex-1 bg-transparent text-sm text-gray-400 font-mono focus:outline-none"
                    />
                    <button onClick={handleReveal} className="text-gray-400 hover:text-white">
                        {isRevealed ? <EyeSlashIcon className="w-5 h-5"/> : <EyeIcon className="w-5 h-5"/>}
                    </button>
                </div>
            </div>
        </div>
    );
};

export const SecureVaultView: React.FC<SecureVaultViewProps> = ({ currentUser, secrets, onAddSecret, onUpdateSecret, onDeleteSecret, onNewAuditEvent }) => {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [secretToEdit, setSecretToEdit] = useState<Secret | null>(null);

    const canManage = currentUser.role === Role.MANAGER;
    
    const handleOpenModal = (secret: Secret | null) => {
        setSecretToEdit(secret);
        setIsModalOpen(true);
    };
    
    const handleCloseModal = () => {
        setSecretToEdit(null);
        setIsModalOpen(false);
    };

    const handleSaveSecret = (secretData: Omit<Secret, 'id'> | Secret) => {
        if ('id' in secretData) {
            onUpdateSecret(secretData);
        } else {
            onAddSecret(secretData);
        }
    };
    
    const handleDelete = (secret: Secret) => {
        if(window.confirm(`Are you sure you want to delete the secret "${secret.name}"? This action cannot be undone.`)) {
            onDeleteSecret(secret.id);
        }
    };

    const handleViewSecret = useCallback((secretName: string) => {
        onNewAuditEvent({
            id: crypto.randomUUID(),
            type: AuditEventType.VAULT_SECRET_VIEWED,
            timestamp: new Date().toISOString(),
            user: currentUser,
            details: { secretName },
        })
    }, [onNewAuditEvent, currentUser]);

    if (!canManage) {
        return (
            <div className="flex flex-col h-full bg-background p-6 items-center justify-center">
                <div className="text-center bg-surface rounded-lg p-8 max-w-md">
                    <ShieldCheckIcon className="w-16 h-16 text-red-500 mx-auto" />
                    <h3 className="mt-4 text-xl font-bold text-white">Access Denied</h3>
                    <p className="mt-2 text-gray-400">You do not have the required permissions to manage the Secure Vault. This feature is only available to users with the 'Manager' role.</p>
                </div>
            </div>
        );
    }
    
    return (
        <div className="flex flex-col h-full bg-background p-6">
            <SecretModal isOpen={isModalOpen} onClose={handleCloseModal} onSave={handleSaveSecret} secretToEdit={secretToEdit} />
            <header className="mb-6 flex justify-between items-center">
                <div className="flex items-center space-x-3">
                    <LockIcon className="w-8 h-8 text-primary"/>
                    <div>
                        <h2 className="text-2xl font-bold text-white">Secure Vault</h2>
                        <p className="text-md text-gray-400">Manage sensitive configurations and secrets.</p>
                    </div>
                </div>
                <button
                    onClick={() => handleOpenModal(null)}
                    className="flex items-center space-x-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-500">
                    <PlusIcon className="w-5 h-5"/>
                    <span>Add New Secret</span>
                </button>
            </header>
            <div className="flex-1 overflow-y-auto pr-2">
                {secrets.length === 0 ? (
                    <div className="text-center py-16 text-gray-500">
                        <p>The Secure Vault is empty.</p>
                        <p className="text-sm mt-2">Click "Add New Secret" to get started.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {secrets.map(secret => (
                            <SecretCard
                                key={secret.id}
                                secret={secret}
                                onEdit={() => handleOpenModal(secret)}
                                onDelete={() => handleDelete(secret)}
                                onView={() => handleViewSecret(secret.name)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};