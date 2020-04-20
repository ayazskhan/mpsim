"""Defines matrix product state class."""

from typing import List, Optional

import numpy as np
import tensornetwork as tn

from mpsim.gates import hgate, rgate, xgate, cnot, swap
from mpsim.mpsim_cirq.circuits import MPSOperation


class MPS:
    """Matrix Product State (MPS) for simulating (noisy) quantum circuits."""

    def __init__(
            self,
            nqudits: int,
            qudit_dimension: int = 2,
            tensor_prefix: str = "q"
    ) -> None:
        """Initializes an MPS of qudits in the all |0> state.

        The MPS has the following structure (shown for six qudits):

            @ ---- @ ---- @ ---- @ ---- @ ---- @
            |      |      |      |      |      |

        Virtual indices have bond dimension one and physical indices
        have bond dimension equal to the qudit_dimension.

        Args:
            nqudits: Number of qubits in the all zero state.
            qudit_dimension: Dimension of qudits. Default value is 2 (qubits).
            tensor_prefix: Prefix for tensor names.
                The full name is prefix + numerical index, numbered from
                left to right starting with zero.
        """
        if nqudits < 2:
            raise ValueError(
                f"Number of qudits must be greater than 2 but is {nqudits}."
            )

        # Get nodes on the interior
        nodes = [
            tn.Node(
                np.array(
                    [[[1.0]], *[[[0]]] * (qudit_dimension - 1)],
                    dtype=np.complex64
                ),
                name=tensor_prefix + str(x + 1),
            )
            for x in range(nqudits - 2)
        ]

        # Get nodes on the edges
        nodes.insert(
            0,
            tn.Node(
                np.array(
                    [[1.0], *[[0]] * (qudit_dimension - 1)], dtype=np.complex64
                ),
                name=tensor_prefix + str(0),
            ),
        )
        nodes.append(
            tn.Node(
                np.array(
                    [[1.0], *[[0]] * (qudit_dimension - 1)], dtype=np.complex64
                ),
                name=tensor_prefix + str(nqudits - 1),
            )
        )

        # Connect edges between middle nodes
        for i in range(1, nqudits - 2):
            tn.connect(nodes[i].get_edge(2), nodes[i + 1].get_edge(1))

        # Connect end nodes to the adjacent middle nodes
        if nqudits < 3:
            tn.connect(nodes[0].get_edge(1), nodes[1].get_edge(1))
        else:
            tn.connect(nodes[0].get_edge(1), nodes[1].get_edge(1))
            tn.connect(nodes[-1].get_edge(1), nodes[-2].get_edge(2))

        self._nqudits = nqudits
        self._qudit_dimension = qudit_dimension
        self._prefix = tensor_prefix
        self._nodes = nodes
        self._max_bond_dimensions = [
            self._qudit_dimension ** (i + 1) for i in range(self._nqudits // 2)
        ]
        self._max_bond_dimensions += list(reversed(self._max_bond_dimensions))
        if self._nqudits % 2 == 0:
            self._max_bond_dimensions.remove(
                self._qudit_dimension ** (self._nqudits // 2)
            )
        self._infidelities = []  # type: List[float]
        self._fidelities = []  # type: List[float]

    @property
    def nqudits(self) -> int:
        """Returns the number of qudits in the MPS."""
        return self._nqudits

    @property
    def qudit_dimension(self) -> int:
        """Returns the dimension of each qudit in the MPS."""
        return self._qudit_dimension

    def get_bond_dimension_of(self, index: int) -> int:
        """Returns the bond dimension of the right edge of the node
        at the given index.

        Args:
            index: Index of the node.
                The returned bond dimension is that of the right edge
                of the given node.
        """
        if not self.is_valid():
            raise ValueError("MPS is invalid.")
        if index >= self._nqudits:
            raise ValueError(
                f"Index should be less than {self._nqudits} but is {index}."
            )

        left = self.get_node(index, copy=False)
        right = self.get_node(index + 1, copy=False)
        tn.check_connected((left, right))
        edge = tn.get_shared_edges(left, right).pop()
        return edge.dimension

    def get_bond_dimensions(self) -> List[int]:
        """Returns the bond dimensions of the MPS."""
        return [self.get_bond_dimension_of(i) for i in range(self._nqudits - 1)]

    def get_max_bond_dimension_of(self, index: int) -> int:
        """Returns the maximum bond dimension of the right edge
        of the node at the given index.

        Args:
            index: Index of the node.
                The returned bond dimension is that of the right edge
                of the given node.
                Negative indices count backwards from the right of the MPS.
        """
        if index >= self._nqudits:
            raise ValueError(
                f"Index should be less than {self._nqudits} but is {index}."
            )
        return self._max_bond_dimensions[index]

    def get_max_bond_dimensions(self) -> List[int]:
        """Returns the maximum bond dimensions of the MPS."""
        return self._max_bond_dimensions

    def is_valid(self) -> bool:
        """Returns true if the mpslist defines a valid MPS, else False.

        A valid MPS satisfies the following criteria:
            (1) At least two tensors.
            (2) Every tensor has exactly one free (dangling) edge.
            (3) Every tensor has connected edges to its nearest neighbor(s).
        """
        if len(self._nodes) < 2:
            return False

        for (i, tensor) in enumerate(self._nodes):
            # Exterior nodes
            if i == 0 or i == len(self._nodes) - 1:
                if len(tensor.get_all_dangling()) != 1:
                    return False
                if len(tensor.get_all_nondangling()) != 1:
                    return False
            # Interior nodes
            else:
                if len(tensor.get_all_dangling()) != 1:
                    return False
                if len(tensor.get_all_nondangling()) != 2:
                    return False

            if i < len(self._nodes) - 1:
                try:
                    tn.check_connected((self._nodes[i], self._nodes[i + 1]))
                except ValueError:
                    print(f"Nodes at index {i} and {i + 1} are not connected.")
                    return False
        return True

    def get_nodes(self, copy: bool = True) -> List[tn.Node]:
        """Returns """
        if not copy:
            return self._nodes
        nodes_dict, _ = tn.copy(self._nodes)
        return list(nodes_dict.values())

    def get_node(self, i: int, copy: bool = True) -> tn.Node:
        """Returns the ith node in the MPS counting from the left.

        Args:
            i: Index of node to get.
            copy: If true, a copy of the node is returned,
                   else the actual node is returned.
        """
        return self.get_nodes(copy)[i]

    # TODO: Add unit tests for!
    def get_free_edge_of(self, index: int, copy: bool = True) -> tn.Edge:
        """Returns the free (dangling) edge of a node with specified index.
        
        Args:
            index: Specifies the node.
            copy: If True, returns a copy of the edge.
                  If False, returns the actual edge.
        """
        return self.get_node(index, copy).get_all_dangling().pop()

    @property
    def wavefunction(self) -> np.array:
        """Returns the wavefunction of a valid MPS as a (potentially giant)
        vector by contracting all virtual indices.
        """
        if not self.is_valid():
            raise ValueError("MPS is not valid.")

        # Replicate the mps
        nodes = self.get_nodes(copy=True)
        fin = nodes.pop(0)
        for node in nodes:
            fin = tn.contract_between(fin, node)

        # Make sure all edges are free
        if set(fin.get_all_dangling()) != set(fin.get_all_edges()):
            raise ValueError("Invalid MPS.")

        return np.reshape(
            fin.tensor, newshape=(self._qudit_dimension ** self._nqudits))

    def norm(self) -> float:
        """Returns the norm of the MPS computed by contraction."""
        a = self.get_nodes(copy=True)
        b = self.get_nodes(copy=True)
        for n in b:
            n.set_tensor(np.conj(n.tensor))

        for i in range(self._nqudits):
            tn.connect(
                a[i].get_all_dangling().pop(), b[i].get_all_dangling().pop()
            )

        for i in range(self._nqudits - 1):
            # TODO: Optimize by flattening edges
            mid = tn.contract_between(a[i], b[i])
            new = tn.contract_between(mid, a[i + 1])
            a[i + 1] = new

        fin = tn.contract_between(a[-1], b[-1])
        assert len(fin.edges) == 0  # Debug check
        assert np.isclose(np.imag(fin.tensor), 0.0)  # Debug check
        return abs(fin.tensor)

    def apply_one_qubit_gate(self, gate: tn.Node, index: int) -> None:
        """Applies a single qubit gate to a specified node.

        Args:
            gate: Single qubit gate to apply. A tensor with two free indices.
            index: Index of tensor (qubit) in the MPS to apply
                    the single qubit gate to.
        """
        if not self.is_valid():
            raise ValueError("Input mpslist does not define a valid MPS.")

        if index not in range(self._nqudits):
            raise ValueError(
                f"Input tensor index={index} is out of bounds for"
                f" an MPS on {self._nqudits} qubits."
            )

        if (len(gate.get_all_dangling()) != 2
                or len(gate.get_all_nondangling()) != 0):
            raise ValueError(
                "Single qubit gate must have two free edges"
                " and zero connected edges."
            )

        # Connect the MPS and gate edges
        mps_edge = list(self._nodes[index].get_all_dangling())[0]
        gate_edge = gate[0]
        connected = tn.connect(mps_edge, gate_edge)

        # Contract the edge to get the new tensor
        new = tn.contract(connected, name=self._nodes[index].name)
        self._nodes[index] = new

    def apply_one_qubit_gate_to_all(self, gate: tn.Node) -> None:
        """Applies a single qubit gate to all tensors in the MPS.

        Args:
            gate: Single qubit gate to apply. A tensor with two free indices.
        """
        for i in range(self._nqudits):
            self.apply_one_qubit_gate(gate, i)

    def swap_until_adjacent(
            self, left_index: int, right_index: int, **kwargs
    ) -> None:
        """Swaps nodes in the MPS from left to right until the nodes at
        left_index and right_index are adjacent, modifying the MPS in place.
        
        Args:
            left_index: Index of the left-most node in the MPS to swap.
            right_index: Index of the right-most node in the MPS to swap.
        """
        if left_index >= right_index:
            raise ValueError("left_index should be less than right_index.")

        if left_index < 0 or right_index >= self._nqudits:
            raise ValueError("Indices out of range.")

        if left_index == right_index - 1:
            return

        while left_index < right_index - 1:
            print(f"Swapping node {left_index} with node {left_index + 1}")
            self.swap(left_index, left_index + 1, **kwargs)
            left_index += 1

    def apply_two_qubit_gate(
        self, gate: tn.Node, indexA: int, indexB: int, **kwargs
    ) -> None:
        """Applies a two qubit gate to the specified nodes.

        Args:
            gate: Two qubit gate to apply. See Notes for the edge convention.
            indexA: Index of first tensor (qubit) in the mpslist to apply the
                     single qubit gate to.
            indexB: Index of second tensor (qubit) in the mpslist to apply the
                     single qubit gate to.

        Keyword Arguments:
            keep_left_canonical: After performing an SVD on the new node to
                obtain U, S, Vdag, S is grouped with Vdag to form the
                new right tensor. That is, the left tensor is U, and the
                right tensor is S @ Vdag. This keeps the MPS in left canonical
                form if it already was in left canonical form.

                If False, S is grouped with U so that the new left tensor
                 is U @ S and the new right tensor is Vdag.

            maxsvals (int): Number of singular values to keep
                for all two-qubit gates.

            fraction (float): Number of singular values to keep expressed as a
                fraction of the maximum bond dimension.
                Must be between 0 and 1, inclusive.

        Notes:
            Gate edge convention:
                gate edge 0: Connects to tensor at indexA.
                gate edge 1: Connects to tensor at indexB.
                gate edge 2: Becomes free index of new tensor at indexA
                              after contracting.
                gate edge 3: Becomes free index of new tensor at indexB
                              after contracting.
        """
        if not self.is_valid():
            raise ValueError("Input mpslist does not define a valid MPS.")

        if (indexA not in range(self._nqudits)
                or indexB not in range(self.nqudits)):
            raise ValueError(
                f"Input tensor indices={(indexA, indexB)} are out of bounds"
                f" for an MPS on {self._nqudits} qubits."
            )

        if indexA == indexB:
            raise ValueError("Input indices cannot be identical.")

        if abs(indexA - indexB) != 1:
            raise ValueError(
                "Indices must be for adjacent tensors (must differ by one)."
            )

        if (len(gate.get_all_dangling()) != 4
                or len(gate.get_all_nondangling()) != 0):
            raise ValueError(
                "Two qubit gate must have four free edges"
                " and zero connected edges."
            )

        # Connect the MPS tensors to the gate edges
        if indexA < indexB:
            left_index = indexA
            right_index = indexB
        else:
            raise ValueError(f"IndexA must be less than IndexB.")

        _ = tn.connect(
            list(self._nodes[indexA].get_all_dangling())[0], gate.get_edge(0)
        )
        _ = tn.connect(
            list(self._nodes[indexB].get_all_dangling())[0], gate.get_edge(1)
        )

        # Store the free edges of the gate, using the docstring edge convention
        left_gate_edge = gate.get_edge(2)
        right_gate_edge = gate.get_edge(3)

        # Contract the tensors in the MPS
        new_node = tn.contract_between(
            self._nodes[indexA], self._nodes[indexB], name="new_mps_tensor"
        )

        # Flatten the two edges from the MPS node to the gate node
        node_gate_edge = tn.flatten_edges_between(new_node, gate)

        # Contract the flattened edge to get a new single MPS node
        new_node = tn.contract(node_gate_edge, name="new_mps_tensor")

        # Get the left and right connected edges (if any)
        left_connected_edge = None
        right_connected_edge = None
        for connected_edge in new_node.get_all_nondangling():
            if self._prefix in connected_edge.node1.name:
                # Use the "node1" node by default
                index = int(connected_edge.node1.name.split(self._prefix)[-1])
            else:
                # If "node1" is the new_mps_node, use "node2"
                index = int(connected_edge.node2.name.split(self._prefix)[-1])

            # Get the connected edges (if any)
            if index <= left_index:
                left_connected_edge = connected_edge
            else:
                right_connected_edge = connected_edge

        # Get the left and right free edges from the original gate
        left_free_edge = left_gate_edge
        right_free_edge = right_gate_edge

        # Group the left (un)connected and right (un)connected edges
        left_edges = [
            edge for edge in (left_free_edge, left_connected_edge)
            if edge is not None
        ]
        right_edges = [
            edge for edge in (right_free_edge, right_connected_edge)
            if edge is not None
        ]

        # ================================================
        # Do the SVD to split the single MPS node into two
        # ================================================
        # Options for canonicalization + truncation
        if "keep_left_canonical" in kwargs.keys():
            keep_left_canonical = kwargs.get("keep_left_canonical")
        else:
            keep_left_canonical = True

        if "fraction" in kwargs.keys() and "maxsvals" in kwargs.keys():
            raise ValueError(
                "Only one of (fraction, maxsvals) can be provided as kwargs."
            )

        if "fraction" in kwargs.keys():
            fraction = kwargs.get("fraction")
            if not (0 <= fraction <= 1):
                raise ValueError(
                    "Keyword fraction must be between 0 and 1 but is", fraction
                )
            maxsvals = int(
                round(fraction * self.get_max_bond_dimension_of(
                    min(indexA, indexB)
                ))
            )
        else:
            maxsvals = None  # Keeps all singular values

        if "maxsvals" in kwargs.keys():
            maxsvals = int(kwargs.get("maxsvals"))

        u, s, vdag, truncated_svals = tn.split_node_full_svd(
            new_node,
            left_edges=left_edges,
            right_edges=right_edges,
            max_singular_values=maxsvals,
        )

        # Store the truncated infidelities
        self._infidelities.append(
            np.real(sum(np.conj(x) * x for x in truncated_svals))
        )

        # Contract the tensors to keep left or right canonical form
        if keep_left_canonical:
            new_left = u
            new_right = tn.contract_between(s, vdag)
        else:
            new_left = tn.contract_between(u, s)
            new_right = vdag

        # Put the new tensors after applying the gate back into the MPS list
        new_left.name = self._nodes[indexA].name
        new_right.name = self._nodes[indexB].name

        self._nodes[left_index] = new_left
        self._nodes[right_index] = new_right

        self._fidelities.append(self.norm())

    def apply_mps_operation(
            self, mps_operation: MPSOperation, **kwargs
    ) -> None:
        """Applies the MPS Operation to the MPS.

        Args:
            mps_operation: Valid MPS Operation to apply to the MPS.

        Keyword Args:
            See MPS.apply_two_qubit_gate.
        """
        if not mps_operation.is_valid():
            raise ValueError("Input MPS Operation is not valid.")

        if mps_operation.is_single_qudit_operation():
            self.apply_one_qubit_gate(
                mps_operation.node, mps_operation.qudit_indices[0]
            )
        elif mps_operation.is_two_qudit_operation():
            self.apply_two_qubit_gate(
                mps_operation.node, *mps_operation.qudit_indices, **kwargs
            )
        else:
            raise ValueError(
                "Only one-qudit and two-qudit gates are currently supported."
            )

    def apply_all_mps_operations(
            self, mps_operations: List[MPSOperation], **kwargs
    ):
        """Applies the MPS Operation to the MPS.

        Args:
            mps_operations: List of valid MPS Operations to apply to the MPS.

        Keyword Args:
            See MPS.apply_two_qubit_gate.
        """
        for mps_operation in mps_operations:
            self.apply_mps_operation(mps_operation, **kwargs)

    def x(self, index: int) -> None:
        """Applies a NOT (Pauli-X) gate to a qubit specified by the index.

        If index == -1, the gate is applied to all qubits.

        Args:
            index: Index of qubit (tensor) to apply X gate to.
        """
        if index == -1:
            self.apply_one_qubit_gate_to_all(xgate())
        else:
            self.apply_one_qubit_gate(xgate(), index)

    def h(self, index: int) -> None:
        """Applies a Hadamard gate to a qubit specified by the index.

        If index == -1, the gate is applied to all qubits.

        Args:
            index: Index of qubit (tensor) to apply X gate to.
        """
        if index == -1:
            self.apply_one_qubit_gate_to_all(hgate())
        else:
            self.apply_one_qubit_gate(hgate(), index)

    def r(self, index, seed: Optional[int] = None,
          angle_scale: float = 1.0) -> None:
        """Applies a random rotation to the qubit indexed by `index`.

        If index == -1, (different) random rotations are applied to all qubits.
        Args:
            index: Index of tensor to apply rotation to.
            seed: Seed for random number generator.
            angle_scale: Floating point value to scale angles by. Default 1.
        """
        if index == -1:
            for i in range(self._nqudits):
                self.apply_one_qubit_gate(
                    rgate(seed, angle_scale), i,
                )
        else:
            self.apply_one_qubit_gate(rgate(seed, angle_scale), index)

    def cnot(self, a: int, b: int, **kwargs) -> None:
        """Applies a CNOT gate with qubit indexed `a` as control
        and qubit indexed `b` as target.
        """
        self.apply_two_qubit_gate(cnot(), a, b, **kwargs)

    def sweep_cnots_left_to_right(self, **kwargs) -> None:
        """Applies a layer of CNOTs between adjacent qubits
        going from left to right.
        """
        for i in range(0, self._nqudits - 1, 2):
            self.cnot(i, i + 1, keep_left_canonical=True, **kwargs)

    def sweep_cnots_right_to_left(self, **kwargs) -> None:
        """Applies a layer of CNOTs between adjacent qubits
         going from right to left.
         """
        for i in range(self._nqudits - 2, 0, -2):
            self.cnot(i - 1, i, keep_left_canonical=False, **kwargs)

    def swap(self, a: int, b: int, **kwargs) -> None:
        """Applies a SWAP gate between qubits indexed `a` and `b`."""
        self.apply_two_qubit_gate(swap(), a, b, **kwargs)

    def __str__(self):
        return "----".join(str(tensor) for tensor in self._nodes)
