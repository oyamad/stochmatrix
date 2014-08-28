"""
Filename: stochmatrix.py

Author: Daisuke Oyama

"""
import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

try:
    xrange
except:  # python3
    xrange = range


def mc_compute_stationary(P):
    r"""
    This function computes the stationary distributions of P.

    Parameters
    ----------
    P : instance of StochMatrix
        Stochastic matrix. Must be of shape n x n.

    Returns
    -------
    numpy.ndarray(float, ndim=2)
        Array that contains the stationary distributions of P
        as its rows.
    """
    n = P.shape[0]

    if P.is_irreducible:
        stationary_dists_list = stoch_eig(P).reshape(1, n)
    else:
        rec_classes = P.rec_classes()
        stationary_dists_list = np.zeros((len(rec_classes), n))
        for i, rec_class in enumerate(rec_classes):
            stationary_dists_list[i, rec_class] = \
                stoch_eig(P[rec_class, :][:, rec_class])

    return stationary_dists_list


class StochMatrix(np.matrix):
    r"""
    Add structure as a directed graph to numpy.matrix.

    Parameters
    ----------
    P : array_like(float, ndim=2)
        Stochastic matrix. Must be of shape n x n.

    Attributes
    ----------
    is_irreducible : bool
        Indicate whether P is an irreducible matrix.

    Methods
    -------
    comm_classes
    rec_classes

    """

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
        """
        Returns the communication classes (strongly connected components) of P

        Returns
        -------
        list(list(int))
            List of lists that contains the communication classes

        """
        if self.is_irreducible:
            return [range(self.n)]
        else:
            return [np.where(self.comm_classes_proj == i)[0].tolist()
                    for i in range(self.num_comm_classes)]

    def rec_classes(self):
        """
        Returns the recurrent classes (closed ommunication classes) of P

        Returns
        -------
        list(list(int))
            List of lists that contains the recurrent classes

        """
        if self.is_irreducible:
            return [range(self.n)]
        else:
            return [np.where(self.comm_classes_proj == i)[0].tolist()
                    for i in self.rec_classes_labels]


# From https://github.com/oyamad/numpy_eigen_markov

def stoch_eig(P, overwrite=False):
    r"""
    This routine returns the stochastic eigenvector (stationary
    probability distribution vector) of an irreducible stochastic matrix
    *P*, i.e., the solution to `x P = x`, normalized so that its 1-norm
    equals one. Internally, the routine passes the input to the
    ``gth_solve`` routine.

    Parameters
    ----------
    P : array_like(float, ndim=2)
        Stochastic matrix. Must be of shape n x n.
    overwrite : bool, optional(default=False)
        Whether to overwrite P; may improve performance.

    Returns
    -------
    x : numpy.ndarray(float, ndim=1)
        Stochastic eigenvalue (stationary distribution) of P, i.e., the
        solution to x P = x, normalized so that its 1-norm equals one.

    Examples
    --------
    >>> import numpy as np
    >>> from eigen_markov import stoch_eig
    >>> P = np.array([[0.9, 0.075, 0.025], [0.15, 0.8, 0.05], [0.25, 0.25, 0.5]])
    >>> x = stoch_eig(P)
    >>> print x
    [ 0.625   0.3125  0.0625]
    >>> print np.dot(x, P)
    [ 0.625   0.3125  0.0625]

    """
    # In fact, stoch_eig, which for the user is a routine to solve
    # x P = x, or x (P - I) = 0, is just another name of the function
    # gth_solve, which solves x A = 0, where the GTH algorithm,
    # the algorithm used there, does not use the actual values of
    # the diagonals of A, under the assumption that
    # A_{ii} = \sum_{j \neq i} A_{ij}, and therefore,
    # gth_solve(P-I) = gth_solve(P), so that it is irrelevant whether to
    # pass P or P - I to gth_solve.
    return gth_solve(P, overwrite=overwrite)


def gth_solve(A, overwrite=False):
    r"""
    This routine computes a nontrivial solution of a linear equation
    system of the form `x A = 0`, where *A* is an irreducible transition
    rate matrix, by using the Grassmann-Taksar-Heyman (GTH) algorithm, a
    variant of Gaussian elimination. The solution is normalized so that
    its 1-norm equals one.

    Parameters
    ----------
    A : array_like(float, ndim=2)
        Transition rate matrix. Must be of shape n x n.
    overwrite : bool, optional(default=False)
        Whether to overwrite A; may improve performance.

    Returns
    -------
    x : numpy.ndarray(float, ndim=1)
        Non-zero solution to x A = 0, normalized so that its 1-norm
        equals one.

    Examples
    --------
    >>> import numpy as np
    >>> from eigen_markov import gth_solve
    >>> A = np.array([[-0.1, 0.075, 0.025], [0.15, -0.2, 0.05], [0.25, 0.25, -0.5]])
    >>> x = gth_solve(A)
    >>> print x
    [ 0.625   0.3125  0.0625]
    >>> print np.dot(x, A)
    [ 0.  0.  0.]

    """
    A1 = np.array(A, copy=not overwrite)

    n, m = A1.shape

    if n != m:
        raise ValueError('matrix must be square')

    x = np.zeros(n)

    # === Reduction === #
    for i in xrange(n-1):
        scale = np.sum(A1[i, i+1:n])
        if scale <= 0:
            # Only consider the leading principal minor of size i+1,
            # which is irreducible
            n = i+1
            break
        A1[i+1:n, i] /= scale

        for j in xrange(i+1, n):
            A1[i+1:n, j] += A1[i, j] * A1[i+1:n, i]

    # === Backward substitution === #
    x[n-1] = 1
    for i in xrange(n-2, -1, -1):
        x[i] = np.sum((x[j] * A1[j, i] for j in xrange(i+1, n)))

    # === Normalization === #
    x /= np.sum(x)

    return x
