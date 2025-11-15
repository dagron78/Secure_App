"""
Tool execution service with proper isolation and error handling.

⚠️ SECURITY WARNING - NOT PRODUCTION READY ⚠️

This implementation contains CRITICAL security vulnerabilities:

P0 VULNERABILITIES (Must fix before production):
1. Arbitrary Code Execution - Python scripts execute without sandboxing
2. Shell Injection - Command execution uses shell=True equivalent
3. SSRF Vulnerability - HTTP requests can access internal network

DO NOT DEPLOY TO PRODUCTION until these are resolved.
See SECURITY_REVIEW.md for full security assessment and hardening plan.

Required for Production:
- Docker/Firejail sandbox for Python/Shell execution
- Replace create_subprocess_shell with create_subprocess_exec
- Implement SSRF protection (IP blocklist + domain allowlist)
- Add Pydantic-based input validation
- Implement read-only SQL execution with dedicated user

Estimated hardening time: 5-7 days
"""
import asyncio
import subprocess
import json
import logging
from typing import Any, Dict, Optional
from enum import Enum
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool, ToolExecution, ExecutionStatus
from app.core.exceptions import ValidationError, ExternalServiceError

logger = logging.getLogger(__name__)

# Security warning for production deployments
logger.warning(
    "⚠️ SECURITY WARNING: Tool executor is NOT production-ready. "
    "Contains P0 vulnerabilities. See SECURITY_REVIEW.md for details."
)


class ToolType(str, Enum):
    """Tool type enumeration."""
    PYTHON_SCRIPT = "python_script"
    SHELL_COMMAND = "shell_command"
    API_CALL = "api_call"
    SQL_QUERY = "sql_query"
    HTTP_REQUEST = "http_request"


