# LLM-Jury — Decentralized AI Arbitration Platform

A GenLayer-native decentralized arbitration platform where AI validators resolve peer-to-peer text contract disputes.

## How It Works

1. **Create Dispute** — Submit contract terms and claimant evidence
2. **Submit Defense** — Respondent uploads their evidence
3. **Trigger AI Jury** — 5 AI validators independently review the case and produce a verdict
4. **Verdict** — Majority consensus determines: CLAIMANT_FAVORED, RESPONDENT_FAVORED, or DISMISSED

## Contract

- **Network:** GenLayer Bradbury Testnet (chain 4221)
- **Contract:** `0x0000000000000000000000000000000000000000` (deployed address TBD)

## Quick Start

```bash
# Deploy contract
genlayer network set testnet-bradbury
genlayer deploy --contract contracts/llm_jury.py

# Create dispute
genlayer write <address> create_dispute --args "Contract terms..." "Claimant evidence..."

# Submit defense
genlayer write <address> submit_defense --args dispute-1 "Respondent evidence..."

# Run arbitration
genlayer write <address> run_arbitration --args dispute-1

# Read dispute
genlayer call <address> get_dispute --args dispute-1
```

## Frontend

Open `index.html` in a browser with a Web3 wallet connected to Bradbury Testnet (chain 4221).

## Tech Stack

- **Contract:** Python GenLayer Intelligent Contract
- **Consensus:** `gl.vm.run_nondet` with leader/validator pattern
- **AI:** `gl.nondet.exec_prompt` for legal reasoning
- **Frontend:** Vanilla HTML/CSS/JS
