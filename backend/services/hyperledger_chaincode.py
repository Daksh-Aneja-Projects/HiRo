# services/hyperledger_chaincode.py
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
import asyncio

logger = logging.getLogger(__name__)

VOTING_PERIOD_HOURS = getattr(settings, 'DAO_VOTING_PERIOD', 72)
QUORUM_PCT = getattr(settings, 'DAO_QUORUM', 51)

class AHCMGovernanceChaincode:
    """
    Async Governance Engine backed by Postgres (acting as the World State).
    """
    def __init__(self, mongo_client=None):
        # The user directory is the electorate. Quorum used to be measured
        # against a hardcoded "10000.0 # Mock Total Supply", so on a platform
        # with a handful of accounts participation could never exceed 0.1% and
        # no proposal could ever reach quorum, whatever anybody voted.
        self.mongo_client = mongo_client
        logger.info("✓ Governance Chaincode Initialized (Postgres Backend).")

    async def get_eligible_voters(self) -> Optional[int]:
        """How many accounts exist to vote. None when the directory is unreadable.

        Returning None rather than a number is deliberate: a quorum decision made
        against a guessed electorate is worse than no quorum decision at all.
        """
        if self.mongo_client is None:
            return None
        try:
            count = await self.mongo_client[settings.MONGO_DB_NAME]["users"].count_documents({})
            return int(count) if count > 0 else None
        except Exception as e:
            logger.warning(f"Could not count eligible voters: {e}")
            return None

    async def _get_proposal(self, proposal_id: str) -> Optional[Dict]:
        query = "SELECT data FROM dao_proposals WHERE proposal_id = $1"
        row = await pg_client.fetchrow(query, proposal_id)
        if row and 'data' in row:
             # NOTE: pg_client (asyncpg) might return 'data' already as a dict if properly configured
             return row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
        return None

    async def _save_proposal(self, proposal: Dict):
        query = """
            INSERT INTO dao_proposals (proposal_id, status, data, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (proposal_id) DO UPDATE 
            SET status = $2, data = $3::jsonb, updated_at = NOW()
        """
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
            'executed': False,
            # Filled in on the first vote, from the real user directory.
            'eligible_voters': await self.get_eligible_voters(),
            'participation_pct': 0.0,
            'quorum_note': f"No votes cast yet; {QUORUM_PCT}% participation is needed for quorum.",
        }
        
        await self._save_proposal(proposal)
        logger.info(f"Proposal {pid} created.")
        return pid

    async def cast_vote(self, vote_data: Dict[str, Any]) -> bool:
        """Processes a vote with transactional integrity."""
        pid = vote_data['proposal_id']
        voter = vote_data['voter_id']
        try:
            weight = float(vote_data.get('token_weight', 1.0))
        except (ValueError, TypeError):
             weight = 1.0
             
        choice = vote_data['vote'].lower()

        # Transactional Vote Processing
        async with pg_client.transaction("DAO_Chaincode", "Vote") as conn:
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
        """Evaluates Quorum and Threshold against the real eligible electorate."""
        if proposal['status'] != 'VOTING':
            return

        deadline_dt = datetime.fromisoformat(proposal['deadline']).replace(tzinfo=timezone.utc)
        if deadline_dt < datetime.now(timezone.utc):
            proposal['status'] = 'EXPIRED'
            return

        eligible_voters = await self.get_eligible_voters()
        proposal['eligible_voters'] = eligible_voters

        if not eligible_voters:
            # No honest electorate size, so no honest participation figure and no
            # quorum decision. The proposal stays open and says why.
            proposal['participation_pct'] = None
            proposal['quorum_note'] = ("The eligible voter count could not be read, "
                                       "so quorum cannot be evaluated yet.")
            return

        # Quorum is turnout: HEADS who voted over heads eligible to vote. It must
        # not use total_votes, which is the token-WEIGHTED sum -- dividing voting
        # power by a headcount produces a ratio of two different units that only
        # looks like a percentage (the seeded proposals, with weights in the
        # thousands, would read as 766000% turnout).
        # Vote weight belongs to the approval threshold below, and is used there.
        heads_voted = len(proposal.get('voters') or [])
        participation = (heads_voted / float(eligible_voters)) * 100
        proposal['participation_pct'] = round(participation, 2)
        proposal['quorum_note'] = (f"{heads_voted} of {eligible_voters} eligible voters have voted "
                                   f"({proposal['participation_pct']}%); {QUORUM_PCT}% is needed "
                                   f"for quorum.")

        if participation > QUORUM_PCT and proposal['total_votes'] > 0:
            approval_rate = (proposal['votes_for'] / proposal['total_votes']) * 100
            if approval_rate > 66:
                proposal['status'] = 'APPROVED'
                proposal['executed'] = True
                logger.info(f"Proposal {proposal['proposal_id']} PASSED "
                            f"({proposal['participation_pct']}% participation, "
                            f"{approval_rate:.1f}% in favour).")

    async def list_active_proposals(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Real active (VOTING) proposals from Postgres for the governance feed."""
        rows = await pg_client.fetch(
            "SELECT data FROM dao_proposals WHERE status = 'VOTING' ORDER BY updated_at DESC LIMIT $1",
            limit,
        )
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = r['data'] if isinstance(r['data'], dict) else json.loads(r['data'])
            out.append({
                'id': d.get('proposal_id'),
                'title': (d.get('rule_content') or {}).get('title') or d.get('proposal_id'),
                'proposer': d.get('proposer'),
                'votes_for': d.get('votes_for', 0.0),
                'votes_against': d.get('votes_against', 0.0),
                'deadline': d.get('deadline'),
                # Real electorate size and turnout; None when the directory
                # could not be read, never a stand-in number.
                'eligible_voters': d.get('eligible_voters'),
                'participation_pct': d.get('participation_pct'),
                'quorum_note': d.get('quorum_note'),
            })
        return out

    async def get_governance_stats(self, mongo_client=None) -> Dict[str, Any]:
        """DAO aggregates backing /dao/dashboard and the governance cards.

        Two of these figures did not measure what their labels said. members_voting
        summed the voter list of every proposal, so one person who voted on four
        proposals counted as four people, and the card read "256 people" on a
        platform with five accounts. ledger_commits_24h counted proposals touched
        in the last day and never went near the hash-chained ledger at all.
        """
        row = await pg_client.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE status = 'VOTING')       AS active_proposals,
              COALESCE(SUM((data->>'total_votes')::float), 0) AS total_voting_power,
              COALESCE((SELECT COUNT(DISTINCT voter)
                        FROM dao_proposals p,
                             LATERAL jsonb_array_elements_text(
                                 COALESCE(p.data->'voters', '[]'::jsonb)) AS voter), 0)
                                                             AS members_voting
            FROM dao_proposals
            """
        ) or {}

        # The ledger is the Mongo policy_ledger collection, so count it there.
        mongo_client = mongo_client if mongo_client is not None else self.mongo_client
        ledger_blocks_24h = 0
        if mongo_client is not None:
            try:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                ledger_blocks_24h = await mongo_client[settings.MONGO_DB_NAME]["policy_ledger"]                     .count_documents({"timestamp": {"$gte": cutoff}})
            except Exception as e:
                logger.warning(f"Could not count ledger blocks: {e}")

        return {
            'active_proposals': int(row.get('active_proposals') or 0),
            'total_voting_power': float(row.get('total_voting_power') or 0.0),
            'members_voting': int(row.get('members_voting') or 0),
            'ledger_commits_24h': int(ledger_blocks_24h),
            # The electorate quorum is measured against. None when unreadable.
            'eligible_voters': await self.get_eligible_voters(),
        }