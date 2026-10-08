"""
LLM-Jury Integration Test
Tests the deployed contract on Bradbury Testnet (chain 4221).
Contract: 0x52F65805F656BC3a331f703AeEc858E9Fc2586C1

Steps:
1. create_dispute — submit contract terms + claimant evidence
2. submit_defense — respondent uploads counter-evidence
3. run_arbitration — trigger AI jury consensus
4. get_dispute — read and print the verdict

Uses genlayer CLI via subprocess for all contract interactions.
"""

import json
import subprocess
import sys
import time

# Configuration
CONTRACT = '0xb8d96Dca02F3BFd789F198deA138625621f52Ee2'
RPC = 'https://rpc-bradbury.genlayer.com'
CHAIN_ID = 4221
KEYSTORE_PASSWORD = 'Okikiola1!'
FEES = '{"gasLimit":"0x186a0","gasPrice":"0x0bebc200"}'

# Sample data
CONTRACT_TERMS = "Freelancer agrees to deliver a complete website with header, footer, and contact form by 2026-01-15. Payment of 500 GEN upon delivery."
CLAIMANT_EVIDENCE = "Freelancer did not deliver the website header. The contact form is also missing. Deadline was 2026-01-15 and only partial work was submitted."
RESPONDENT_EVIDENCE = "I delivered the full codebase via GitHub link on 2026-01-14. The header and contact form are included in the main branch. Here is the commit proof."


def print_step(step_num, title):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*60}")


def run_genlayer(args, timeout=300):
    """Run genlayer CLI command and return output."""
    cmd = f"printf '{KEYSTORE_PASSWORD}\\n' | genlayer {args} 2>&1"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"


