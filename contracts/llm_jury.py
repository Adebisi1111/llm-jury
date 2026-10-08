# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""LLM-Jury — decentralized arbitration via AI validators."""

import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass

from genlayer import *


# ---------------------------------------------------------------------------
# Module-level helpers (GenVM doesn't support @staticmethod or local imports)
# ---------------------------------------------------------------------------

def _arbitrate(contract_terms: str, claimant_evidence: str, respondent_evidence: str) -> dict:
    """Run AI arbitration: compare contract terms against both evidence sets."""
    prompt = (
        "You are an impartial AI arbitrator. Review the contract terms and evidence from both parties.\n\n"
        f"CONTRACT TERMS:\n{contract_terms}\n\n"
        f"CLAIMANT EVIDENCE:\n{claimant_evidence}\n\n"
        f"RESPONDENT EVIDENCE:\n{respondent_evidence}\n\n"
        "Determine which party the contract terms favor based on the evidence provided.\n\n"
        "Respond with ONLY a valid JSON object in this exact format:\n"
        '{"verdict": "CLAIMANT_FAVORED" | "RESPONDENT_FAVORED" | "DISMISSED", "justification": "brief legal reasoning"}\n\n'
        "Rules:\n"
        "- CLAIMANT_FAVORED: Contract terms and evidence support the claimant's position\n"
        "- RESPONDENT_FAVORED: Contract terms and evidence support the respondent's position\n"
        "- DISMISSED: Case lacks merit, evidence is insufficient, or contract terms are unclear\n"
        "- Default to DISMISSED if evidence is ambiguous\n"
        "- Do NOT include any text outside the JSON object"
    )
    raw_response = gl.nondet.exec_prompt(prompt).strip()
    parsed = _parse_verdict_json(raw_response)
    return {
        "verdict": parsed.get("verdict", "DISMISSED"),
        "justification": parsed.get("justification", ""),
    }


