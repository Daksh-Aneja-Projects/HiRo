# backend/services/self_correcting_agent.py

import asyncio
import logging
import json
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timezone
from services.ai_services import AIService
from config.settings import settings
import random 

logger = logging.getLogger(__name__)

class SelfCorrectingAgent:
    """AI Agent capable of self-diagnosis and autonomous correction of BPCL (Business Process Compliance Language)."""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.iteration_count = 0
        self.max_iterations = getattr(settings, 'SELF_CORRECTING_MAX_ITERATIONS', 5) 
        
        logger.info(" ✓ Self-Correcting Agent Initialized")

    async def generate_and_fix_bpcl(self, nl_prompt: str) -> AsyncGenerator[str, None]:
        """
        Stream agent thought process while generating and self-correcting BPCL.
        """
        
        logger.info(f"Starting self-correcting BPCL generation for: {nl_prompt[:50]}...")
        
        # Initial thought
        yield json.dumps({
            "stage": "initialization",
            "message": " 🔄  Parsing natural language intent (Prompt-to-BPCL)...",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": 0
        })
        
        await asyncio.sleep(0.1)
        
        current_bpcl = ""
        try:
            # Generate initial BPCL
            initial_bpcl = await self._generate_initial_bpcl(nl_prompt)
            current_bpcl = initial_bpcl
            
            if "WORKFLOW: Emergency_Fallback" in current_bpcl:
                raise RuntimeError(f"Initial BPCL generation failed: {current_bpcl}")
            
            if "ERROR: " in current_bpcl:
                raise RuntimeError(f"Initial BPCL generation failed: {current_bpcl}")
            
            
            yield json.dumps({
                "stage": "generation",
                "message": " ✨  Generated initial BPCL structure",
                "content": current_bpcl[:200] + "..." if len(current_bpcl) > 200 else current_bpcl,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": 1
            })
            
            # Self-correction loop
            for i in range(self.max_iterations):
                self.iteration_count = i + 1
                
                yield json.dumps({
                    "stage": "correction_loop",
                    "message": f" 🔧  Self-correction iteration {i+1}/{self.max_iterations}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iteration": i + 1
                })
                
                # Analyze current BPCL for issues
                issues = await self._analyze_bpcl_issues(current_bpcl)
                
                if not issues:
                    yield json.dumps({
                        "stage": "completion",
                        "message": " ✅  BPCL passed all checks - Ready for deployment",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "iteration": i + 1
                    })
                    break
                
                yield json.dumps({
                    "stage": "analysis",
                    "message": f" ⚠️  Found {len(issues)} issues to fix (Compliance/Logic errors)",
                    "issues": issues[:3], 
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iteration": i + 1
                })
                
                # Apply corrections
                corrected_bpcl = await self._apply_corrections(current_bpcl, issues)
                
                if corrected_bpcl == current_bpcl or "ERROR: " in corrected_bpcl:
                    yield json.dumps({
                        "stage": "stagnation",
                        "message": " 🔄  No improvements made or error during correction - terminating",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "iteration": i + 1
                    })
                    break
                
                current_bpcl = corrected_bpcl
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.critical(f"Fatal error during BPCL self-correction: {type(e).__name__}: {e}")
            final_bpcl_content = current_bpcl if current_bpcl else "FAILED TO GENERATE"
            yield json.dumps({
                "stage": "critical_failure",
                "message": f" ❌  Critical failure: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": self.iteration_count
            })
            current_bpcl = final_bpcl_content
            
        # Final output
        yield json.dumps({
            "stage": "final",
            "message": f" 🎉  Self-correction process terminated after {self.iteration_count} iterations",
            "final_bpcl": current_bpcl, 
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": self.iteration_count
        })

        yield "COMPLETE"

    async def _generate_initial_bpcl(self, nl_prompt: str) -> str:
        """Generate initial BPCL from natural language prompt."""
        
        prompt = f"""Convert this HR process description into BPCL (Business Process Compliance Language):
Description: {nl_prompt}
Generate a structured BPCL with:
1. WORKFLOW: [Descriptive Name]
2. TRIGGER: [Event that starts the process]
3. ACTORS: [List of roles involved]
4. STEPS: [Sequential steps with conditions]
5. COMPLIANCE_RULES: [Policy compliance requirements]
6. ESCALATION: [Escalation paths]
Output only valid BPCL syntax and content, no preamble or explanation."""
        try:
            response = await self.ai_service.generate_text(
                prompt=prompt,
                task_type="bpcl_generation"
            )
            return response.strip()
            
        except Exception as e:
            logger.error(f"BPCL initial generation failed: {type(e).__name__}: {e}")
            return f"WORKFLOW: Emergency_Fallback\nERROR: {type(e).__name__}"

    async def _analyze_bpcl_issues(self, bpcl_content: str) -> list:
        """Analyze BPCL for syntax, logic, and compliance issues."""
        
        issues = []
        
        # Check for basic syntax issues (Deterministic checks first)
        if not bpcl_content.strip():
            issues.append({"type": "syntax", "severity": "critical", "message": "Empty BPCL content"})
            return issues
            
        # We rely on the AI and the VV Compiler for deep structural validation.
        if len(bpcl_content.split('\n')) < 5: 
            issues.append({"type": "structure", "severity": "medium", "message": "BPCL content seems too short/incomplete."})
            
        # Analyze with AI for deeper issues
        analysis_prompt = f"""Analyze this BPCL for issues:
{bpcl_content}
Return JSON with:
- issues: array of {{  "type": "syntax|logic|compliance|security",  "severity": "critical|high|medium|low",  "message": "description",  "line": "affected line if available"}}
Only return issues not already covered by deterministic checks (i.e., focus on logic, compliance, security, and flow errors)."""
        try:
            analysis = await self.ai_service.generate_json_response(
                prompt=analysis_prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "severity": {"type": "string"},
                                    "message": {"type": "string"},
                                    "line": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                task_type="analysis"
            )
            
            if analysis and "issues" in analysis:
                issues.extend(analysis["issues"])
        except Exception as e:
            logger.warning(f"AI analysis failed: {type(e).__name__}: {e}")
            
        return issues[:10]

    async def _apply_corrections(self, bpcl_content: str, issues: list) -> str:
        """Apply corrections to BPCL based on identified issues."""
        
        if not issues:
            return bpcl_content
            
        critical_and_high_issues = [i for i in issues if i.get("severity") in ["critical", "high"]]
        
        if critical_and_high_issues:
            correction_prompt = f"""Correct the following BPCL by resolving ONLY these issues:
Original BPCL:
{bpcl_content}
Issues to fix (Prioritize Critical/High):
{json.dumps(critical_and_high_issues[:5], indent=2)}
Provide the FULL corrected BPCL. Do not include any explanation or extra text."""
            try:
                corrected = await self.ai_service.generate_text(
                    prompt=correction_prompt,
                    task_type="correction"
                )
                return corrected.strip()
            except Exception as e:
                logger.error(f"Correction generation failed: {type(e).__name__}: {e}")
                return f"ERROR: Correction failed with {type(e).__name__}"
                
        return bpcl_content

    async def generate_bpcl_sync(self, nl_prompt: str) -> Dict[str, Any]:
        """
        [CRITICAL ORCHESTRATOR INTERFACE] Synchronous-compatible method for non-streaming contexts.
        Performs full generation and single-step correction to ensure deployable BPCL.
        """
        
        result = {
            "bpcl_content": "",
            "iterations": 0,
            "issues_found": 0,
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        } 
        
        try:
            # 1. Initial Generation
            bpcl = await self._generate_initial_bpcl(nl_prompt)
            current_bpcl = bpcl
            
            # 2. Analyze
            issues = await self._analyze_bpcl_issues(current_bpcl)
            
            result["iterations"] = 1
            result["issues_found"] = len(issues)
            
            # 3. Attempt Single Correction (if critical issues exist)
            if any(i.get("severity") in ["critical", "high"] for i in issues):
                corrected_bpcl = await self._apply_corrections(current_bpcl, issues)
                result["iterations"] = 2
                
                if "ERROR: " not in corrected_bpcl and corrected_bpcl != current_bpcl:
                    current_bpcl = corrected_bpcl
                    # Re-analyze after correction 
                    issues = await self._analyze_bpcl_issues(current_bpcl)
                
                
            result.update({
                "bpcl_content": current_bpcl,
                "issues_found": len(issues),
                "success": "ERROR:" not in current_bpcl and len(issues) == 0, 
                "issues": issues[:5] if issues else []
            })
        except Exception as e:
            logger.error(f"Sync BPCL generation failed: {type(e).__name__}: {e}")
            result["error"] = str(e)
            
        return result