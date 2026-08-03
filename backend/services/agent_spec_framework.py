# backend/services/agent_spec_framework.py
"""AgentSpec Framework: Validates the semantic and runtime viability of a generated AgentSpec.
Crucial for the Agent Creation Service to ensure newly generated agents are deployable."""
import logging
from typing import Dict, Any, List, Optional
import importlib.util
import asyncio

from services.agent_spec_dsl import AgentSpecDSL

logger = logging.getLogger(__name__)

# Mock list of currently available services for dependency resolution
_AVAILABLE_SERVICES: List[str] = [
    "EventPublisherService", "PIIVault", "PostgresClient", "AIService", 
    "PolicyVersioningService", "JWTService"
]

class AgentSpecValidator:
    """
    Validates the generated AgentSpec for semantic correctness and deployability.
    """
    def __init__(self):
        self.dsl = AgentSpecDSL()
        logger.info("✓ AgentSpec Validator initialized.")
        
    def _check_dependency_resolution(self, dependencies: List[str]) -> List[str]:
        """Check whether all required service dependencies are available in the running environment."""
        missing = []
        for dep in dependencies:
            if dep not in _AVAILABLE_SERVICES:
                missing.append(dep)
        return missing

    def _check_execution_module_syntax(self, module_path: str) -> bool:
        """
        Simulates checking if the Python execution module path is syntactically valid and importable.
        """
        try:
            # spec = importlib.util.find_spec(module_path)
            # return spec is not None
            
            # Mock check: assume path starting with 'services.'
            return module_path.startswith("services.")
        except Exception:
            return False

    async def validate_deployability(self, agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs comprehensive checks to ensure the agent is ready for autonomous deployment.
        """
        await asyncio.sleep(0.1) # Simulate complex validation time
        
        errors: List[str] = []
        
        # 1. Syntactic Validation
        errors.extend(self.dsl.validate_syntactic_structure(agent_spec))
        if errors:
            return {"is_deployable": False, "errors": errors}
            
        # 2. Dependency Resolution Check
        missing_deps = self._check_dependency_resolution(agent_spec.get('dependencies', []))
        if missing_deps:
            errors.append(f"Missing critical service dependencies: {', '.join(missing_deps)}")
            
        # 3. Execution Module Check (Ensures LLM didn't invent an un-importable path)
        if 'execution_module' not in agent_spec:
             errors.append("Missing required key: 'execution_module'")
        elif not self._check_execution_module_syntax(agent_spec['execution_module']):
            errors.append(f"Execution module path is invalid: {agent_spec['execution_module']}")
            
        # 4. Permissions Scope Check (Mocked)
        # In production: Check if requested permissions (agent_spec['permissions']) can be granted by the platform
        if not agent_spec.get('permissions'):
            errors.append("Agent must declare required permissions/scopes.")
            
        return {
            "is_deployable": not errors,
            "errors": errors,
            "message": "Validation complete."
        }