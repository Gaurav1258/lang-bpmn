# 🧪 Pre-Flight Simulation Report: `hybrid_invoice_routing_flow` (v1.3.0)
**Simulation ID:** `sim_audit_pr_982` | **Generated:** 2026-10-29T18:58:03.058757+00:00
**Cases Evaluated:** 15 Historical Production Runs

## 📊 Executive Summary Diff
| Metric | Production Baseline | Candidate Version | Delta | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Success Rate** | 100.0% | 100.0% | +0.0% | ✅ PASS |
| **Average Cost** | $0.0220 USD | $0.0210 USD | -4.5% | ✅ DECREASED |
| **Average Latency** | 130.0 ms | 185.7 ms | +42.9% | ℹ️ SLOWER |
| **Schema Violations** | 0 | 0 | 0 | ✅ ZERO CRASHES |

## 🔀 Route Distribution Shifts
| Destination Route / Node | Baseline Share | Candidate Share | Shift (% Points) | Direction |
| :--- | :--- | :--- | :--- | :--- |
| `auto_payment_settlement` | 80.0% | 0.0% | -80.0% | 📉 Decreased (-) |
| `emergency_compliance_review` | 20.0% | 100.0% | +80.0% | 📈 Increased (+) |

## ⚠️ Critical Findings & Guardrails
- 🔀 Significant route shift on 'auto_payment_settlement': decreased by 80.0% points (80.0% -> 0.0%).
- 🔀 Significant route shift on 'emergency_compliance_review': increased by 80.0% points (20.0% -> 100.0%).