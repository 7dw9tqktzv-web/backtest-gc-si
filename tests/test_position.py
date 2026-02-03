# ============================================================================
# TEST_POSITION.PY - Tests pour le module position.py
# ============================================================================
#
# Tests des fonctions de sizing et calcul de PnL :
# - calculate_position_size()
# - calculate_transaction_costs()
# - calculate_trade_pnl()
#
# ============================================================================

import pytest
import numpy as np
import sys
from pathlib import Path

# Ajouter src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from position import (
    calculate_position_size,
    calculate_transaction_costs,
    calculate_trade_pnl,
)


class TestCalculatePositionSize:
    """Tests de calculate_position_size()."""

    def test_output_keys(self, sample_config):
        """Verifie que toutes les cles sont presentes."""
        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.0,
            config=sample_config
        )

        expected_keys = [
            'si_contracts', 'gc_contracts', 'gc_contracts_raw',
            'notional_gc', 'notional_si',
            'notional_gc_total', 'notional_si_total',
            'imbalance_pct'
        ]

        for key in expected_keys:
            assert key in result

    def test_dollar_neutral_beta_mode(self, sample_config):
        """Test du mode dollar_neutral_beta."""
        sample_config['sizing']['mode'] = 'dollar_neutral_beta'

        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.0,
            config=sample_config
        )

        # GC_contracts = (SI_notional / GC_notional) * Beta * SI_contracts
        # SI_notional = 32 * 5000 = 160,000
        # GC_notional = 2800 * 100 = 280,000
        # GC_raw = (160000 / 280000) * 1.0 * 1 = 0.571
        # GC_contracts = round(0.571) = 1

        assert result['si_contracts'] == 1
        assert result['gc_contracts'] >= 1  # Minimum 1
        assert np.isclose(result['gc_contracts_raw'], 160000/280000, atol=0.01)

    def test_minimum_one_gc_contract(self, sample_config):
        """GC contracts minimum = 1."""
        sample_config['sizing']['mode'] = 'dollar_neutral_beta'

        # Avec un beta tres petit, GC_raw serait < 1
        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=0.1,  # Tres petit
            config=sample_config
        )

        # Meme si le calcul donne < 1, on prend 1
        assert result['gc_contracts'] >= 1

    def test_gc_contracts_max_cap(self, sample_config):
        """Cap sur GC contracts si configure."""
        sample_config['sizing']['mode'] = 'dollar_neutral_beta'
        sample_config['sizing']['gc_contracts_max'] = 3

        # Avec un beta grand, on aurait plus de 3 GC
        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=10.0,  # Tres grand
            config=sample_config
        )

        # Devrait etre cappe a 3
        assert result['gc_contracts'] <= 3

    def test_fixed_mode(self, sample_config):
        """Test du mode fixed."""
        sample_config['sizing']['mode'] = 'fixed'
        sample_config['sizing']['si_contracts'] = 2

        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.5,  # Ignore en mode fixed
            config=sample_config
        )

        # En mode fixed, GC = SI
        assert result['gc_contracts'] == result['si_contracts'] == 2

    def test_dollar_neutral_mode(self, sample_config):
        """Test du mode dollar_neutral (sans beta)."""
        sample_config['sizing']['mode'] = 'dollar_neutral'

        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.5,  # Ignore en mode dollar_neutral
            config=sample_config
        )

        # GC_contracts = (SI_notional / GC_notional) * SI_contracts
        # Sans ajustement beta
        expected_gc_raw = (32 * 5000) / (2800 * 100)
        assert np.isclose(result['gc_contracts_raw'], expected_gc_raw, atol=0.01)

    def test_invalid_mode_raises_error(self, sample_config):
        """Mode inconnu leve une erreur."""
        sample_config['sizing']['mode'] = 'invalid_mode'

        with pytest.raises(ValueError) as excinfo:
            calculate_position_size(
                gc_price=2800.0,
                si_price=32.0,
                beta=1.0,
                config=sample_config
            )

        assert "Mode de sizing inconnu" in str(excinfo.value)

    def test_notional_calculations(self, sample_config):
        """Verifie les calculs de notionnel."""
        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.0,
            config=sample_config
        )

        # Notional par contrat
        expected_gc_notional = 2800.0 * 100  # 280,000
        expected_si_notional = 32.0 * 5000   # 160,000

        assert result['notional_gc'] == expected_gc_notional
        assert result['notional_si'] == expected_si_notional

    def test_imbalance_calculation(self, sample_config):
        """Verifie le calcul du desequilibre."""
        sample_config['sizing']['mode'] = 'fixed'  # 1 GC pour 1 SI

        result = calculate_position_size(
            gc_price=2800.0,
            si_price=32.0,
            beta=1.0,
            config=sample_config
        )

        # GC total = 1 * 2800 * 100 = 280,000
        # SI total = 1 * 32 * 5000 = 160,000
        # Moyenne = (280000 + 160000) / 2 = 220,000
        # Imbalance = |280000 - 160000| / 220000 * 100 = 54.5%
        expected_imbalance = abs(280000 - 160000) / 220000 * 100

        assert np.isclose(result['imbalance_pct'], expected_imbalance, atol=0.1)


