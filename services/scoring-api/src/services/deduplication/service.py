"""
Deduplication Service — merges records across sources by BVN + phone.
Per PRD FR-009: "Deduplicate records across sources using BVN as the primary
key and phone number as a secondary key."
"""

import logging
from typing import Any, Dict, List, Optional

from src.core.security import hash_bvn, hash_phone

logger = logging.getLogger(__name__)


class DeduplicationService:
    """
    Merges data from multiple sources for the same borrower.
    Uses BVN as primary dedup key, phone as secondary.
    """

    def merge_bureau_data(
        self,
        bvn: str,
        phone: str,
        bureau_records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Merge bureau records from multiple sources (CRC, FirstCentral, CreditRegistry).
        
        Strategy:
        - Take the most recent record as the base
        - Fill in missing fields from other records
        - Aggregate account counts, flags, and inquiries across all sources
        """
        if not bureau_records:
            return {}

        bvn_hash = hash_bvn(bvn)
        phone_hash = hash_phone(phone)

        # Sort by data freshness (prefer records with more fields)
        sorted_records = sorted(
            bureau_records,
            key=lambda r: self._completeness_score(r),
            reverse=True,
        )

        merged = dict(sorted_records[0])  # Start with most complete record

        # Aggregate across all sources
        total_accounts = 0
        total_delinquent = 0
        total_outstanding = 0
        all_flags: list = []
        total_inquiries = 0
        max_oldest_age = 0

        for record in sorted_records:
            total_accounts += record.get("total_accounts", 0) or 0
            total_delinquent += record.get("delinquent_accounts", 0) or 0
            total_outstanding += record.get("total_outstanding_balance", 0) or 0
            all_flags.extend(record.get("delinquency_flags", []))
            total_inquiries += record.get("inquiries_last_6_months", 0) or 0
            age = record.get("oldest_account_age_months") or 0
            max_oldest_age = max(max_oldest_age, age)

        merged["total_accounts"] = total_accounts
        merged["delinquent_accounts"] = total_delinquent
        merged["total_outstanding_balance"] = total_outstanding
        merged["delinquency_flags"] = list(set(all_flags))  # Deduplicate flags
        merged["inquiries_last_6_months"] = total_inquiries
        merged["oldest_account_age_months"] = max_oldest_age

        # Average bureau score if multiple sources
        scores = [
            r.get("credit_score")
            for r in sorted_records
            if r.get("credit_score")
        ]
        if len(scores) > 1:
            merged["credit_score"] = sum(scores) / len(scores)

        merged["_source_count"] = len(bureau_records)
        merged["_bvn_hash"] = bvn_hash
        merged["_phone_hash"] = phone_hash

        return merged

    def merge_all_tier_data(
        self,
        bvn: str,
        phone: str,
        formal_data: List[Dict[str, Any]],
        alternative_data: Optional[List[Dict[str, Any]]] = None,
        psychographic_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Merge data from all tiers for a borrower.
        Returns a unified borrower risk profile.
        """
        profile = {}

        # Merge formal (bureau + bank)
        if formal_data:
            profile["formal"] = self.merge_bureau_data(bvn, phone, formal_data)

        # Merge alternative (telco + mobile money + utility)
        if alternative_data:
            profile["alternative"] = self._merge_alternative_data(alternative_data)

        # Merge psychographic
        if psychographic_data:
            profile["psychographic"] = self._merge_psychographic_data(psychographic_data)

        # Calculate overall data coverage
        total_possible = 3  # formal + alternative + psychographic
        available = sum(1 for v in profile.values() if v)
        profile["data_coverage_pct"] = (available / total_possible) * 100

        return profile

    def _merge_alternative_data(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge alternative data sources."""
        if not records:
            return {}
        merged = dict(records[0])
        for record in records[1:]:
            for key, value in record.items():
                if key not in merged or value is not None:
                    merged[key] = value
        return merged

    def _merge_psychographic_data(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge psychographic data sources."""
        if not records:
            return {}
        merged = dict(records[0])
        for record in records[1:]:
            for key, value in record.items():
                if key not in merged or value is not None:
                    merged[key] = value
        return merged

    @staticmethod
    def _completeness_score(record: Dict[str, Any]) -> int:
        """Score a record's completeness (number of non-null fields)."""
        return sum(1 for v in record.values() if v is not None)
