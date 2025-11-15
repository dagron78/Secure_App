INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Generating static SQL
INFO  [alembic.runtime.migration] Will assume transactional DDL.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INFO  [alembic.runtime.migration] Running upgrade  -> 001, initial schema
-- Running upgrade  -> 001

CREATE TABLE roles (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description VARCHAR(500), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE INDEX ix_roles_id ON roles (id);

CREATE TABLE permissions (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    description VARCHAR(500), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE INDEX ix_permissions_id ON permissions (id);

CREATE TABLE users (
    id SERIAL NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    username VARCHAR(100) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    full_name VARCHAR(255), 
    is_active BOOLEAN NOT NULL, 
    is_superuser BOOLEAN NOT NULL, 
    is_verified BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_login TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_id ON users (id);

CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL, 
    role_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, role_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL, 
    permission_id INTEGER NOT NULL, 
    PRIMARY KEY (role_id, permission_id), 
    FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE TABLE sessions (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    token VARCHAR(500) NOT NULL, 
    refresh_token VARCHAR(500), 
    ip_address VARCHAR(50), 
    user_agent VARCHAR(500), 
    is_active BOOLEAN NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_activity TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_sessions_id ON sessions (id);

CREATE UNIQUE INDEX ix_sessions_token ON sessions (token);

CREATE INDEX ix_sessions_user_active ON sessions (user_id, is_active);

CREATE TABLE chat_sessions (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    title VARCHAR(500) NOT NULL, 
    model VARCHAR(100), 
    temperature VARCHAR(10) NOT NULL, 
    context_window_size INTEGER NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_message_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_sessions_id ON chat_sessions (id);

CREATE INDEX ix_chat_sessions_user_active ON chat_sessions (user_id, is_active);

CREATE TABLE chat_messages (
    id SERIAL NOT NULL, 
    session_id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    tokens INTEGER, 
    model VARCHAR(100), 
    meta_data JSON, 
    tool_execution_id INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_messages_id ON chat_messages (id);

CREATE INDEX ix_chat_messages_session ON chat_messages (session_id, created_at);

CREATE TABLE context_windows (
    id SERIAL NOT NULL, 
    session_id INTEGER NOT NULL, 
    max_tokens INTEGER NOT NULL, 
    current_tokens INTEGER NOT NULL, 
    message_count INTEGER NOT NULL, 
    strategy VARCHAR(50) NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_context_windows_id ON context_windows (id);

CREATE UNIQUE INDEX ix_context_windows_session_id ON context_windows (session_id);

CREATE TABLE tools (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    display_name VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    category VARCHAR(50) NOT NULL, 
    version VARCHAR(20) NOT NULL, 
    python_function VARCHAR(200) NOT NULL, 
    parameters_schema JSON NOT NULL, 
    return_schema JSON, 
    status VARCHAR(20) NOT NULL, 
    requires_approval BOOLEAN NOT NULL, 
    required_permission VARCHAR(100), 
    timeout_seconds INTEGER NOT NULL, 
    max_retries INTEGER NOT NULL, 
    execution_count INTEGER NOT NULL, 
    success_count INTEGER NOT NULL, 
    failure_count INTEGER NOT NULL, 
    avg_execution_time FLOAT, 
    last_executed_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_tools_id ON tools (id);

CREATE UNIQUE INDEX ix_tools_name ON tools (name);

CREATE INDEX ix_tools_category_status ON tools (category, status);

CREATE TABLE tool_executions (
    id SERIAL NOT NULL, 
    tool_id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    session_id INTEGER, 
    status VARCHAR(20) NOT NULL, 
    input_data JSON NOT NULL, 
    output_data JSON, 
    error_message TEXT, 
    started_at TIMESTAMP WITHOUT TIME ZONE, 
    completed_at TIMESTAMP WITHOUT TIME ZONE, 
    execution_time FLOAT, 
    retry_count INTEGER NOT NULL, 
    requires_approval BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE SET NULL, 
    FOREIGN KEY(tool_id) REFERENCES tools (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_tool_executions_id ON tool_executions (id);

CREATE INDEX ix_tool_executions_tool_status ON tool_executions (tool_id, status);

CREATE INDEX ix_tool_executions_user_created ON tool_executions (user_id, created_at);

CREATE TABLE tool_approvals (
    id SERIAL NOT NULL, 
    execution_id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    reason TEXT, 
    notes TEXT, 
    requested_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    responded_at TIMESTAMP WITHOUT TIME ZONE, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(execution_id) REFERENCES tool_executions (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_tool_approvals_id ON tool_approvals (id);

CREATE INDEX ix_tool_approvals_status_requested ON tool_approvals (status, requested_at);

CREATE INDEX ix_tool_approvals_user_status ON tool_approvals (user_id, status);

CREATE TABLE tool_cache (
    id SERIAL NOT NULL, 
    tool_id INTEGER NOT NULL, 
    input_hash VARCHAR(64) NOT NULL, 
    input_data JSON NOT NULL, 
    output_data JSON NOT NULL, 
    execution_time FLOAT NOT NULL, 
    hit_count INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_accessed TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tool_id) REFERENCES tools (id) ON DELETE CASCADE
);

CREATE INDEX ix_tool_cache_id ON tool_cache (id);

CREATE UNIQUE INDEX ix_tool_cache_tool_hash ON tool_cache (tool_id, input_hash);

CREATE TABLE documents (
    id SERIAL NOT NULL, 
    title VARCHAR(500) NOT NULL, 
    source VARCHAR(1000) NOT NULL, 
    source_type VARCHAR(50) NOT NULL, 
    file_type VARCHAR(50), 
    file_size INTEGER, 
    tags VARCHAR[], 
    meta_data JSON, 
    is_processed BOOLEAN NOT NULL, 
    is_indexed BOOLEAN NOT NULL, 
    processing_error TEXT, 
    uploaded_by INTEGER, 
    is_public BOOLEAN NOT NULL, 
    required_permission VARCHAR(100), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    last_accessed TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_documents_id ON documents (id);

CREATE INDEX ix_documents_indexed_public ON documents (is_indexed, is_public);

CREATE INDEX ix_documents_source_type ON documents (source_type, created_at);

CREATE TABLE embedding_models (
    id SERIAL NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    display_name VARCHAR(200) NOT NULL, 
    provider VARCHAR(50) NOT NULL, 
    model_id VARCHAR(200) NOT NULL, 
    dimension INTEGER NOT NULL, 
    max_tokens INTEGER NOT NULL, 
    cost_per_1k_tokens FLOAT, 
    is_active BOOLEAN NOT NULL, 
    is_default BOOLEAN NOT NULL, 
    avg_latency_ms FLOAT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_embedding_models_id ON embedding_models (id);

CREATE UNIQUE INDEX ix_embedding_models_name ON embedding_models (name);

CREATE TABLE document_chunks (
    id SERIAL NOT NULL, 
    document_id INTEGER NOT NULL, 
    chunk_index INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    embedding FLOAT[], 
    embedding_model_id INTEGER, 
    token_count INTEGER, 
    char_count INTEGER, 
    meta_data JSON, 
    search_keywords VARCHAR[], 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(embedding_model_id) REFERENCES embedding_models (id) ON DELETE SET NULL
);

CREATE INDEX ix_document_chunks_id ON document_chunks (id);

CREATE UNIQUE INDEX ix_document_chunks_doc_index ON document_chunks (document_id, chunk_index);

CREATE TABLE search_results (
    id SERIAL NOT NULL, 
    chunk_id INTEGER NOT NULL, 
    query TEXT NOT NULL, 
    similarity_score FLOAT NOT NULL, 
    search_type VARCHAR(50) NOT NULL, 
    user_id INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_search_results_id ON search_results (id);

CREATE INDEX ix_search_results_user_created ON search_results (user_id, created_at);

CREATE TABLE secrets (
    id SERIAL NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT, 
    secret_type VARCHAR(50) NOT NULL, 
    encrypted_value TEXT NOT NULL, 
    encryption_key_id VARCHAR(100) NOT NULL, 
    version INTEGER NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_by INTEGER NOT NULL, 
    tags VARCHAR[], 
    meta_data JSON, 
    rotation_enabled BOOLEAN NOT NULL, 
    rotation_interval_days INTEGER, 
    last_rotated_at TIMESTAMP WITHOUT TIME ZONE, 
    next_rotation_at TIMESTAMP WITHOUT TIME ZONE, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_secrets_id ON secrets (id);

CREATE UNIQUE INDEX ix_secrets_name ON secrets (name);

CREATE INDEX ix_secrets_active_type ON secrets (is_active, secret_type);

CREATE TABLE secret_versions (
    id SERIAL NOT NULL, 
    secret_id INTEGER NOT NULL, 
    version INTEGER NOT NULL, 
    encrypted_value TEXT NOT NULL, 
    encryption_key_id VARCHAR(100) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_by INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(secret_id) REFERENCES secrets (id) ON DELETE CASCADE
);

CREATE INDEX ix_secret_versions_id ON secret_versions (id);

CREATE UNIQUE INDEX ix_secret_versions_secret_version ON secret_versions (secret_id, version);

CREATE TABLE secret_access_logs (
    id SERIAL NOT NULL, 
    secret_id INTEGER NOT NULL, 
    user_id INTEGER NOT NULL, 
    access_type VARCHAR(50) NOT NULL, 
    ip_address VARCHAR(50), 
    user_agent VARCHAR(500), 
    accessed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(secret_id) REFERENCES secrets (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_secret_access_logs_id ON secret_access_logs (id);

CREATE INDEX ix_secret_access_logs_secret_accessed ON secret_access_logs (secret_id, accessed_at);

CREATE INDEX ix_secret_access_logs_user_accessed ON secret_access_logs (user_id, accessed_at);

CREATE TABLE audit_logs (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    action VARCHAR(100) NOT NULL, 
    resource_type VARCHAR(100) NOT NULL, 
    resource_id INTEGER, 
    details JSON, 
    ip_address VARCHAR(50), 
    user_agent VARCHAR(500), 
    session_id INTEGER, 
    tool_execution_id INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE SET NULL, 
    FOREIGN KEY(tool_execution_id) REFERENCES tool_executions (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_logs_id ON audit_logs (id);

CREATE INDEX ix_audit_logs_action_created ON audit_logs (action, created_at);

CREATE INDEX ix_audit_logs_resource ON audit_logs (resource_type, resource_id);

CREATE INDEX ix_audit_logs_user_created ON audit_logs (user_id, created_at);

CREATE TABLE system_metrics (
    id SERIAL NOT NULL, 
    metric_name VARCHAR(100) NOT NULL, 
    metric_value FLOAT NOT NULL, 
    metric_type VARCHAR(50) NOT NULL, 
    tags JSON, 
    recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_system_metrics_id ON system_metrics (id);

CREATE INDEX ix_system_metrics_name_recorded ON system_metrics (metric_name, recorded_at);

CREATE TABLE notifications (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    type VARCHAR(100) NOT NULL, 
    title VARCHAR(500) NOT NULL, 
    message TEXT NOT NULL, 
    data JSON, 
    priority VARCHAR(20) NOT NULL, 
    is_read BOOLEAN NOT NULL, 
    read_at TIMESTAMP WITHOUT TIME ZONE, 
    expires_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_id ON notifications (id);

CREATE INDEX idx_notifications_priority ON notifications (priority, created_at);

CREATE INDEX idx_notifications_type ON notifications (type);

CREATE INDEX idx_notifications_unread ON notifications (user_id, is_read, created_at);

CREATE INDEX idx_notifications_user ON notifications (user_id);

CREATE TABLE notification_preferences (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    notification_type VARCHAR(100) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    delivery_method VARCHAR(50) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notification_preferences_id ON notification_preferences (id);

CREATE UNIQUE INDEX idx_notification_prefs_user_type ON notification_preferences (user_id, notification_type);

INSERT INTO alembic_version (version_num) VALUES ('001') RETURNING alembic_version.version_num;

COMMIT;

