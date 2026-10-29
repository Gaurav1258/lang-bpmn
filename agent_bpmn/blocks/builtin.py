import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field

from agent_bpmn.sdk import domain_block

# ==============================================================================
# 1. Compliance Department: Sanctions & PEP Screening Block
# ==============================================================================

class SanctionCheckInput(BaseModel):
    entity_name: str = Field(..., description="Full legal name of the entity or individual")
    country_code: str = Field(..., min_length=2, max_length=2, description="Two-letter ISO 3166-1 alpha-2 country code")
    transaction_amount_usd: float = Field(..., ge=0.0, description="Associated transaction amount in USD")


class SanctionCheckOutput(BaseModel):
    is_flagged: bool = Field(..., description="True if entity matches sanctions, OFAC or PEP lists")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Calculated compliance risk score (0.0 to 1.0)")
    matched_entries: List[str] = Field(default_factory=list, description="Specific sanctions list matches, if any")
    compliance_note: str = Field(..., description="Summary of reasoning for audit trail")


OFAC_SANCTION_LIST = {
    "acme contraband corp": "OFAC SDN List (Weapons)",
    "redstar maritime ltd": "EU Sanctions Annex I (Trade Embargo)",
    "victor chavez": "PEP High Risk Political Associate",
}

HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "CU", "RU"}


@domain_block(
    id="compliance.sanctions_screener",
    name="Screen Against Sanctions List",
    department="Compliance",
    description="Cross-references counterparty against OFAC, EU, UN, and PEP international watchlists.",
    icon="shield-alert",
    estimated_cost_usd=0.004,
    p95_latency_ms=1200,
    tags=["compliance", "ofac", "kyc", "aml", "sanctions"],
)
async def screen_sanctions(payload: SanctionCheckInput) -> SanctionCheckOutput:
    await asyncio.sleep(0.05)
    entity_clean = payload.entity_name.strip().lower()
    matches: List[str] = []
    base_risk = 0.05

    for target_name, match_reason in OFAC_SANCTION_LIST.items():
        if target_name in entity_clean:
            matches.append(match_reason)
            base_risk = max(base_risk, 0.95)

    if payload.country_code.upper() in HIGH_RISK_COUNTRIES:
        matches.append(f"Jurisdiction '{payload.country_code.upper()}' is designated high-risk")
        base_risk = max(base_risk, 0.85)

    if payload.transaction_amount_usd > 100_000:
        base_risk = min(1.0, base_risk + 0.1)

    is_flagged = len(matches) > 0 or base_risk >= 0.75
    note = (
        f"Flagged for human review. Matches: {', '.join(matches)}"
        if is_flagged
        else "Sanctions screening passed clean. No watchlist records found."
    )

    return SanctionCheckOutput(
        is_flagged=is_flagged,
        risk_score=round(base_risk, 2),
        matched_entries=matches,
        compliance_note=note,
    )


# ==============================================================================
# 2. Finance Department: Invoice Line Items Extractor
# ==============================================================================

class InvoiceLineItem(BaseModel):
    description: str
    quantity: int = Field(default=1, ge=1)
    unit_price_usd: float = Field(..., ge=0.0)
    total_usd: float = Field(..., ge=0.0)


class InvoiceExtractInput(BaseModel):
    document_url: str = Field(..., description="Secure S3/GCS bucket URL to invoice PDF/image")
    vendor_tax_id: Optional[str] = Field(default=None, description="Optional known Vendor Tax / VAT ID")


class InvoiceExtractOutput(BaseModel):
    invoice_number: str
    vendor_name: str
    total_amount_usd: float = Field(..., ge=0.0)
    currency: str = "USD"
    line_items: List[InvoiceLineItem]
    confidence_score: float = Field(..., ge=0.0, le=1.0)


