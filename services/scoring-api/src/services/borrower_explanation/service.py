"""
Borrower-Facing Score Explanation — different vocabulary from lender-facing one.
Per PRD FR-014: "different vocabulary, actionable framing."

Lender explanation: technical, risk-focused
Borrower explanation: plain language, improvement-focused, empowering
"""

BORROWER_POSITIVE_TEMPLATES = {
    "no_delinquency": "You've kept up with your credit payments — this helps your score!",
    "long_history": "Your long credit history ({months} months) shows financial stability.",
    "telco_consistent": "Your phone and mobile money usage patterns look consistent.",
    "utility_streak": "You've made {streak} utility payments on time — that's great!",
    "mobile_inflow": "Your mobile money is growing — lenders see this as positive.",
    "default": "You have a solid financial track record.",
}

BORROWER_NEGATIVE_TEMPLATES = {
    "delinquent": "You've missed some payments. Catching up on overdue balances would help.",
    "many_inquiries": "Multiple recent credit applications can lower your score. Space them out.",
    "no_alt_data": "Link your phone and utility accounts to show more of your financial picture.",
    "thin_file": "You don't have many credit accounts yet. Building a history will improve your score.",
    "default": "Your score could improve with more financial activity.",
}


def generate_borrower_explanation(
    lender_positive_factors: list,
    lender_negative_factors: list,
    features: dict,
) -> dict:
    """
    Generate a borrower-friendly score explanation.
    Uses simple language, actionable framing, and avoids risk jargon.
    PRD FR-014.
    """
    borrower_positive = []
    borrower_negative = []

    # Map lender factors to borrower-friendly language
    for factor in lender_positive_factors[:3]:
        factor_lower = factor.lower()

        if "no delinquency" in factor_lower or "no missed" in factor_lower:
            borrower_positive.append(BORROWER_POSITIVE_TEMPLATES["no_delinquency"])
        elif "long credit history" in factor_lower or "months demonstrates" in factor_lower:
            months = _extract_months(factor_lower) or features.get("oldest_account_age_months", 0)
            borrower_positive.append(
                BORROWER_POSITIVE_TEMPLATES["long_history"].format(months=int(months))
            )
        elif "telco" in factor_lower or "mobile" in factor_lower:
            borrower_positive.append(BORROWER_POSITIVE_TEMPLATES["telco_consistent"])
        elif "utility" in factor_lower and "payment" in factor_lower:
            streak = _extract_number(factor_lower) or features.get("utility_payment_streak", 0)
            borrower_positive.append(
                BORROWER_POSITIVE_TEMPLATES["utility_streak"].format(streak=int(streak))
            )
        elif "inflow" in factor_lower:
            borrower_positive.append(BORROWER_POSITIVE_TEMPLATES["mobile_inflow"])
        else:
            borrower_positive.append(BORROWER_POSITIVE_TEMPLATES["default"])

    for factor in lender_negative_factors[:3]:
        factor_lower = factor.lower()

        if "delinquency" in factor_lower or "missed" in factor_lower:
            borrower_negative.append(BORROWER_NEGATIVE_TEMPLATES["delinquent"])
        elif "inquir" in factor_lower:
            borrower_negative.append(BORROWER_NEGATIVE_TEMPLATES["many_inquiries"])
        elif "alternative" in factor_lower or "limited" in factor_lower:
            borrower_negative.append(BORROWER_NEGATIVE_TEMPLATES["no_alt_data"])
        elif "thin" in factor_lower or "few" in factor_lower:
            borrower_negative.append(BORROWER_NEGATIVE_TEMPLATES["thin_file"])
        else:
            borrower_negative.append(BORROWER_NEGATIVE_TEMPLATES["default"])

    return {
        "positive_factors": borrower_positive[:3],
        "negative_factors": borrower_negative[:3],
        "actionable_tips": _generate_actionable_tips(features),
    }


def _generate_actionable_tips(features: dict) -> list:
    """Generate personalized, actionable improvement tips."""
    tips = []

    if features.get("bureau_delinquency_flag", 0) > 0:
        tips.append("Pay any overdue balances first — this has the biggest impact on your score.")

    if features.get("total_credit_accounts", 0) < 2:
        tips.append(
            "Consider opening a savings account or getting a small credit line to build your history."
        )

    if features.get("telco_consistency_index", 0) < 0.5:
        tips.append(
            "Link your phone number to mobile money services — regular usage improves your score."
        )

    if features.get("utility_payment_streak", 0) < 3:
        tips.append("Pay utility bills (electricity, water) on time — every payment counts.")

    if features.get("recent_inquiries_6m", 0) > 5:
        tips.append(
            "Avoid applying for multiple loans at once — each inquiry can slightly lower your score."
        )

    if features.get("credit_utilization_ratio", 0) > 0.7:
        tips.append(
            "Try to use less than 70% of your available credit — high utilization hurts your score."
        )

    if not tips:
        tips.append("Keep doing what you're doing — your financial habits look good!")

    return tips[:3]


def _extract_months(text: str) -> int | None:
    """Extract number of months from text like '24 months'."""
    import re
    match = re.search(r"(\d+)\s*month", text)
    return int(match.group(1)) if match else None


def _extract_number(text: str) -> int | None:
    """Extract the first number from text."""
    import re
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None
