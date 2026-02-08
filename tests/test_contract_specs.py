# ============================================================================
# TESTS : Specs contrats configurables (standard / micro)
# ============================================================================

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common import get_contract_specs, resolve_contract_specs
from position import calculate_position_size, calculate_transaction_costs, calculate_trade_pnl


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def config_standard():
    """Config avec contracts en format nouveau, mode standard."""
    return {
        'contracts': {
            'mode': 'standard',
            'standard': {
                'gc_point_value': 100,
                'gc_tick_size': 0.10,
                'gc_tick_value': 10,
                'si_point_value': 5000,
                'si_tick_size': 0.005,
                'si_tick_value': 25,
            },
            'micro': {
                'gc_point_value': 10,
                'gc_tick_size': 0.10,
                'gc_tick_value': 1,
                'si_point_value': 1000,
                'si_tick_size': 0.005,
                'si_tick_value': 5,
            },
        },
        'sizing': {'mode': 'dollar_neutral_beta', 'si_contracts': 1, 'gc_contracts_max': 0},
        'costs': {'commission_per_contract': 4.00, 'slippage_gc_ticks': 1, 'slippage_si_ticks': 1},
    }


@pytest.fixture
def config_micro():
    """Config avec contracts en format nouveau, mode micro."""
    return {
        'contracts': {
            'mode': 'micro',
            'standard': {
                'gc_point_value': 100,
                'gc_tick_size': 0.10,
                'gc_tick_value': 10,
                'si_point_value': 5000,
                'si_tick_size': 0.005,
                'si_tick_value': 25,
            },
            'micro': {
                'gc_point_value': 10,
                'gc_tick_size': 0.10,
                'gc_tick_value': 1,
                'si_point_value': 1000,
                'si_tick_size': 0.005,
                'si_tick_value': 5,
            },
        },
        'sizing': {'mode': 'dollar_neutral_beta', 'si_contracts': 1, 'gc_contracts_max': 0},
        'costs': {'commission_per_contract': 4.00, 'slippage_gc_ticks': 1, 'slippage_si_ticks': 1},
    }


@pytest.fixture
def config_flat_legacy():
    """Config ancien format (flat, sans mode) -- retrocompatibilite."""
    return {
        'contracts': {
            'gc_point_value': 100,
            'gc_tick_size': 0.10,
            'gc_tick_value': 10,
            'si_point_value': 5000,
            'si_tick_size': 0.005,
            'si_tick_value': 25,
        },
        'sizing': {'mode': 'dollar_neutral_beta', 'si_contracts': 1, 'gc_contracts_max': 0},
        'costs': {'commission_per_contract': 4.00, 'slippage_gc_ticks': 1, 'slippage_si_ticks': 1},
    }


@pytest.fixture
def config_no_contracts():
    """Config sans section contracts du tout."""
    return {
        'sizing': {'mode': 'dollar_neutral_beta', 'si_contracts': 1, 'gc_contracts_max': 0},
        'costs': {'commission_per_contract': 4.00, 'slippage_gc_ticks': 1, 'slippage_si_ticks': 1},
    }


# ============================================================================
# TESTS get_contract_specs()
# ============================================================================

class TestGetContractSpecs:
    def test_standard_mode(self, config_standard):
        specs = get_contract_specs(config_standard)
        assert specs['gc_point_value'] == 100
        assert specs['si_point_value'] == 5000
        assert specs['gc_tick_value'] == 10
        assert specs['si_tick_value'] == 25

    def test_micro_mode(self, config_micro):
        specs = get_contract_specs(config_micro)
        assert specs['gc_point_value'] == 10
        assert specs['si_point_value'] == 1000
        assert specs['gc_tick_value'] == 1
        assert specs['si_tick_value'] == 5

    def test_flat_legacy(self, config_flat_legacy):
        specs = get_contract_specs(config_flat_legacy)
        assert specs['gc_point_value'] == 100
        assert specs['si_point_value'] == 5000

    def test_no_contracts_section(self, config_no_contracts):
        specs = get_contract_specs(config_no_contracts)
        assert specs['gc_point_value'] == 100
        assert specs['si_point_value'] == 5000

    def test_invalid_mode_raises(self):
        config = {'contracts': {'mode': 'invalid'}}
        with pytest.raises(ValueError, match="contracts.mode invalide"):
            get_contract_specs(config)

    def test_tick_sizes_same_both_modes(self, config_standard, config_micro):
        std = get_contract_specs(config_standard)
        micro = get_contract_specs(config_micro)
        assert std['gc_tick_size'] == micro['gc_tick_size']
        assert std['si_tick_size'] == micro['si_tick_size']


# ============================================================================
# TESTS resolve_contract_specs()
# ============================================================================

