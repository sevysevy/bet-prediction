"""
Portals package — Modules de filtrage et de gestion des portails de paris sportifs.
"""

__all__ = []

# Portail 1 : Option 1 (Double Tier / Coffre-fort & Pépites)
try:
    from src.portals.portal1_double_tier import (
        filter_portal_1,
        get_portal_1_summary,
        partition_by_tier,
        get_match_dedup_key,
    )
    __all__.extend([
        "filter_portal_1",
        "get_portal_1_summary",
        "partition_by_tier",
        "get_match_dedup_key",
    ])
except ImportError:
    pass

# Portail 2 : Option 2 (Ratio de Sharpe Sportif / Markowitz-Kelly)
try:
    from src.portals.portal2_sharpe import (
        filter_portal_2,
        compute_bet_sigma,
        compute_bet_sharpe,
        compute_bet_quality_index,
        audit_portal_2,
    )
    __all__.extend([
        "filter_portal_2",
        "compute_bet_sigma",
        "compute_bet_sharpe",
        "compute_bet_quality_index",
        "audit_portal_2",
    ])
except ImportError:
    pass

# Portail 3 : Option 3 (Filtre Dur Sécuritaire / Anti-Bruit Strict)
try:
    from src.portals.portal3_hard_filter import (
        filter_portal_3,
        evaluate_candidate,
        audit_portal_3,
    )
    __all__.extend([
        "filter_portal_3",
        "evaluate_candidate",
        "audit_portal_3",
    ])
except ImportError:
    pass
