# ============================================================================
# TEST_RUN_HELPERS.PY - Tests des fonctions utilitaires de run_helpers.py
# ============================================================================
#
# Tests de count_exit_reasons(), check_csv_resumption(), save_batch_csv().
# Utilise tmp_path pour les tests d'I/O fichier.
#
# ============================================================================

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from run_helpers import count_exit_reasons, check_csv_resumption, save_batch_csv


# ============================================================================
# TESTS count_exit_reasons()
# ============================================================================

class TestCountExitReasons:
    """Tests de count_exit_reasons()."""

    def test_basic_counts(self):
        """Compte les 4 types de sortie."""
        df = pd.DataFrame({
            'Exit_Reason': ['TP_ZSCORE', 'TP_ZSCORE', 'SL_DOLLAR', 'TP_DOLLAR']
        })
        result = count_exit_reasons(df)
        assert result['tp_zscore'] == 2
        assert result['tp_dollar'] == 1
        assert result['sl_dollar'] == 1
        assert result['sl_zscore'] == 0

    def test_empty_dataframe(self):
        """DataFrame vide retourne des compteurs a zero."""
        df = pd.DataFrame(columns=['Exit_Reason'])
        result = count_exit_reasons(df)
        assert result == {"tp_zscore": 0, "tp_dollar": 0, "sl_zscore": 0, "sl_dollar": 0}


# ============================================================================
# TESTS check_csv_resumption()
# ============================================================================

class TestCheckCsvResumption:
    """Tests de check_csv_resumption()."""

    def test_existing_csv(self, tmp_path):
        """CSV existant retourne les labels deja traites."""
        csv_path = tmp_path / "results.csv"
        df = pd.DataFrame({'label': ['config_A', 'config_B', 'config_C']})
        df.to_csv(csv_path, index=False, sep=";")

        completed = check_csv_resumption(str(csv_path))
        assert completed == {'config_A', 'config_B', 'config_C'}

    def test_missing_file(self, tmp_path):
        """Fichier absent retourne un set vide."""
        csv_path = tmp_path / "does_not_exist.csv"
        completed = check_csv_resumption(str(csv_path))
        assert completed == set()


# ============================================================================
# TESTS save_batch_csv()
# ============================================================================

class TestSaveBatchCsv:
    """Tests de save_batch_csv()."""

    def test_create_new_csv(self, tmp_path):
        """Cree un nouveau CSV si inexistant."""
        output_path = tmp_path / "output" / "batch.csv"
        batch = [{"label": "A", "pnl": 100}, {"label": "B", "pnl": 200}]
        n = save_batch_csv(batch, str(output_path))
        assert n == 2
        assert output_path.exists()
        df = pd.read_csv(output_path, sep=";")
        assert len(df) == 2
        assert list(df['label']) == ['A', 'B']

    def test_append_to_existing(self, tmp_path):
        """Ajoute au CSV existant (mode append)."""
        output_path = tmp_path / "batch.csv"
        save_batch_csv([{"label": "A", "pnl": 100}], str(output_path))
        save_batch_csv([{"label": "B", "pnl": 200}], str(output_path))
        df = pd.read_csv(output_path, sep=";")
        assert len(df) == 2
        assert set(df['label']) == {'A', 'B'}