class TestResolveContractSpecs:
    def test_resolve_flattens_config(self, config_standard):
        resolve_contract_specs(config_standard)
        # Apres resolution, config['contracts'] est plat
        assert config_standard['contracts']['gc_point_value'] == 100
        assert 'standard' not in config_standard['contracts']

    def test_resolve_preserves_mode(self, config_micro):
        resolve_contract_specs(config_micro)
        assert config_micro['contracts']['mode'] == 'micro'
        assert config_micro['contracts']['gc_point_value'] == 10


# ============================================================================
# TESTS position sizing avec micro
# ============================================================================

class TestPositionSizingMicro:
    def test_sizing_standard(self, config_standard):
        resolve_contract_specs(config_standard)
        size = calculate_position_size(2800.0, 32.0, 1.0, config_standard)
        assert size['gc_contracts'] >= 1
        assert size['notional_gc'] == 2800.0 * 100

    def test_sizing_micro(self, config_micro):
        resolve_contract_specs(config_micro)
        size = calculate_position_size(2800.0, 32.0, 1.0, config_micro)
        assert size['gc_contracts'] >= 1
        assert size['notional_gc'] == 2800.0 * 10

    def test_sizing_micro_more_contracts(self, config_standard, config_micro):
        """Micro devrait donner plus de contrats GC car le notionnel est plus petit."""
        resolve_contract_specs(config_standard)
        resolve_contract_specs(config_micro)
        size_std = calculate_position_size(2800.0, 32.0, 1.0, config_standard)
        size_micro = calculate_position_size(2800.0, 32.0, 1.0, config_micro)
        # Micro: NotionalSI/NotionalGC = (32*1000)/(2800*10) = 1.14
        # Standard: NotionalSI/NotionalGC = (32*5000)/(2800*100) = 0.57
        # Micro donne ~2x plus de contrats GC (ratio asymetrique)
        assert size_micro['gc_contracts'] >= size_std['gc_contracts']


# ============================================================================
# TESTS PnL avec micro
# ============================================================================

class TestTradePnlMicro:
    def test_pnl_standard(self, config_standard):
        resolve_contract_specs(config_standard)
        pnl = calculate_trade_pnl(1, 2800.0, 32.0, 2799.0, 32.05,
                                   1, 1, config_standard)
        # LONG: GC short: (2800-2799)*100*1 = 100, SI long: (32.05-32)*5000*1 = 250
        assert pnl['pnl_gc'] == 100.0
        assert pnl['pnl_si'] == 250.0

    def test_pnl_micro(self, config_micro):
        resolve_contract_specs(config_micro)
        pnl = calculate_trade_pnl(1, 2800.0, 32.0, 2799.0, 32.05,
                                   1, 1, config_micro)
        # LONG: GC short: (2800-2799)*10*1 = 10, SI long: (32.05-32)*1000*1 = 50
        assert pnl['pnl_gc'] == 10.0
        assert pnl['pnl_si'] == 50.0

    def test_micro_vs_standard_ratio(self, config_standard, config_micro):
        """PnL micro GC = standard/10, PnL micro SI = standard/5."""
        resolve_contract_specs(config_standard)
        resolve_contract_specs(config_micro)
        pnl_std = calculate_trade_pnl(1, 2800.0, 32.0, 2799.0, 32.05,
                                       1, 1, config_standard)
        pnl_micro = calculate_trade_pnl(1, 2800.0, 32.0, 2799.0, 32.05,
                                         1, 1, config_micro)
        assert pnl_micro['pnl_gc'] == pnl_std['pnl_gc'] / 10
        assert pnl_micro['pnl_si'] == pnl_std['pnl_si'] / 5


# ============================================================================
# TESTS slippage avec micro
# ============================================================================

class TestSlippageMicro:
    def test_slippage_standard(self, config_standard):
        resolve_contract_specs(config_standard)
        costs = calculate_transaction_costs(1, 1, config_standard)
        # 1 tick GC: $10 * 1 * 2 = $20, 1 tick SI: $25 * 1 * 2 = $50
        assert costs['slippage_gc'] == 20.0
        assert costs['slippage_si'] == 50.0

    def test_slippage_micro(self, config_micro):
        resolve_contract_specs(config_micro)
        costs = calculate_transaction_costs(1, 1, config_micro)
        # 1 tick MGC: $1 * 1 * 2 = $2, 1 tick SIL: $5 * 1 * 2 = $10
        assert costs['slippage_gc'] == 2.0
        assert costs['slippage_si'] == 10.0

    def test_slippage_ratio(self, config_standard, config_micro):
        """Slippage micro = standard / 10 (GC) et / 5 (SI)."""
        resolve_contract_specs(config_standard)
        resolve_contract_specs(config_micro)
        cost_std = calculate_transaction_costs(1, 1, config_standard)
        cost_micro = calculate_transaction_costs(1, 1, config_micro)
        assert cost_micro['slippage_gc'] == cost_std['slippage_gc'] / 10
        assert cost_micro['slippage_si'] == cost_std['slippage_si'] / 5