@domain_block(
    id="finance.invoice_extractor",
    name="Extract Invoice Line Items",
    department="Finance",
    description="Extracts structured vendor data, line items, and totals from PDF invoices using vision models.",
    icon="receipt-text",
    estimated_cost_usd=0.015,
    p95_latency_ms=1800,
    tags=["finance", "ap", "invoices", "ocr", "extraction"],
)
async def extract_invoice(payload: InvoiceExtractInput) -> InvoiceExtractOutput:
    await asyncio.sleep(0.08)
    doc_lower = payload.document_url.lower()
    if "suspicious" in doc_lower or "redstar" in doc_lower:
        return InvoiceExtractOutput(
            invoice_number="INV-2026-SUSP-01",
            vendor_name="RedStar Maritime Ltd (Cargo Delivery)",
            total_amount_usd=85000.00,
            currency="USD",
            line_items=[
                InvoiceLineItem(description="Maritime Vessel Fuel & Cargo", quantity=1, unit_price_usd=85000.00, total_usd=85000.00),
            ],
            confidence_score=0.94,
        )

    return InvoiceExtractOutput(
        invoice_number="INV-2026-9812",
        vendor_name="Apex Cloud Infrastructure Ltd",
        total_amount_usd=14500.00,
        currency="USD",
        line_items=[
            InvoiceLineItem(description="GPU Cluster Compute Reservation (Monthly)", quantity=2, unit_price_usd=6000.00, total_usd=12000.00),
            InvoiceLineItem(description="Enterprise SLA Support & Egress", quantity=1, unit_price_usd=2500.00, total_usd=2500.00),
        ],
        confidence_score=0.98,
    )


# ==============================================================================
# 3. Customer Care: Support Ticket Triage & Intent Classifier
# ==============================================================================

class SupportTicketInput(BaseModel):
    customer_email: str
    subject: str
    message_body: str
    account_tier: str = Field(default="STANDARD", description="Account tier: STANDARD, PRO, or ENTERPRISE")


class SupportTicketOutput(BaseModel):
    category: str = Field(..., description="Identified category: BILLING, TECHNICAL, CHURN_RISK, or GENERAL")
    urgency: str = Field(..., description="Assigned priority: P1_CRITICAL, P2_HIGH, P3_NORMAL")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Customer sentiment from -1.0 (angry) to +1.0 (happy)")
    recommended_routing: str


@domain_block(
    id="support.ticket_triage",
    name="Triage Customer Support Ticket",
    department="Customer Care",
    description="Classifies incoming customer inquiry by intent, urgency, and sentiment.",
    icon="life-buoy",
    estimated_cost_usd=0.002,
    p95_latency_ms=650,
    tags=["support", "triage", "nlp", "sentiment"],
)
def triage_ticket(payload: SupportTicketInput) -> SupportTicketOutput:
    body = payload.message_body.lower()
    if "cancel" in body or "churn" in body or "leaving" in body:
        category = "CHURN_RISK"
        urgency = "P1_CRITICAL" if payload.account_tier == "ENTERPRISE" else "P2_HIGH"
        sentiment = -0.7
        routing = "retention_specialist_queue"
    elif "invoice" in body or "refund" in body or "charged" in body:
        category = "BILLING"
        urgency = "P2_HIGH"
        sentiment = -0.3
        routing = "billing_support_queue"
    elif "error" in body or "500" in body or "broken" in body or "down" in body:
        category = "TECHNICAL"
        urgency = "P1_CRITICAL" if payload.account_tier == "ENTERPRISE" else "P2_HIGH"
        sentiment = -0.5
        routing = "tier_2_engineering"
    else:
        category = "GENERAL"
        urgency = "P3_NORMAL"
        sentiment = 0.2
        routing = "standard_inbox"

    return SupportTicketOutput(
        category=category,
        urgency=urgency,
        sentiment_score=sentiment,
        recommended_routing=routing,
    )


# ==============================================================================
# 4. Finance Department: Automated Payment Settlement
# ==============================================================================

class SettlementInput(BaseModel):
    invoice_number: str
    amount_usd: float
    vendor_name: str


class SettlementOutput(BaseModel):
    transaction_id: str
    status: str
    settled_amount: float
    settlement_timestamp: str


@domain_block(
    id="finance.auto_settlement",
    name="Auto-Settle Invoice Payment",
    department="Finance",
    description="Dispatches automated ACH/Wire payment for approved invoices.",
    icon="credit-card",
    estimated_cost_usd=0.001,
    p95_latency_ms=450,
    tags=["finance", "payments", "settlement"],
)
async def auto_settlement(payload: SettlementInput) -> SettlementOutput:
    await asyncio.sleep(0.02)
    return SettlementOutput(
        transaction_id=f"TXN-ACH-2026-{payload.invoice_number.replace('-', '')}",
        status="SETTLED_AUTOMATICALLY",
        settled_amount=payload.amount_usd,
        settlement_timestamp="2026-10-29T22:50:00Z",
    )


