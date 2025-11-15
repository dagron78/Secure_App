import React, { useState, useRef } from 'react';
import { Document, Role, User } from '../types';
import { DocumentIcon, DatabaseIcon, CheckCircleIcon, ShieldCheckIcon, UploadIcon } from './icons';

interface DocumentViewProps {
    documents: Document[];
    onIndexDocument: (docId: string) => void;
    onUploadDocument: (file: File, metadata: { title?: string; classification: string; type: string }) => Promise<void>;
    currentUser: User;
}

const DocumentCard: React.FC<{ 
    doc: Document;
    onIndex: (docId: string) => void;
    canIndex: boolean;
}> = ({ doc, onIndex, canIndex }) => {
    
    const [isIndexing, setIsIndexing] = useState(false);
    const classificationColor = doc.classification === 'Confidential' ? 'text-red-400 bg-red-400/10' : 'text-blue-400 bg-blue-400/10';

    const handleIndex = () => {
        if (doc.indexed || !canIndex) return;
        setIsIndexing(true);
        // Simulate backend processing time
        setTimeout(() => {
            onIndex(doc.id);
            setIsIndexing(false);
        }, 1500);
    }

    return (
        <div className="bg-surface rounded-lg shadow-lg p-6 border border-gray-700 hover:border-primary transition-all duration-300 flex flex-col">
            <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-accent break-all">{doc.title}</h3>
                <div className={`text-xs font-semibold px-2 py-1 rounded-full ${classificationColor}`}>
                    {doc.classification}
                </div>
            </div>
            
            <p className="mt-2 text-sm text-gray-400"><strong>Type:</strong> {doc.type}</p>
            <p className="mt-2 text-sm text-gray-300 flex-grow min-h-[60px]">{doc.summary}</p>
            
            <div className="mt-4 border-t border-gray-600 pt-4 flex items-center justify-between">
                 <p className="text-xs text-gray-500">Doc ID: {doc.id}</p>
                 {canIndex && (
                     <button
                        onClick={handleIndex}
                        disabled={doc.indexed || isIndexing}
                        className={`flex items-center space-x-2 px-3 py-1.5 text-xs font-semibold rounded-md transition-colors disabled:cursor-not-allowed ${
                            doc.indexed
                                ? 'bg-green-500/10 text-green-400'
                                : isIndexing
                                ? 'bg-sky-500/10 text-sky-400 animate-pulse'
                                : 'bg-primary/20 text-accent hover:bg-primary/40'
                        }`}
                     >
                        {doc.indexed ? (
                            <CheckCircleIcon className="w-4 h-4" />
                        ) : (
                            <DatabaseIcon className="w-4 h-4" />
                        )}
                        <span>
                            {doc.indexed ? 'Indexed' : isIndexing ? 'Indexing...' : 'Index Document'}
                        </span>
                     </button>
                 )}
            </div>
        </div>
    );
}

export const DocumentView: React.FC<DocumentViewProps> = ({ documents, onIndexDocument, onUploadDocument, currentUser }) => {
  const canManageDocuments = currentUser.role === Role.MANAGER;
  const [isUploading, setIsUploading] = useState(false);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMetadata, setUploadMetadata] = useState({
    title: '',
    classification: 'Internal' as 'Confidential' | 'Internal' | 'Public',
    type: 'Policy' as 'Policy' | 'Guide' | 'Report'
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      setUploadMetadata(prev => ({
        ...prev,
        title: prev.title || file.name.replace(/\.[^/.]+$/, '')
      }));
      setShowUploadDialog(true);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    
    setIsUploading(true);
    try {
      await onUploadDocument(uploadFile, uploadMetadata);
      setShowUploadDialog(false);
      setUploadFile(null);
      setUploadMetadata({
        title: '',
        classification: 'Internal',
        type: 'Policy'
      });
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload document. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancelUpload = () => {
    setShowUploadDialog(false);
    setUploadFile(null);
    setUploadMetadata({
      title: '',
      classification: 'Internal',
      type: 'Policy'
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
    
  return (
    <div className="flex flex-col h-full bg-background p-6">
        <header className="mb-6 flex items-center space-x-3">
            <DocumentIcon className="w-8 h-8 text-primary"/>
            <div>
                <h2 className="text-2xl font-bold text-white">Document Knowledge Base</h2>
                <p className="text-md text-gray-400">Local documents available for the agent's RAG pipeline.</p>
            </div>
        </header>
        {!canManageDocuments && (
            <div className="bg-surface border border-yellow-500/30 text-yellow-300 text-sm p-4 rounded-lg mb-6 flex items-center space-x-3">
                <ShieldCheckIcon className="w-6 h-6 flex-shrink-0" />
                <p>As an Analyst, you can view documents. Only users with the 'Manager' role can index, add, or remove documents from the vector store.</p>
            </div>
        )}
        
        {canManageDocuments && (
            <div className="mb-6">
                <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileSelect}
                    accept=".pdf,.docx,.pptx,.html,.md,.txt,.png,.jpg,.jpeg"
                    className="hidden"
                    id="document-upload"
                />
                <label
                    htmlFor="document-upload"
                    className="inline-flex items-center space-x-2 px-4 py-2 bg-primary hover:bg-primary-dark text-white font-semibold rounded-lg cursor-pointer transition-colors"
                >
                    <UploadIcon className="w-5 h-5" />
                    <span>Upload Document</span>
                </label>
            </div>
        )}

        {showUploadDialog && uploadFile && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div className="bg-surface rounded-lg p-6 max-w-md w-full border border-gray-700">
                    <h3 className="text-xl font-bold text-white mb-4">Upload Document</h3>
                    
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">File</label>
                            <p className="text-sm text-gray-400 break-all">{uploadFile.name}</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Title</label>
                            <input
                                type="text"
                                value={uploadMetadata.title}
                                onChange={(e) => setUploadMetadata(prev => ({ ...prev, title: e.target.value }))}
                                className="w-full px-3 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
                                placeholder="Document title"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Classification</label>
                            <select
                                value={uploadMetadata.classification}
                                onChange={(e) => setUploadMetadata(prev => ({ ...prev, classification: e.target.value as any }))}
                                className="w-full px-3 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
                            >
                                <option value="Public">Public</option>
                                <option value="Internal">Internal</option>
                                <option value="Confidential">Confidential</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-1">Type</label>
                            <select
                                value={uploadMetadata.type}
                                onChange={(e) => setUploadMetadata(prev => ({ ...prev, type: e.target.value as any }))}
                                className="w-full px-3 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
                            >
                                <option value="Policy">Policy</option>
                                <option value="Guide">Guide</option>
                                <option value="Report">Report</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex space-x-3 mt-6">
                        <button
                            onClick={handleUpload}
                            disabled={isUploading || !uploadMetadata.title}
                            className="flex-1 bg-primary hover:bg-primary-dark text-white font-semibold py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isUploading ? 'Uploading...' : 'Upload'}
                        </button>
                        <button
                            onClick={handleCancelUpload}
                            disabled={isUploading}
                            className="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        )}
        
        <div className="flex-1 overflow-y-auto pr-2">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {documents.map(doc => (
                    <DocumentCard 
                        key={doc.id}
                        doc={doc}
                        onIndex={onIndexDocument}
                        canIndex={canManageDocuments}
                    />
                ))}
            </div>
        </div>
    </div>
  );
};