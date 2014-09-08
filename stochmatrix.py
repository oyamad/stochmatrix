"""
Filename: stochmatrix.py

Author: Daisuke Oyama

Tools for dealing with a stochastic matrix.

"""
import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

try:
    xrange
except:  # python3
    xrange = range


class StochMatrix(np.ndarray):
    r"""
    Add structure as a directed graph to a numpy.ndarray of a stochastic
    matrix. In particular, implement methods that find communication
    classes and reccurent classes.

    Parameters
    ----------
    input_array : array_like(float, ndim=2)
        Array representing a stochastic matrix. Must be of shape n x n.

    Attributes
    ----------
    is_irreducible : bool
        Indicate whether the array is an irreducible matrix.

    num_comm_classes : int
        Number of communication classes.

    num_rec_classes : int
        Number of recurrent classes.

    """

    # Subclassing numpy.ndarray
    # docs.scipy.org/doc/numpy/user/basics.subclassing.html
    def __new__(cls, input_array):
        obj = np.asarray(input_array).view(cls)
        ndim = obj.ndim
        if ndim != 2:
            raise ValueError('matrix must be 2-dimensional')
        n, m = obj.shape
        if n != m:
            raise ValueError('matrix must be square')

        obj.n = n

        obj._num_comm_classes = None
        obj._comm_classes_proj = None
        obj._rec_classes_labels = None

        return obj

    def __array_finalize__(self, obj):
        pass

    def _find_comm_classes(self):
        """
        Set ``self._num_comm_classes`` and ``self._comm_classes_proj``
        by calling ``scipy.sparse.csgraph.connected_components``:
        * docs.scipy.org/doc/scipy/reference/sparse.csgraph.html
        * github.com/scipy/scipy/blob/master/scipy/sparse/csgraph/_traversal.pyx

        ``self._comm_classes_proj`` is a list of length `n` that assigns
        to each index the label of the communication class to which it belongs.

        """
        # Directed graph generated by P, represented by sparse.csr_matrix
        digraph_csr = sparse.csr_matrix(self > 0, dtype=bool)

        # Find the communication classes (strongly connected components)
        self._num_comm_classes, self._comm_classes_proj = \
            csgraph.connected_components(digraph_csr, connection='strong')

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
        return (self.num_comm_classes == 1)

    def _find_rec_classes(self):
        """
        Set self._rec_classes_labels, which is a list containing the labels of
        the recurrent communication classes.

        """
        # Directed graph on the quotient set (the set of communication classes)
        # represented by dictionary of sets
        digraph_quo = {k: set() for k in range(self.num_comm_classes)}

        try:
            # ``ValueError`` raised if ``np.where(self > 0)`` is zero-sized
            edges_iter = np.nditer(np.where(self > 0))
        except ValueError:
            edges_iter = ()

        comm_classes_proj = self.comm_classes_proj
        for state_from, state_to in edges_iter:
            comm_class_from, comm_class_to = \
                comm_classes_proj[state_from], comm_classes_proj[state_to]
            if comm_class_from != comm_class_to:
                digraph_quo[comm_class_from].add(comm_class_to)

        # A recurrent class is a communication class such that none of
        # its members communicates with states in other classes
        self._rec_classes_labels = \
            [k for k, val in digraph_quo.items() if len(val) == 0]

    @property
    def rec_classes_labels(self):
        if self._rec_classes_labels is None:
            self._find_rec_classes()
        return self._rec_classes_labels

    @property
    def num_rec_classes(self):
        return len(self.rec_classes_labels)

    def comm_classes(self):
        r"""
        Return the communication classes (strongly connected components).

        Returns
        -------
        list(list(int))
            List of lists containing the communication classes

        """
        if self.is_irreducible:
            return [list(range(self.n))]
        else:
            return [np.where(self.comm_classes_proj == k)[0].tolist()
                    for k in range(self.num_comm_classes)]

    def rec_classes(self):
        r"""
        Return the recurrent classes (closed communication classes).

        Returns
        -------
        list(list(int))
            List of lists containing the recurrent classes

        """
        if self.is_irreducible:
            return [list(range(self.n))]
        else:
            return [np.where(self.comm_classes_proj == k)[0].tolist()
                    for k in self.rec_classes_labels]

    def __repr__(self):
        s = repr(self.__array__()).replace('array', 'StochMatrix')
        # From defmatrix.py in NumPy:
        # now, 'StochMatrix' has 11 letters, and 'array' 5, so the columns don't
        # line up anymore. We need to add 6 spaces.
        l = s.splitlines()
        for i in range(1, len(l)):
            if l[i]:
                l[i] = ' ' * 6 + l[i]
        return '\n'.join(l)