def wait_for_tx(tx_hash, max_wait=300):
    """Poll for transaction receipt."""
    print(f"[INFO] Waiting for tx {tx_hash[:20]}...")
    for i in range(max_wait // 5):
        output = run_genlayer(f"receipt {tx_hash}", timeout=30)
        if "ACCEPTED" in output or "FINALIZED" in output:
            print(f"[RECEIPT] Transaction confirmed")
            return True
        if "error" in output.lower() and "not found" not in output.lower():
            print(f"[WARN] Receipt output: {output[:200]}")
        time.sleep(5)
    print(f"[WARN] Transaction not confirmed after {max_wait}s")
    return False


def main():
    print("=" * 60)
    print("LLM-JURY INTEGRATION TEST")
    print(f"Contract: {CONTRACT}")
    print(f"Network: Bradbury Testnet (chain {CHAIN_ID})")
    print("=" * 60)

    # Step 1: Create dispute
    print_step(1, "CREATE DISPUTE")
    print(f"Contract Terms: {CONTRACT_TERMS[:80]}...")
    print(f"Claimant Evidence: {CLAIMANT_EVIDENCE[:80]}...")

    try:
        output = run_genlayer(
            f'write {CONTRACT} create_dispute '
            f'--args "{CONTRACT_TERMS}" "{CLAIMANT_EVIDENCE}" '
            f'--fees \'{FEES}\'',
            timeout=120
        )
        print(f"[OUTPUT] {output[:500]}")

        # Extract tx hash
        tx_hash = None
        for line in output.split('\n'):
            if '0x' in line and len(line) > 40:
                # Find tx hash in output
                parts = line.split()
                for part in parts:
                    if part.startswith('0x') and len(part) == 66:
                        tx_hash = part
                        break
            if tx_hash:
                break

        if not tx_hash:
            print("[ERROR] Could not extract transaction hash from output")
            print(f"[DEBUG] Full output: {output}")
            sys.exit(1)

        print(f"[TX] create_dispute submitted: {tx_hash}")
        wait_for_tx(tx_hash)

        # Get total disputes to find our ID
        output = run_genlayer(f"call {CONTRACT} total_disputes", timeout=30)
        print(f"[OUTPUT] total_disputes: {output[:200]}")

        # Parse total
        total = 0
        for line in output.split('\n'):
            line = line.strip()
            if line.isdigit():
                total = int(line)
                break

        dispute_id = f"dispute-{total}"
        print(f"[SUCCESS] Dispute created with ID: {dispute_id}")

    except Exception as e:
        print(f"[ERROR] create_dispute failed: {e}")
        sys.exit(1)

    # Step 2: Submit defense
    print_step(2, "SUBMIT DEFENSE")
    print(f"Dispute ID: {dispute_id}")
    print(f"Respondent Evidence: {RESPONDENT_EVIDENCE[:80]}...")

    try:
        output = run_genlayer(
            f'write {CONTRACT} submit_defense '
            f'--args "{dispute_id}" "{RESPONDENT_EVIDENCE}" '
            f'--fees \'{FEES}\'',
            timeout=120
        )
        print(f"[OUTPUT] {output[:500]}")

        # Extract tx hash
        tx_hash = None
        for line in output.split('\n'):
            if '0x' in line and len(line) > 40:
                parts = line.split()
                for part in parts:
                    if part.startswith('0x') and len(part) == 66:
                        tx_hash = part
                        break
            if tx_hash:
                break

        if not tx_hash:
            print("[ERROR] Could not extract transaction hash from output")
            print(f"[DEBUG] Full output: {output}")
            sys.exit(1)

        print(f"[TX] submit_defense submitted: {tx_hash}")
        wait_for_tx(tx_hash)
        print("[SUCCESS] Defense submitted")

    except Exception as e:
        print(f"[ERROR] submit_defense failed: {e}")
        sys.exit(1)

    # Step 3: Run arbitration
    print_step(3, "RUN ARBITRATION")
    print(f"Dispute ID: {dispute_id}")
    print("[INFO] AI Jury is reviewing evidence (this may take up to 45 seconds)...")

    try:
        output = run_genlayer(
            f'write {CONTRACT} run_arbitration '
            f'--args "{dispute_id}" '
            f'--fees \'{FEES}\'',
            timeout=300
        )
        print(f"[OUTPUT] {output[:500]}")

        # Extract tx hash
        tx_hash = None
        for line in output.split('\n'):
            if '0x' in line and len(line) > 40:
                parts = line.split()
                for part in parts:
                    if part.startswith('0x') and len(part) == 66:
                        tx_hash = part
                        break
            if tx_hash:
                break

        if not tx_hash:
            print("[ERROR] Could not extract transaction hash from output")
            print(f"[DEBUG] Full output: {output}")
            sys.exit(1)

        print(f"[TX] run_arbitration submitted: {tx_hash}")

        # Wait for consensus
        print("[INFO] Waiting for consensus...")
        confirmed = wait_for_tx(tx_hash, max_wait=300)

        if not confirmed:
            print("[WARN] Transaction not confirmed yet. Checking state anyway...")
            time.sleep(10)

    except Exception as e:
        print(f"[ERROR] run_arbitration failed: {e}")
        print("[INFO] This may be a LEADER_TIMEOUT. Checking if arbitration succeeded anyway...")
        time.sleep(10)

    # Step 4: Get dispute
    print_step(4, "GET DISPUTE")
    print(f"Dispute ID: {dispute_id}")

    try:
        output = run_genlayer(
            f'call {CONTRACT} get_dispute --args "{dispute_id}"',
            timeout=60
        )
        print(f"\n[RAW OUTPUT]:")
        print(output)

        # Try to find JSON in output
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = output[json_start:json_end]
            try:
                dispute = json.loads(json_str)
                print(f"\n[PARSED JSON]:")
                print(json.dumps(dispute, indent=2))

                if dispute.get("exists"):
                    print(f"\n[VERDICT]: {dispute.get('verdict')}")
                    print(f"[JUSTIFICATION]: {dispute.get('justification')}")
                    print(f"[STATUS]: {dispute.get('status')}")

                    if dispute.get("verdict") == "DISMISSED" and "Could not parse" in dispute.get("justification", ""):
                        print("\n[WARNING] Verdict fell back to DISMISSED due to parsing error!")
                    elif dispute.get("verdict") == "DISMISSED":
                        print("\n[INFO] Verdict is DISMISSED (may be legitimate or parsing fallback)")
                    else:
                        print(f"\n[SUCCESS] Verdict parsed correctly: {dispute.get('verdict')}")
                else:
                    print(f"\n[ERROR] Dispute not found: {json.dumps(dispute)}")

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON: {e}")
                print(f"[RAW JSON STR] {json_str}")
        else:
            print("[ERROR] No JSON found in output")

    except Exception as e:
        print(f"[ERROR] get_dispute failed: {e}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
