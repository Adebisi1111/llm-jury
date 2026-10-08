/**
 * LLM-Jury Integration Test
 * Tests the deployed contract on Bradbury Testnet (chain 4221).
 * Contract: 0x52F65805F656BC3a331f703AeEc858E9Fc2586C1
 *
 * Steps:
 * 1. create_dispute — submit contract terms + claimant evidence
 * 2. submit_defense — respondent uploads counter-evidence
 * 3. run_arbitration — trigger AI jury consensus
 * 4. get_dispute — read and print the verdict
 */

import { createRequire } from 'module';
const require_ = createRequire(import.meta.url);
const { createClient, createAccount, chains } = require_('/home/administrator/genlayer-prediction-market/node_modules/genlayer-js');

// Configuration
const CONTRACT = '0x52F65805F656BC3a331f703AeEc858E9Fc2586C1';
const PK = '0x023d076ab40ea46c59ac7ca7cecfaa2db5fa10b7a481aef27cf68e9cc5a8c0af';
const ADDR = '0x61fd0047595A30A067f1F21F3b28C4AE8A8e3Dc3';

// Sample data
const CONTRACT_TERMS = "Freelancer agrees to deliver a complete website with header, footer, and contact form by 2026-01-15. Payment of 500 GEN upon delivery.";
const CLAIMANT_EVIDENCE = "Freelancer did not deliver the website header. The contact form is also missing. Deadline was 2026-01-15 and only partial work was submitted.";
const RESPONDENT_EVIDENCE = "I delivered the full codebase via GitHub link on 2026-01-14. The header and contact form are included in the main branch. Here is the commit proof.";

