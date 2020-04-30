"""Unit tests for gates."""

import numpy as np
import pytest

from mpsim.gates import computational_basis_projector


def test_qubit_pi0_projector():
    """Tests correctness for |0><0| on a qubit."""
    pi0 = computational_basis_projector(state=0)
    correct_tensor = np.array([[1., 0.], [0., 0.]])
    assert np.array_equal(pi0.tensor, correct_tensor)
    assert pi0.__str__() == "|0><0|"


def test_qubit_pi1_projector():
    """Tests correctness for |0><0| on a qubit."""
    pi1 = computational_basis_projector(state=1)
    correct_tensor = np.array([[0., 0.], [0., 1.]])
    assert np.array_equal(pi1.tensor, correct_tensor)
    assert pi1.__str__() == "|1><1|"


def test_invalid_projectors():
    """Tests exceptions are raised for invalid projectors."""
    # State must be positive
    with pytest.raises(ValueError):
        computational_basis_projector(state=-1)

    # Dimension must be positive
    with pytest.raises(ValueError):
        computational_basis_projector(state=2, dim=-1)

    # State must be less than dimension
    with pytest.raises(ValueError):
        computational_basis_projector(state=10, dim=8)


def test_qutrit_projectors():
    """Tests correctness for projectors on qutrits."""
    dim = 3
    for state in (0, 1, 2):
        projector = computational_basis_projector(state, dim)
        correct_tensor = np.zeros((dim, dim))
        correct_tensor[state, state] = 1.
        assert np.array_equal(projector.tensor, correct_tensor)
        assert projector.__str__() == f"|{state}><{state}|"
