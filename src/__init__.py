# ============================================================================
# BACKTEST GC/SI - Package Source
# ============================================================================
#
# Ce package contient tous les modules du systeme de backtest :
#   - common : Constantes d'etats et fonctions partagees
#   - data_loader : Chargement et synchronisation des donnees
#   - indicators : Calculs des indicateurs (Beta, Z-Score, etc.)
#   - position : Gestion des positions et sizing
#   - backtest_engine : Moteur de simulation
#   - metrics : Calcul des metriques de performance
#
# ============================================================================

from .common import (
    STATE_FLAT, STATE_LONG, STATE_SHORT,
    STATE_COOLDOWN_LONG, STATE_COOLDOWN_SHORT,
    check_entry_conditions, check_zscore_exit,
    check_cooldown_reset, calculate_current_pnl,
    build_config_fingerprint
)

from .data_loader import (
    load_config,
    load_sierra_chart_data,
    synchronize_data,
    validate_data,
    load_and_prepare_data,
    get_price_at_datetime
)

from .indicators import (
    calculate_all_indicators,
    get_indicators_at_datetime
)

from .position import (
    calculate_position_size,
    calculate_transaction_costs,
    calculate_trade_pnl
)

from .archive_manager import (
    archive_config,
    archive_top_n_from_grid,
    generate_rankings,
    generate_dashboard,
    list_configs,
)

__version__ = "1.0.0"
__author__ = "Assistant IA"