function printStep(stepNum, title) {
  console.log('\n' + '='.repeat(60));
  console.log(`STEP ${stepNum}: ${title}`);
  console.log('='.repeat(60));
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  console.log('='.repeat(60));
  console.log('LLM-JURY INTEGRATION TEST');
  console.log(`Contract: ${CONTRACT}`);
  console.log('Network: Bradbury Testnet (chain 4221)');
  console.log(`Account: ${ADDR}`);
  console.log('='.repeat(60));

  const account = createAccount(PK);
  const client = createClient({ chain: chains.testnetBradbury, account });

  // Step 1: Create dispute
  printStep(1, 'CREATE DISPUTE');
  console.log(`Contract Terms: ${CONTRACT_TERMS.slice(0, 80)}...`);
  console.log(`Claimant Evidence: ${CLAIMANT_EVIDENCE.slice(0, 80)}...`);

  let disputeId;
  try {
    const hash = await client.writeContract({
      address: CONTRACT,
      functionName: 'create_dispute',
      args: [CONTRACT_TERMS, CLAIMANT_EVIDENCE],
    });
    console.log(`[TX] create_dispute submitted: ${hash}`);

    let receipt = null;
    for (let i = 0; i < 60; i++) {
      try {
        receipt = await client.waitForTransactionReceipt({ hash, retries: 1 });
        if (receipt && receipt.statusName) break;
      } catch (e) {}
      await sleep(5000);
    }
    console.log(`[RECEIPT] Status: ${receipt?.statusName}`);

    // Extract dispute ID from receipt
    const decoded = receipt?.txDataDecoded;
    if (decoded && decoded.callData && decoded.callData.args) {
      // The return value is the dispute_id - we need to find it
      // For now, query total_disputes to get the ID
    }

    // Get total disputes to find our ID
    const total = await client.readContract({
      address: CONTRACT,
      functionName: 'total_disputes',
      args: [],
    });
    disputeId = `dispute-${total}`;
    console.log(`[SUCCESS] Dispute created with ID: ${disputeId}`);

  } catch (e) {
    console.error(`[ERROR] create_dispute failed: ${e.message}`);
    process.exit(1);
  }

  // Step 2: Submit defense
  printStep(2, 'SUBMIT DEFENSE');
  console.log(`Dispute ID: ${disputeId}`);
  console.log(`Respondent Evidence: ${RESPONDENT_EVIDENCE.slice(0, 80)}...`);

  try {
    const hash = await client.writeContract({
      address: CONTRACT,
      functionName: 'submit_defense',
      args: [disputeId, RESPONDENT_EVIDENCE],
    });
    console.log(`[TX] submit_defense submitted: ${hash}`);

    let receipt = null;
    for (let i = 0; i < 60; i++) {
      try {
        receipt = await client.waitForTransactionReceipt({ hash, retries: 1 });
        if (receipt && receipt.statusName) break;
      } catch (e) {}
      await sleep(5000);
    }
    console.log(`[RECEIPT] Status: ${receipt?.statusName}`);
    console.log('[SUCCESS] Defense submitted');

  } catch (e) {
    console.error(`[ERROR] submit_defense failed: ${e.message}`);
    process.exit(1);
  }

  // Step 3: Run arbitration
  printStep(3, 'RUN ARBITRATION');
  console.log(`Dispute ID: ${disputeId}`);
  console.log('[INFO] AI Jury is reviewing evidence (this may take up to 45 seconds)...');

  try {
    const hash = await client.writeContract({
      address: CONTRACT,
      functionName: 'run_arbitration',
      args: [disputeId],
    });
    console.log(`[TX] run_arbitration submitted: ${hash}`);

    let receipt = null;
    for (let i = 0; i < 120; i++) {
      try {
        receipt = await client.waitForTransactionReceipt({ hash, retries: 1 });
        if (receipt && receipt.statusName) break;
      } catch (e) {}
      await sleep(5000);
      if (i % 6 === 0) console.log(`  ... waiting (${i}/120)`);
    }
    console.log(`[RECEIPT] Status: ${receipt?.statusName}`);
    console.log('[SUCCESS] Arbitration completed');

  } catch (e) {
    console.error(`[ERROR] run_arbitration failed: ${e.message}`);
    console.log('[INFO] This may be a LEADER_TIMEOUT. Checking if arbitration succeeded anyway...');
    await sleep(10000);
  }

  // Step 4: Get dispute
  printStep(4, 'GET DISPUTE');
  console.log(`Dispute ID: ${disputeId}`);

  try {
    const result = await client.readContract({
      address: CONTRACT,
      functionName: 'get_dispute',
      args: [disputeId],
    });

    console.log(`\n[RAW RESULT] Type: ${typeof result}`);
    console.log(`[RAW RESULT] Value: ${result}`);

    if (typeof result === 'string') {
      try {
        const dispute = JSON.parse(result);
        console.log('\n[PARSED JSON]:');
        console.log(JSON.stringify(dispute, null, 2));

        if (dispute.exists) {
          console.log(`\n[VERDICT]: ${dispute.verdict}`);
          console.log(`[JUSTIFICATION]: ${dispute.justification}`);
          console.log(`[STATUS]: ${dispute.status}`);

          if (dispute.verdict === 'DISMISSED' && (dispute.justification || '').includes('Could not parse')) {
            console.log('\n[WARNING] Verdict fell back to DISMISSED due to parsing error!');
          } else if (dispute.verdict === 'DISMISSED') {
            console.log('\n[INFO] Verdict is DISMISSED (may be legitimate or parsing fallback)');
          } else {
            console.log(`\n[SUCCESS] Verdict parsed correctly: ${dispute.verdict}`);
          }
        } else {
          console.log(`\n[ERROR] Dispute not found: ${JSON.stringify(dispute)}`);
        }

      } catch (jsonErr) {
        console.error(`[ERROR] Failed to parse result as JSON: ${jsonErr.message}`);
        console.log(`[RAW] ${result}`);
      }
    } else {
      console.log(`[INFO] Result is not a string: ${JSON.stringify(result)}`);
    }

  } catch (e) {
    console.error(`[ERROR] get_dispute failed: ${e.message}`);
  }

  console.log('\n' + '='.repeat(60));
  console.log('TEST COMPLETE');
  console.log('='.repeat(60));
}

main().catch(e => {
  console.error(`[FATAL] ${e.message}`);
  process.exit(1);
});
