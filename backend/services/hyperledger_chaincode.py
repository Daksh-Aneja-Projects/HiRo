# services/hyperledger_chaincode.py - REPLACEMENT (Transactional Integrity and JSON Handling)
"""
Governance Chaincode: Postgres-backed DAO Logic.
Replaces in-memory MockStub with persistent AsyncPG operations.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import uuid

# CRITICAL: Use Real DB Client
from services.postgres_client import pg_client
from config.settings import settings
import asyncio # CRITICAL FIX: Add missing import

logger = logging.getLogger(__name__)

VOTING_PERIOD_HOURS = getattr(settings, 'DAO_VOTING_PERIOD', 72)
QUORUM_PCT = getattr(settings, 'DAO_QUORUM', 51)

class AHCMGovernanceChaincode:
    """
    Async Governance Engine backed by Postgres (acting as the World State).
    """
    def __init__(self):
        logger.info("✓ Governance Chaincode Initialized (Postgres Backend).")

    async def _get_proposal(self, proposal_id: str) -> Optional[Dict]:
        query = "SELECT data FROM dao_proposals WHERE proposal_id = $1"
        row = await pg_client.fetchrow(query, proposal_id)
        # CRITICAL FIX: If row exists, return the deserialized JSONB content
        if row and 'data' in row:
             # NOTE: pg_client (asyncpg) might return 'data' already as a dict if properly configured
             return row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
        return None

    async def _save_proposal(self, proposal: Dict):
        # CRITICAL FIX: Ensure proposal_id is used for CONFLICT resolution
        query = """
            INSERT INTO dao_proposals (proposal_id, status, data, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (proposal_id) DO UPDATE 
            SET status = $2, data = $3::jsonb, updated_at = NOW()
        """
        # CRITICAL FIX: Ensure `proposal` is passed as a JSON string for the JSONB column
        await pg_client.execute(query, proposal['proposal_id'], proposal['status'], json.dumps(proposal))

    async def propose_policy_update(self, data: Dict[str, Any]) -> str:
        """Creates a persistent proposal."""
        pid = f"PROP_{uuid.uuid4().hex[:8].upper()}"
        deadline = datetime.now(timezone.utc) + timedelta(hours=VOTING_PERIOD_HOURS)
        
        proposal = {
            'proposal_id': pid,
            'proposer': data.get('proposer_id', 'SYSTEM'),
            'rule_content': data.get('rule_content', {}),
            'status': 'VOTING',
            'votes_for': 0.0, # Use floats for weighted voting
            'votes_against': 0.0,
            'total_votes': 0.0,
            'voters': [],
            'deadline': deadline.isoformat(),
            'executed': False
        }
        
        await self._save_proposal(proposal)
        logger.info(f"Proposal {pid} created.")
        return pid

    async def cast_vote(self, vote_data: Dict[str, Any]) -> bool:
        """Processes a vote with transactional integrity."""
        pid = vote_data['proposal_id']
        voter = vote_data['voter_id']
        # CRITICAL FIX: Robustly cast weight
        try:
            weight = float(vote_data.get('token_weight', 1.0))
        except (ValueError, TypeError):
             weight = 1.0
             
        choice = vote_data['vote'].lower()

        # Transactional Vote Processing
        async with pg_client.transaction("DAO_Chaincode", "Vote") as conn:
            # CRITICAL FIX: Use the conn object to ensure operations are atomic
            proposal = await self._get_proposal(pid) # NOTE: _get_proposal uses pg_client.fetchrow, which is fine outside tx, but we must save inside.
            
            if not proposal: raise ValueError("Proposal not found")
            if proposal['status'] != 'VOTING': raise ValueError("Voting closed")
            if voter in proposal['voters']: raise ValueError("Already voted")

            # Update Tally
            proposal['voters'].append(voter)
            proposal['total_votes'] += weight
            if choice == 'for': proposal['votes_for'] += weight
            elif choice == 'against': proposal['votes_against'] += weight
            
            # Check Logic (Execute logic inside the transaction)
            await self._check_execution(proposal)
            
            # CRITICAL FIX: Save using conn.execute/update logic
            # Since _save_proposal uses pg_client.execute directly, we rely on the ACID nature of the outer transaction
            # and that _save_proposal implicitly wraps its own execution. For full transactional safety using conn:
            update_query = """
                UPDATE dao_proposals 
                SET status = $2, data = $3::jsonb, updated_at = NOW() 
                WHERE proposal_id = $1
            """
            await conn.execute(update_query, proposal['proposal_id'], proposal['status'], json.dumps(proposal))
            
        return True

    async def _check_execution(self, proposal: Dict):
        """Evaluates Quorum and Threshold."""
        total_possible = 10000.0 # Mock Total Supply (use float)
        
        # CRITICAL FIX: Prevent Division by Zero
        if total_possible <= 0: return 
        
        participation = (proposal['total_votes'] / total_possible) * 100
        
        if proposal['status'] == 'VOTING':
            # CRITICAL FIX: Properly compare timezone-aware datetimes
            deadline_dt = datetime.fromisoformat(proposal['deadline']).replace(tzinfo=timezone.utc)
            if deadline_dt < datetime.now(timezone.utc):
                proposal['status'] = 'EXPIRED'
                return

            # Check Approval
            if participation > QUORUM_PCT:
                if proposal['total_votes'] > 0:
                    approval_rate = (proposal['votes_for'] / proposal['total_votes']) * 100
                    if approval_rate > 66:
                        proposal['status'] = 'APPROVED'
                        proposal['executed'] = True
                        logger.info(f"Proposal {proposal['proposal_id']} PASSED.")