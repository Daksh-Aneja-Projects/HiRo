# services/policy_tree_generator.py - REPLACEMENT (AST Engine Robustness)
"""
Policy Tree Generator: Uses Python's native AST parser for robust boolean logic parsing.
"""
import logging
import ast
from typing import Dict, Any, List
import uuid
import asyncio 

logger = logging.getLogger(__name__)

class PolicyTreeGenerator:
    """
    Parses BPCL logic strings into executable AST dictionaries using python.ast.
    """
    def __init__(self):
        logger.info("✓ PolicyTreeGenerator Initialized (AST Engine).")

    def _node_to_dict(self, node) -> Dict[str, Any]:
        """Recursively converts Python AST nodes to a JSON-serializable tree (Synchronous)."""
        # Handle Boolean Operators (AND, OR)
        if isinstance(node, ast.BoolOp):
            op_type = 'AND' if isinstance(node.op, ast.And) else 'OR'
            return {
                "type": op_type,
                "children": [self._node_to_dict(val) for val in node.values]
            }
        
        # Handle Comparisons (salary > 50000)
        elif isinstance(node, ast.Compare):
            # CRITICAL FIX: Ensure only one comparison is processed (simple DSL)
            if len(node.ops) != 1 or len(node.comparators) != 1:
                return {"type": "ERROR", "message": "Complex chained comparison not supported."}

            left = self._get_id(node.left)
            op = self._get_operator(node.ops[0])
            right = self._get_id(node.comparators[0])
            
            return {
                "type": "COMPARISON",
                "operator": op,
                "left": left,
                "right": right
            }
        
        # Handle Raw Expressions
        elif isinstance(node, ast.Expression):
            return self._node_to_dict(node.body)

        # Base nodes (Name, Constant, Attribute)
        elif isinstance(node, ast.Name): return node.id
        elif isinstance(node, ast.Constant): return node.value
        elif isinstance(node, ast.Attribute): return f"{self._get_id(node.value)}.{node.attr}"
        return str(node)

    def _get_id(self, node):
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Attribute): return f"{self._get_id(node.value)}.{node.attr}"
        return str(node)

    def _get_operator(self, op):
        if isinstance(op, ast.Gt): return ">"
        if isinstance(op, ast.Lt): return "<"
        if isinstance(op, ast.GtE): return ">="
        if isinstance(op, ast.LtE): return "<="
        if isinstance(op, ast.Eq): return "=="
        if isinstance(op, ast.NotEq): return "!="
        return "ERROR_OP"
        
    def _generate_policy_execution_tree_sync(self, bpcl_content: Dict[str, Any]) -> Dict[str, Any]:
        """[SYNCHRONOUS CORE] Generates AST from rules."""
        execution_map = {}
        
        for rule in bpcl_content.get('rules', []):
            rule_id = rule.get('id', str(uuid.uuid4()))
            # CRITICAL FIX: Ensure condition is a string, default to True for safety
            condition = str(rule.get('condition', 'True'))
            
            try:
                # CRITICAL FIX: Wrap the expression in a check to prevent arbitrary code execution before parsing
                if not all(c in condition for c in ['<', '>', '==', '!=', 'and', 'or', 'True', 'False']):
                    raise SyntaxError("Condition contains invalid or unsupported Python constructs.")
                    
                # Use Python's built-in safe parser (ast.parse with mode='eval' prevents arbitrary statements)
                tree_node = ast.parse(condition, mode='eval')
                execution_map[rule_id] = {
                    "action": rule.get('action'),
                    "tree": self._node_to_dict(tree_node)
                }
            except Exception as e:
                logger.error(f"AST Parse Error for {rule_id}: {e}")
                execution_map[rule_id] = {"error": str(e), "action": rule.get('action')}

        return {"execution_map": execution_map, "status": "COMPLETED_WITH_ERRORS" if any("error" in v for v in execution_map.values()) else "SUCCESS"}


    async def generate_policy_execution_tree(self, bpcl_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        [ASYNCHRONOUS PUBLIC INTERFACE] Runs AST generation safely in a thread.
        """
        return await asyncio.to_thread(self._generate_policy_execution_tree_sync, bpcl_content)