class TestCalculateTransactionCosts:
    """Tests de calculate_transaction_costs()."""

    def test_output_keys(self, sample_config):
        """Verifie que toutes les cles sont presentes."""
        result = calculate_transaction_costs(
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        expected_keys = [
            'commission_gc', 'commission_si', 'commission_total',
            'slippage_gc', 'slippage_si', 'slippage_total',
            'total_cost'
        ]

        for key in expected_keys:
            assert key in result

    def test_commission_calculation(self, sample_config):
        """Verifie le calcul des commissions."""
        sample_config['costs']['commission_per_contract'] = 4.00

        result = calculate_transaction_costs(
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # Commission = $4 par contrat (round-trip)
        # GC: 6 * 4 = 24
        # SI: 1 * 4 = 4
        # Total: 28
        assert result['commission_gc'] == 24.0
        assert result['commission_si'] == 4.0
        assert result['commission_total'] == 28.0

    def test_slippage_calculation(self, sample_config):
        """Verifie le calcul du slippage."""
        sample_config['costs']['slippage_gc_ticks'] = 1
        sample_config['costs']['slippage_si_ticks'] = 1

        result = calculate_transaction_costs(
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # Slippage = ticks * tick_value * contracts * 2 (entree + sortie)
        # GC: 1 * 10 * 6 * 2 = 120
        # SI: 1 * 25 * 1 * 2 = 50
        # Total: 170
        assert result['slippage_gc'] == 120.0
        assert result['slippage_si'] == 50.0
        assert result['slippage_total'] == 170.0

    def test_total_cost(self, sample_config):
        """Verifie le cout total."""
        result = calculate_transaction_costs(
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # Total = commission + slippage
        expected_total = result['commission_total'] + result['slippage_total']
        assert result['total_cost'] == expected_total

    def test_two_ticks_slippage(self, sample_config):
        """Test avec 2 ticks de slippage."""
        sample_config['costs']['slippage_gc_ticks'] = 2
        sample_config['costs']['slippage_si_ticks'] = 2

        result = calculate_transaction_costs(
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # Slippage GC: 2 * 10 * 6 * 2 = 240
        # Slippage SI: 2 * 25 * 1 * 2 = 100
        assert result['slippage_gc'] == 240.0
        assert result['slippage_si'] == 100.0


class TestCalculateTradePnl:
    """Tests de calculate_trade_pnl()."""

    def test_output_keys(self, sample_config):
        """Verifie que toutes les cles sont presentes."""
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2800.0,
            exit_si=32.0,
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        expected_keys = ['pnl_gc', 'pnl_si', 'pnl_gross', 'costs', 'pnl_net']

        for key in expected_keys:
            assert key in result

    def test_long_spread_profit(self, sample_config):
        """PnL positif pour LONG spread gagnant."""
        # LONG spread = long SI, short GC
        # Profit si SI monte et/ou GC baisse
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2795.0,  # GC baisse de 5 points
            exit_si=32.05,   # SI monte de 0.05
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # PnL GC = (entry - exit) * 100 * 6 = (2800 - 2795) * 100 * 6 = 3000
        # PnL SI = (exit - entry) * 5000 * 1 = (32.05 - 32.0) * 5000 = 250
        # Gross = 3250
        assert result['pnl_gc'] == 3000.0
        assert result['pnl_si'] == 250.0
        assert result['pnl_gross'] == 3250.0
        assert result['pnl_net'] < result['pnl_gross']  # Apres couts

    def test_long_spread_loss(self, sample_config):
        """PnL negatif pour LONG spread perdant."""
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2810.0,  # GC monte de 10 points
            exit_si=31.95,   # SI baisse de 0.05
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # PnL GC = (2800 - 2810) * 100 * 6 = -6000
        # PnL SI = (31.95 - 32.0) * 5000 = -250
        # Gross = -6250
        assert result['pnl_gc'] == -6000.0
        assert result['pnl_si'] == -250.0
        assert result['pnl_gross'] == -6250.0

    def test_short_spread_profit(self, sample_config):
        """PnL positif pour SHORT spread gagnant."""
        # SHORT spread = short SI, long GC
        # Profit si SI baisse et/ou GC monte
        result = calculate_trade_pnl(
            direction=-1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2810.0,  # GC monte de 10 points
            exit_si=31.95,   # SI baisse de 0.05
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # PnL GC = (exit - entry) * 100 * 6 = (2810 - 2800) * 100 * 6 = 6000
        # PnL SI = (entry - exit) * 5000 * 1 = (32.0 - 31.95) * 5000 = 250
        # Gross = 6250
        assert result['pnl_gc'] == 6000.0
        assert result['pnl_si'] == 250.0
        assert result['pnl_gross'] == 6250.0

    def test_short_spread_loss(self, sample_config):
        """PnL negatif pour SHORT spread perdant."""
        result = calculate_trade_pnl(
            direction=-1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2795.0,  # GC baisse -> perte (long GC)
            exit_si=32.05,   # SI monte -> perte (short SI)
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        # PnL GC = (2795 - 2800) * 100 * 6 = -3000
        # PnL SI = (32.0 - 32.05) * 5000 = -250
        # Gross = -3250
        assert result['pnl_gc'] == -3000.0
        assert result['pnl_si'] == -250.0
        assert result['pnl_gross'] == -3250.0

    def test_zero_pnl_no_move(self, sample_config):
        """PnL gross = 0 si aucun mouvement de prix."""
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2800.0,  # Inchange
            exit_si=32.0,    # Inchange
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        assert result['pnl_gross'] == 0.0
        # PnL net = -couts
        assert result['pnl_net'] < 0

    def test_invalid_direction_raises_error(self, sample_config):
        """Direction invalide leve une erreur."""
        with pytest.raises(ValueError) as excinfo:
            calculate_trade_pnl(
                direction=0,  # Invalide
                entry_gc=2800.0,
                entry_si=32.0,
                exit_gc=2800.0,
                exit_si=32.0,
                gc_contracts=6,
                si_contracts=1,
                config=sample_config
            )

        assert "Direction invalide" in str(excinfo.value)

    def test_pnl_net_includes_costs(self, sample_config):
        """PnL net = PnL gross - couts."""
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2795.0,
            exit_si=32.05,
            gc_contracts=6,
            si_contracts=1,
            config=sample_config
        )

        expected_net = result['pnl_gross'] - result['costs']
        assert result['pnl_net'] == expected_net

    def test_costs_match_transaction_costs(self, sample_config):
        """Les couts dans trade_pnl correspondent a transaction_costs."""
        gc_contracts = 6
        si_contracts = 1

        trade_result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2800.0,
            exit_si=32.0,
            gc_contracts=gc_contracts,
            si_contracts=si_contracts,
            config=sample_config
        )

        costs_result = calculate_transaction_costs(
            gc_contracts=gc_contracts,
            si_contracts=si_contracts,
            config=sample_config
        )

        assert trade_result['costs'] == costs_result['total_cost']


class TestRealWorldScenarios:
    """Tests avec des scenarios realistes."""

    def test_typical_winning_trade(self, sample_config):
        """Trade gagnant typique avec sizing realiste."""
        # Prix realistes
        gc_price = 2850.0
        si_price = 32.50
        beta = 1.05

        # Calculer le sizing
        size = calculate_position_size(gc_price, si_price, beta, sample_config)

        # Trade LONG avec mouvement favorable
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=gc_price,
            entry_si=si_price,
            exit_gc=gc_price - 3.0,  # GC baisse de 3 points
            exit_si=si_price + 0.02,  # SI monte de 2 cents
            gc_contracts=size['gc_contracts'],
            si_contracts=size['si_contracts'],
            config=sample_config
        )

        # Devrait etre profitable
        assert result['pnl_gross'] > 0

    def test_typical_losing_trade(self, sample_config):
        """Trade perdant typique."""
        gc_price = 2850.0
        si_price = 32.50
        beta = 1.05

        size = calculate_position_size(gc_price, si_price, beta, sample_config)

        # Trade LONG avec mouvement defavorable
        result = calculate_trade_pnl(
            direction=1,
            entry_gc=gc_price,
            entry_si=si_price,
            exit_gc=gc_price + 5.0,  # GC monte de 5 points
            exit_si=si_price - 0.03,  # SI baisse de 3 cents
            gc_contracts=size['gc_contracts'],
            si_contracts=size['si_contracts'],
            config=sample_config
        )

        # Devrait etre perdant
        assert result['pnl_gross'] < 0
        assert result['pnl_net'] < result['pnl_gross']

    def test_breakeven_requires_positive_gross(self, sample_config):
        """Pour etre breakeven net, il faut un PnL gross positif."""
        gc_contracts = 6
        si_contracts = 1

        # Calculer les couts
        costs = calculate_transaction_costs(gc_contracts, si_contracts, sample_config)

        # Pour breakeven net, il faut pnl_gross = costs
        # Avec les prix par defaut, calculer le mouvement necessaire

        # Exemple: mouvement GC necessaire pour couvrir les couts
        # pnl_gc = delta_gc * 100 * 6
        # Si pnl_gc = costs['total_cost'], alors:
        # delta_gc = costs['total_cost'] / (100 * 6)
        delta_gc = costs['total_cost'] / (100 * gc_contracts)

        result = calculate_trade_pnl(
            direction=1,
            entry_gc=2800.0,
            entry_si=32.0,
            exit_gc=2800.0 - delta_gc,  # GC baisse exactement du montant necessaire
            exit_si=32.0,
            gc_contracts=gc_contracts,
            si_contracts=si_contracts,
            config=sample_config
        )

        # PnL net devrait etre proche de 0
        assert np.isclose(result['pnl_net'], 0, atol=0.1)
