# services/document_scanner.py
"""
Document Scanner: Simulates IP Indexing from Enterprise Repositories.
"""
import logging
from typing import Dict, Any, List
import random 

logger = logging.getLogger(__name__)

REPOS = ["SharePoint", "G-Drive", "Confluence"]

class DocumentScanner:
    def __init__(self):
        logger.info("✓ DocumentScanner Initialized.")

    def scan_ip_by_employee(self, employee_id: str) -> List[Dict[str, Any]]: 
        """Deterministically simulates finding documents based on User ID hash."""
        seed = sum(ord(c) for c in employee_id)
        random.seed(seed)
        
        docs = []
        num_docs = random.randint(2, 5)
        
        types = ["Architecture_Spec", "Q3_Report", "Strategic_Plan", "Codebase_Walkthrough"]
        
        for i in range(num_docs):
            repo = random.choice(REPOS)
            dtype = random.choice(types)
            docs.append({
                "document_id": f"DOC_{seed}_{i}",
                "title": f"{dtype}_{i+1}_{employee_id}.pdf",
                "repository": repo,
                "classification": "INTERNAL"
            })
        return docs

    def map_to_ontology(self, documents: List[Dict]) -> Dict:
        """Maps found docs to graph nodes."""
        return {
            "entity_mapped": "Knowledge_Node",
            "relationship_summary": "IS_AUTHOR_OF",
            "documents_indexed": [d['title'] for d in documents],
            "graph_uids": [f"_:doc_{d['document_id']}" for d in documents]
        }