def stationary_dists(P):
    r"""
    This routine computes the stationary distributions of a stochastic
    matrix `P`.

    Parameters
    ----------
    P : numpy.ndarray or StochMatrix
        Stochastic matrix. Must be of shape n x n.

    Returns
    -------
    stationary_dists : numpy.ndarray(float, ndim=2)
        Array containing the stationary distributions of `P` as its rows.

    """
    try:
        is_irreducible = P.is_irreducible  # Succeeds if P is a StochMatrix
    except:
        P = StochMatrix(P)
        is_irreducible = P.is_irreducible

    n = P.shape[0]

    if is_irreducible:
        stationary_dists = gth_solve(P).reshape(1, n)
    else:
        rec_classes = P.rec_classes()
        stationary_dists = np.zeros((len(rec_classes), n))
        for i, rec_class in enumerate(rec_classes):
            stationary_dists[i, rec_class] = \
                gth_solve(P[rec_class, :][:, rec_class])

    return stationary_dists


# From https://github.com/oyamad/numpy_eigen_markov
def gth_solve(A, overwrite=False):
    r"""
    This routine computes the stationary distribution of an irreducible
    stochastic matrix `A`.

    More generally, given a Metzler matrix (square matrix whose
    off-diagonal entries are all nonnegative) `A`, this routine solves
    for a nonzero solution `x` to `x (A - D) = 0`, where `D` is the
    diagonal matrix for which the rows of `A - D` sum to zero (i.e.,
    :math:`D_{ii} = \sum_j A_{ij}` for all :math:`i`). One (and only
    one, up to normalization) nonzero solution exists corresponding to
    each reccurent class of `A`, and in particular, if `A` is
    irreducible, in which case there is a unique solution; where there
    are more than one, the routine returns the solution that involves
    the first index `i` such that no path connects `i` to any index
    larger than `i`. The solution is normalized so that its 1-norm
    equals one. This routine implements the Grassmann-Taksar-Heyman
    (GTH) algorithm, a numerically stable variant of Gaussian
    elimination, where only the off-diagonal entries of `A` are used as
    the input data.

    Parameters
    ----------
    A : array_like(float, ndim=2)
        Stochastic matrix. Must be of shape n x n.
    overwrite : bool, optional(default=False)
        Whether to overwrite `A`; may improve performance.

    Returns
    -------
    x : numpy.ndarray(float, ndim=1)
        Stationary distribution of `A`.

    """
    A1 = np.array(A, copy=not overwrite)

    if len(A1.shape) != 2 or A1.shape[0] != A1.shape[1]:
        raise ValueError('matrix must be square')

    n = A1.shape[0]

    x = np.zeros(n)

    # === Reduction === #
    for i in xrange(n-1):
        scale = np.sum(A1[i, i+1:n])
        if scale <= 0:
            # There is one (and only one) recurrent class contained in
            # {0, ..., i};
            # compute the solution associated with that recurrent class.
            n = i+1
            break
        A1[i+1:n, i] /= scale

        A1[i+1:n, i+1:n] += np.dot(A1[i+1:n, i:i+1], A1[i:i+1, i+1:n])

    # === Backward substitution === #
    x[n-1] = 1
    for i in xrange(n-2, -1, -1):
        x[i] = np.sum((x[j] * A1[j, i] for j in xrange(i+1, n)))

    # === Normalization === #
    x /= np.sum(x)

    return x
