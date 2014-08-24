"""
Filename: stochmatrix.py

Author: Daisuke Oyama

"""
import numpy as np
from scipy import sparse
from scipy.sparse import csgraph


class StochMatrix(np.matrix):

    def __init__(self, P):
        n, m = P.shape

        if n != m:
            raise ValueError('matrix must be square')

        self.P = P
        self.n = n

        self._num_comm_classes = None
        self._comm_classes_proj = None
        self._is_irreducible = None
        self._rec_classes_labels = None

    def _find_comm_classes(self):
        # Directed graph generated by P, represented by sparse.csr_matrix
        digraph_csr = sparse.csr_matrix(self.P > 0, dtype=bool)

        # Find the communication classes (strongly connected components)
        # docs.scipy.org/doc/scipy/reference/sparse.csgraph.html
        self._num_comm_classes, self._comm_classes_proj = \
            csgraph.connected_components(digraph_csr, connection='strong')

        self._is_irreducible = True if self.num_comm_classes == 1 else False

    @property
    def num_comm_classes(self):
        if self._num_comm_classes is None:
            self._find_comm_classes()
        return self._num_comm_classes

    @property
    def comm_classes_proj(self):
        if self._comm_classes_proj is None:
            self._find_comm_classes()
        return self._comm_classes_proj

    @property
    def is_irreducible(self):
        if self._is_irreducible is None:
            self._find_comm_classes()
        return self._is_irreducible

    def _find_rec_classes(self):
        # Directed graph on the quotient set (the set of communication classes)
        # represented by dictionary of sets
        digraph_quo = {i: set() for i in range(self.num_comm_classes)}

        try:
            # `ValueError` raised if `np.where(self.P > 0)` is zero-sized
            edges_iter = np.nditer(np.where(self.P > 0))
        except ValueError:
            edges_iter = ()

        for edge in edges_iter:
            comm_class_from, comm_class_to = \
                self.comm_classes_proj[np.array(edge)]
            if comm_class_from != comm_class_to:
                digraph_quo[comm_class_from].add(comm_class_to)

        self._rec_classes_labels = \
            [i for i, val in digraph_quo.items() if len(val) == 0]

    @property
    def rec_classes_labels(self):
        if self._rec_classes_labels is None:
            self._find_rec_classes()
        return self._rec_classes_labels

    def comm_classes(self):
        if self.is_irreducible:
            return [range(self.n)]
        else:
            return [np.where(self.comm_classes_proj == i)[0].tolist()
                    for i in range(self.num_comm_classes)]

    def rec_classes(self):
        if self.is_irreducible:
            return [range(self.n)]
        else:
            return [np.where(self.comm_classes_proj == i)[0].tolist()
                    for i in self.rec_classes_labels]