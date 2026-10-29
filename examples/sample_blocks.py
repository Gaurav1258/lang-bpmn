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


# Mock sanctions watchlist
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
    """
    Developer-encapsulated logic.
    Engineering manages the vector retrieval, external screening APIs, and LLM prompts.
    Management only sees the inputs, outputs, and the business node in the canvas.
    """
    await asyncio.sleep(0.05)  # Simulate API network roundtrip

    entity_clean = payload.entity_name.strip().lower()
    matches: List[str] = []
    base_risk = 0.05

    # Check watchlist
    for target_name, match_reason in OFAC_SANCTION_LIST.items():
        if target_name in entity_clean:
            matches.append(match_reason)
            base_risk = max(base_risk, 0.95)

    # Check high-risk country
    if payload.country_code.upper() in HIGH_RISK_COUNTRIES:
        matches.append(f"Jurisdiction '{payload.country_code.upper()}' is designated high-risk")
        base_risk = max(base_risk, 0.85)

    # High transaction amount surcharge
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
    """
    Simulates high-precision LLM Vision extraction from an invoice PDF.
    """
    await asyncio.sleep(0.08)

    # In production, this would invoke Claude 3.5 Sonnet / Gemini Vision with OCR tools
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
    """
    Sync domain block example demonstrating classification.
    """
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