# ==============================================================================
# 5. Compliance Department: L2 Emergency Review Dispatch
# ==============================================================================

class EmergencyReviewInput(BaseModel):
    entity_name: str
    risk_score: float
    flag_reason: str = "OFAC_SDN_MATCH"


class EmergencyReviewOutput(BaseModel):
    case_docket_id: str
    assigned_queue: str
    status: str


@domain_block(
    id="compliance.emergency_review",
    name="Escalate to L2 Sanctions Review",
    department="Compliance",
    description="Opens an expedited compliance docket and notifies the Chief Compliance Officer.",
    icon="alert-octagon",
    estimated_cost_usd=0.002,
    p95_latency_ms=300,
    tags=["compliance", "audit", "escalation"],
)
async def emergency_review(payload: EmergencyReviewInput) -> EmergencyReviewOutput:
    await asyncio.sleep(0.02)
    return EmergencyReviewOutput(
        case_docket_id=f"CASE-L2-{payload.entity_name[:4].upper()}-991",
        assigned_queue="HIGH_PRIORITY_SANCTIONS_QUEUE",
        status="PENDING_SENIOR_OFFICER_SIGN_OFF",
    )


# ==============================================================================
# 6. Supply Chain Finance Department: Autonomous SCF & Working Capital Suite
# ==============================================================================

class SCFRiskInput(BaseModel):
    supplier_id: str = Field(..., description="Corporate supplier identifier in ERP")
    supplier_name: str = Field(..., description="Legal entity name")
    invoice_amount_usd: float = Field(..., ge=0.0)


class SCFRiskOutput(BaseModel):
    supplier_risk_score: float = Field(..., ge=0.0, le=1.0)
    financial_health_rating: str = Field(..., description="AAA, AA, A, BBB, BB, B, CCC")
    is_counterparty_flagged: bool = Field(...)
    acceptance_probability: float = Field(..., description="Predicted likelihood of supplier accepting early payment")


@domain_block(
    id="scf.risk_sentinel",
    name="Screen Supplier Counterparty Risk",
    department="Supply Chain Finance",
    description="Screens supplier counterparty risk, Altman-Z credit metrics, and predicts early settlement acceptance probability.",
    icon="shield-check",
    estimated_cost_usd=0.004,
    p95_latency_ms=650,
    tags=["scf", "risk", "credit", "supplier"],
)
async def scf_risk_sentinel(payload: SCFRiskInput) -> SCFRiskOutput:
    await asyncio.sleep(0.03)
    is_flagged = "flag" in payload.supplier_name.lower() or payload.invoice_amount_usd > 100_000
    risk = 0.85 if is_flagged else 0.15
    return SCFRiskOutput(
        supplier_risk_score=risk,
        financial_health_rating="BB" if is_flagged else "AA",
        is_counterparty_flagged=is_flagged,
        acceptance_probability=0.45 if is_flagged else 0.88,
    )


class CashForecastInput(BaseModel):
    corporate_buyer_id: str
    target_dpo_days: int = Field(default=60)
    horizon_days: int = Field(default=60)


class CashForecastOutput(BaseModel):
    projected_cash_buffer_usd: float
    liquidity_status: str
    recommended_deployment_limit_usd: float


@domain_block(
    id="scf.cash_forecaster",
    name="Project 60-Day Corporate Liquidity",
    department="Supply Chain Finance",
    description="Simulates corporate buyer 60-day cash curve, DPO impacts, and committed facility buffer headroom.",
    icon="trending-up",
    estimated_cost_usd=0.003,
    p95_latency_ms=500,
    tags=["scf", "liquidity", "forecasting", "treasury"],
)
async def scf_cash_forecaster(payload: CashForecastInput) -> CashForecastOutput:
    await asyncio.sleep(0.02)
    return CashForecastOutput(
        projected_cash_buffer_usd=485_000.0,
        liquidity_status="ADEQUATE_SURPLUS",
        recommended_deployment_limit_usd=150_000.0,
    )