def _parse_verdict_json(raw: str) -> dict:
    """Parse LLM verdict JSON output with defensive cleanup."""
    raw = re.sub(r'```json\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'```\s*', '', raw)
    match = re.search(r'\{.*\}', raw, flags=re.DOTALL)
    if match:
        raw = match.group()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            verdict = data.get("verdict", "DISMISSED")
            justification = data.get("justification", "")
            if verdict not in ("CLAIMANT_FAVORED", "RESPONDENT_FAVORED", "DISMISSED"):
                verdict = "DISMISSED"
            return {"verdict": verdict, "justification": justification}
    except (json.JSONDecodeError, KeyError):
        pass
    raw_upper = raw.upper()
    for v in ("CLAIMANT_FAVORED", "RESPONDENT_FAVORED", "DISMISSED"):
        if v in raw_upper:
            return {"verdict": v, "justification": raw[:500]}
    return {"verdict": "DISMISSED", "justification": "Could not parse LLM output"}


# ---------------------------------------------------------------------------
# Storage model
# ---------------------------------------------------------------------------


@allow_storage
@dataclass
class Dispute:
    """A text contract dispute pending or resolved."""

    dispute_id: str
    contract_terms: str
    claimant_evidence: str
    respondent_evidence: str
    status: str  # PENDING or RESOLVED
    verdict: str  # CLAIMANT_FAVORED, RESPONDENT_FAVORED, or DISMISSED
    justification: str
    created_at: u256
    resolved_at: u256


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


class LLMJury(gl.Contract):
    """Decentralized arbitration platform with AI-powered jury consensus."""

    disputes: TreeMap[str, Dispute]
    next_id: u256

    def __init__(self):
        self.next_id = u256(0)

    # ------------------------------------------------------------------
    # Dispute lifecycle
    # ------------------------------------------------------------------

    @gl.public.write
    def create_dispute(self, contract_terms: str, claimant_evidence: str) -> str:
        """Create a new dispute. Returns the dispute_id."""
        if not contract_terms.strip():
            raise gl.vm.UserError("Contract terms cannot be empty")
        if not claimant_evidence.strip():
            raise gl.vm.UserError("Claimant evidence cannot be empty")

        self.next_id += u256(1)
        dispute_id = f"dispute-{int(self.next_id)}"
        sender = str(gl.message.sender_address)

        self.disputes[dispute_id] = Dispute(
            dispute_id=dispute_id,
            contract_terms=contract_terms,
            claimant_evidence=claimant_evidence,
            respondent_evidence="",
            status="PENDING",
            verdict="",
            justification="",
            created_at=self._now(),
            resolved_at=u256(0),
        )
        return dispute_id

    @gl.public.write
    def submit_defense(self, dispute_id: str, respondent_evidence: str) -> None:
        """Submit respondent evidence for an existing dispute."""
        if not respondent_evidence.strip():
            raise gl.vm.UserError("Respondent evidence cannot be empty")

        dispute = self.disputes.get(dispute_id, None)
        if dispute is None:
            raise gl.vm.UserError("Dispute not found")
        if dispute.status != "PENDING":
            raise gl.vm.UserError("Dispute already resolved")
        if dispute.respondent_evidence:
            raise gl.vm.UserError("Defense already submitted")

        dispute.respondent_evidence = respondent_evidence
        self.disputes[dispute_id] = dispute

    @gl.public.write
    def run_arbitration(self, dispute_id: str) -> str:
        """Trigger AI jury consensus on a dispute."""
        dispute = self.disputes.get(dispute_id, None)
        if dispute is None:
            raise gl.vm.UserError("Dispute not found")
        if dispute.status != "PENDING":
            raise gl.vm.UserError("Dispute already resolved")
        if not dispute.respondent_evidence:
            raise gl.vm.UserError("Respondent defense not yet submitted")

        # ---- nondeterministic round --------------------------------------
        # Extract values BEFORE nondet to avoid capturing self (storage) in closures
        terms = dispute.contract_terms
        claimant = dispute.claimant_evidence
        respondent = dispute.respondent_evidence

        def leader_fn() -> dict:
            return _arbitrate(terms, claimant, respondent)

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            mine = _arbitrate(terms, claimant, respondent)
            return mine.get("verdict") == leader_res.calldata.get("verdict")

        result = gl.vm.run_nondet(leader_fn, validator_fn)

        # run_nondet returns a gl.vm.Return wrapper; access .calldata for the actual dict
        result_data = result.calldata if hasattr(result, "calldata") else result
        verdict = result_data.get("verdict", "")
        justification = result_data.get("justification", "")

        if verdict not in ("CLAIMANT_FAVORED", "RESPONDENT_FAVORED", "DISMISSED"):
            raise gl.vm.UserError(f"Consensus produced invalid verdict: {verdict}")

        dispute.status = "RESOLVED"
        dispute.verdict = verdict
        dispute.justification = justification[:1000]
        dispute.resolved_at = self._now()
        self.disputes[dispute_id] = dispute

        return verdict

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    @gl.public.view
    def get_dispute(self, dispute_id: str) -> str:
        """Retrieve dispute details by ID."""
        d = self.disputes.get(dispute_id, None)
        if d is None:
            return json.dumps({"exists": False})
        return json.dumps(
            {
                "exists": True,
                "dispute_id": d.dispute_id,
                "contract_terms": d.contract_terms,
                "claimant_evidence": d.claimant_evidence,
                "respondent_evidence": d.respondent_evidence,
                "status": d.status,
                "verdict": d.verdict,
                "justification": d.justification,
                "created_at": int(d.created_at),
                "resolved_at": int(d.resolved_at),
            }
        )

    @gl.public.view
    def total_disputes(self) -> u256:
        return self.next_id

    @gl.public.view
    def list_pending(self) -> str:
        out = []
        for k, d in self.disputes.items():
            if d.status == "PENDING":
                out.append({"dispute_id": k, "created_at": int(d.created_at)})
        return json.dumps(out)

    @gl.public.view
    def now(self) -> str:
        return self._now_iso()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> u256:
        return u256(int(datetime.now(timezone.utc).timestamp()))

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