class ToolExecutor:
    """
    Execute tools with proper isolation and error handling.
    
    Supports multiple tool types with sandboxing, timeouts, and validation.
    """
    
    def __init__(self, timeout: int = 300, max_output_size: int = 1_000_000):
        """
        Initialize tool executor.
        
        Args:
            timeout: Maximum execution time in seconds (default: 5 minutes)
            max_output_size: Maximum output size in bytes (default: 1MB)
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self,
        tool: Tool,
        execution: ToolExecution,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool based on its type.
        
        Args:
            tool: Tool model instance
            execution: ToolExecution model instance
            input_data: Input parameters for the tool
            
        Returns:
            dict: Execution result with output data
            
        Raises:
            ValidationError: If tool type or input is invalid
            ExternalServiceError: If execution fails
        """
        logger.info(f"Executing tool {tool.id} ({tool.name}) of type {tool.tool_type}")
        
        try:
            # Validate input against tool schema
            self._validate_input(tool, input_data)
            
            # Route to appropriate executor
            if tool.tool_type == ToolType.PYTHON_SCRIPT:
                return await self._execute_python(tool, input_data)
            elif tool.tool_type == ToolType.SHELL_COMMAND:
                return await self._execute_shell(tool, input_data)
            elif tool.tool_type == ToolType.API_CALL:
                return await self._execute_api(tool, input_data)
            elif tool.tool_type == ToolType.SQL_QUERY:
                return await self._execute_sql(tool, input_data)
            elif tool.tool_type == ToolType.HTTP_REQUEST:
                return await self._execute_http(tool, input_data)
            else:
                raise ValidationError(
                    f"Unsupported tool type: {tool.tool_type}",
                    details={"tool_id": tool.id, "tool_type": tool.tool_type}
                )
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            raise
    
    def _validate_input(self, tool: Tool, input_data: Dict[str, Any]):
        """
        Validate input data against tool's input schema.
        
        Args:
            tool: Tool instance
            input_data: Input data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        if not tool.input_schema:
            return
        
        # Basic validation - check required fields
        schema = tool.input_schema
        required_fields = schema.get("required", [])
        
        missing_fields = [f for f in required_fields if f not in input_data]
        if missing_fields:
            raise ValidationError(
                f"Missing required input fields: {', '.join(missing_fields)}",
                details={"missing_fields": missing_fields}
            )
    
    async def _execute_python(self, tool: Tool, input_data: Dict) -> Dict:
        """
        Execute Python script in isolated environment.
        
        ⚠️ CRITICAL SECURITY VULNERABILITY ⚠️
        This method executes arbitrary Python code WITHOUT sandboxing.
        DO NOT USE IN PRODUCTION until sandboxing is implemented.
        
        Required Fix:
        - Execute in isolated Docker container (no network, minimal image)
        - Alternative: Firejail, gVisor, or Kata Containers
        - Set resource limits (CPU, memory, disk, timeout)
        
        Args:
            tool: Tool instance
            input_data: Input parameters
            
        Returns:
            dict: Execution result
        """
        logger.warning(
            f"⚠️ EXECUTING UNSANDBOXED PYTHON CODE for tool: {tool.name}. "
            "This is a CRITICAL security risk in production!"
        )
        
        script = tool.config.get("script", "")
        if not script:
            raise ValidationError("Python script is empty")
        
        try:
            # Create input JSON for the script
            input_json = json.dumps(input_data)
            
            # Execute script with timeout
            process = await asyncio.create_subprocess_exec(
                "python3", "-c", script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_json.encode()),
                timeout=self.timeout
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                raise ExternalServiceError("python", f"Script failed: {error_msg}")
            
            # Parse output
            output = stdout.decode('utf-8', errors='replace')
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"output": output}
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"Python script timed out after {self.timeout}s")
            raise ExternalServiceError("python", f"Execution timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"Python execution error: {e}")
            raise ExternalServiceError("python", str(e))
    
    async def _execute_shell(self, tool: Tool, input_data: Dict) -> Dict:
        """
        Execute shell command with proper sanitization.
        
        Args:
            tool: Tool instance
            input_data: Input parameters
            
        Returns:
            dict: Execution result
        """
        logger.info(f"Executing shell command: {tool.name}")
        
        command = tool.config.get("command", "")
        if not command:
            raise ValidationError("Shell command is empty")
        
        # Sanitize command - prevent command injection
        if any(char in command for char in [';', '|', '&', '>', '<', '`', '$']):
            raise ValidationError("Command contains unsafe characters")
        
        try:
            # Execute command with timeout
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"PATH": "/usr/bin:/bin"}  # Restricted PATH
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            
            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')
            
            return {
                "stdout": output,
                "stderr": error,
                "exit_code": process.returncode,
                "success": process.returncode == 0
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Shell command timed out after {self.timeout}s")
            raise ExternalServiceError("shell", f"Execution timeout after {self.timeout}s")
        except Exception as e:
            logger.error(f"Shell execution error: {e}")
            raise ExternalServiceError("shell", str(e))
    
    async def _execute_api(self, tool: Tool, input_data: Dict) -> Dict:
        """
        Make API call with retries and timeout.
        
        Args:
            tool: Tool instance
            input_data: Input parameters
            
        Returns:
            dict: API response
        """
        logger.info(f"Executing API call: {tool.name}")
        
        url = tool.config.get("url", "")
        method = tool.config.get("method", "GET").upper()
        headers = tool.config.get("headers", {})
        
        if not url:
            raise ValidationError("API URL is empty")
        
        try:
            # Make HTTP request with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await self.http_client.request(
                        method=method,
                        url=url,
                        json=input_data if method in ["POST", "PUT", "PATCH"] else None,
                        params=input_data if method == "GET" else None,
                        headers=headers
                    )
                    
                    return {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                        "success": 200 <= response.status_code < 300
                    }
                    
                except httpx.TimeoutException:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        except Exception as e:
            logger.error(f"API call error: {e}")
            raise ExternalServiceError("api", str(e))
    
    async def _execute_http(self, tool: Tool, input_data: Dict) -> Dict:
        """
        Execute HTTP request tool.
        
        Args:
            tool: Tool instance
            input_data: Input parameters including url, method, headers, body
            
        Returns:
            dict: HTTP response
        """
        url = input_data.get("url")
        method = input_data.get("method", "GET").upper()
        headers = input_data.get("headers", {})
        body = input_data.get("body")
        
        if not url:
            raise ValidationError("URL is required")
        
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None
            )
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "success": 200 <= response.status_code < 300
            }
        except Exception as e:
            logger.error(f"HTTP request error: {e}")
            raise ExternalServiceError("http", str(e))
    
    async def _execute_sql(self, tool: Tool, input_data: Dict) -> Dict:
        """
        Execute SQL query in read-only connection.
        
        Args:
            tool: Tool instance
            input_data: Input parameters
            
        Returns:
            dict: Query results
        """
        logger.info(f"Executing SQL query: {tool.name}")
        
        query = tool.config.get("query", "")
        if not query:
            raise ValidationError("SQL query is empty")
        
        # Security check - only allow SELECT statements
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise ValidationError("Only SELECT queries are allowed")
        
        # Check for dangerous keywords
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "GRANT", "REVOKE"]
        if any(keyword in query_upper for keyword in dangerous_keywords):
            raise ValidationError("Query contains unsafe SQL keywords")
        
        # TODO: Implement actual SQL execution with read-only connection
        # This requires database session management
        logger.warning("SQL execution not fully implemented - returning mock data")
        
        return {
            "query": query,
            "rows": [],
            "row_count": 0,
            "columns": [],
            "execution_time_ms": 0,
            "note": "SQL execution not fully implemented"
        }
    
    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.http_client.aclose()


# Global tool executor instance
tool_executor = ToolExecutor()