class CapitalStructureInput(BaseModel):
    invoice_amount_usd: float
    days_to_maturity: int = Field(default=45)
    supplier_acceptance_probability: float = Field(default=0.85)


class CapitalStructureOutput(BaseModel):
    recommended_product: str = Field(..., description="DYNAMIC_DISCOUNTING or REVERSE_FACTORING")
    early_payment_amount_usd: float
    discount_yield_apr: float
    buyer_discount_savings_usd: float


@domain_block(
    id="scf.capital_structurer",
    name="Optimize Dynamic Discount vs Reverse Factoring",
    department="Supply Chain Finance",
    description="Calculates APR arbitrage, day-count discount math, and optimal allocation between balance-sheet cash and bank facility.",
    icon="sliders",
    estimated_cost_usd=0.005,
    p95_latency_ms=750,
    tags=["scf", "structuring", "discount", "factoring"],
)
async def scf_capital_structurer(payload: CapitalStructureInput) -> CapitalStructureOutput:
    await asyncio.sleep(0.03)
    is_rf = payload.invoice_amount_usd > 25000
    apr = 18.5 if not is_rf else 12.0
    discount = round(payload.invoice_amount_usd * (apr / 100.0) * (payload.days_to_maturity / 365.0), 2)
    return CapitalStructureOutput(
        recommended_product="REVERSE_FACTORING" if is_rf else "DYNAMIC_DISCOUNTING",
        early_payment_amount_usd=round(payload.invoice_amount_usd - discount, 2),
        discount_yield_apr=apr,
        buyer_discount_savings_usd=discount,
    )


class FacilityValidatorInput(BaseModel):
    bank_facility_id: str
    drawdown_request_amount_usd: float


class FacilityValidatorOutput(BaseModel):
    is_facility_approved: bool
    remaining_headroom_usd: float
    financing_bank_name: str
    compliance_covenant_status: str


@domain_block(
    id="scf.guardrail_validator",
    name="Verify Bank Credit Facility Headroom",
    department="Supply Chain Finance",
    description="Validates corporate buyer's revolving credit line facility headroom and confirms loan covenant status.",
    icon="check-circle",
    estimated_cost_usd=0.002,
    p95_latency_ms=400,
    tags=["scf", "banking", "credit_line", "covenants"],
)
async def scf_facility_validator(payload: FacilityValidatorInput) -> FacilityValidatorOutput:
    await asyncio.sleep(0.02)
    headroom = 2_450_000.0 - payload.drawdown_request_amount_usd
    return FacilityValidatorOutput(
        is_facility_approved=headroom > 0,
        remaining_headroom_usd=max(0.0, headroom),
        financing_bank_name="Global Corporate & Investment Bank (Citibank N.A.)",
        compliance_covenant_status="COMPLIANT_WITHIN_LEVERAGE_RATIO",
    )


class TreasuryDispatchInput(BaseModel):
    invoice_number: str
    supplier_name: str
    drawdown_amount_usd: float
    financing_facility_id: str


class TreasuryDispatchOutput(BaseModel):
    drawdown_reference_id: str
    bank_ack_timestamp: str
    execution_status: str


@domain_block(
    id="scf.treasury_dispatcher",
    name="Dispatch Bank Facility Drawdown",
    department="Supply Chain Finance",
    description="Dispatches ISO 20022 / MT103 drawdown instructions to corporate banking API rails and records ERP payment.",
    icon="send",
    estimated_cost_usd=0.003,
    p95_latency_ms=550,
    tags=["scf", "treasury", "drawdown", "erp", "banking"],
)
async def scf_treasury_dispatcher(payload: TreasuryDispatchInput) -> TreasuryDispatchOutput:
    await asyncio.sleep(0.03)
    return TreasuryDispatchOutput(
        drawdown_reference_id=f"DRAW-2026-SCF-{payload.invoice_number.replace('-', '')}",
        bank_ack_timestamp="2026-10-30T02:00:00Z",
        execution_status="FUNDS_DISBURSED_TO_SUPPLIER_ACCOUNT",
    )

