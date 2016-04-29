""" This module serves as a wrapper for the two alternative criterion functions.
"""

# standard library
from scipy.optimize import fmin_powell
from scipy.optimize import fmin_bfgs

import numpy as np

import time
import os

# project library
from respy.python.estimate.estimate_auxiliary import dist_optim_paras
from respy.python.estimate.estimate_python import pyth_criterion
from respy.python.shared.shared_auxiliary import HUGE_FLOAT
from respy.fortran.f2py_library import f2py_criterion


class OptimizationClass(object):
    """ This class manages all about the optimization of the criterion
    function. It provides a unified interface for a host of alternative
    optimization algorithms.
    """

    def __init__(self):

        self.attr = dict()

        # constitutive arguments
        self.attr['optimizer_options'] = None

        self.attr['optimizer_used'] = None

        self.attr['file_opt'] = None

        self.attr['version'] = None

        self.attr['maxiter'] = None

        self.attr['x_info'] = None

        self.attr['args'] = None

        # status attributes
        self.attr['value_steps'] = HUGE_FLOAT

        self.attr['value_start'] = HUGE_FLOAT

        self.attr['value_curre'] = HUGE_FLOAT

        self.attr['paras_steps'] = None

        self.attr['paras_curre'] = None

        self.attr['paras_start'] = None

        self.attr['is_locked'] = False

        self.attr['is_first'] = True

        self.attr['num_steps'] = 0

        self.attr['num_evals'] = 0

    def set_attr(self, key, value):
        """ Set attributes.
        """
        # Antibugging
        assert (not self.attr['is_locked'])
        assert self._check_key(key)

        # Finishing
        self.attr[key] = value

    def optimize(self, x0):
        """ Optimize criterion function.
        """
        # Distribute class attributes
        optimizer_used = self.attr['optimizer_used']

        maxiter = self.attr['maxiter']

        args = self.attr['args']

        # Special case where just an evaluation at the starting values is
        # requested is accounted for. Note, that the relevant value of the
        # criterion function is always the one indicated by the class
        # attribute and not the value returned by the optimization algorithm.
        if maxiter == 0:
            crit_val = self.crit_func(x0, *args)

            rslt = dict()
            rslt['x'] = x0
            rslt['fun'] = crit_val
            rslt['success'] = True
            rslt['message'] = 'Evaluation of criterion function at starting values.'

        else:
            if optimizer_used == 'SCIPY-BFGS':
                gtol, epsilon = self._options_distribute(optimizer_used)
                rslt_opt = fmin_bfgs(self.crit_func, x0, args=args, gtol=gtol,
                    epsilon=epsilon, maxiter=maxiter, full_output=True,
                    disp=False)

            elif optimizer_used == 'SCIPY-POWELL':
                xtol, ftol, maxfun = self._options_distribute(optimizer_used)
                rslt_opt = fmin_powell(self.crit_func, x0, args, xtol, ftol,
                    maxiter, maxfun, full_output=True, disp=0)

            else:
                raise NotImplementedError

            # Process results to a common dictionary.
            rslt = self._results_distribute(rslt_opt, optimizer_used)

        # Finalizing results
        self._logging_final(rslt)

        # Finishing
        return rslt['x'], rslt['fun']

    def _results_distribute(self, rslt_opt, optimizer_used):
        """ Distribute results from the return from each of the optimizers.
        """
        # Initialize dictionary
        rslt = dict()
        rslt['x'] = None
        rslt['fun'] = None
        rslt['success'] = None
        rslt['message'] = None

        # Get the best parametrization and the corresponding value of the
        # criterion function.
        rslt['x'] = self.attr['paras_steps']
        rslt['fun'] = self.attr['value_steps']

        # Special treatments for each optimizer to extract message and
        # success indicator.
        if optimizer_used == 'SCIPY-POWELL':
            rslt['success'] = (rslt_opt[5] not in [1, 2])
            rslt['message'] = 'Optimization terminated successfully.'
            if rslt_opt[5] == 1:
                rslt['message'] = 'Maximum number of function evaluations.'
            elif rslt_opt[5] == 2:
                rslt['message'] = 'Maximum number of iterations.'

        elif optimizer_used == 'SCIPY-BFGS':
            rslt['success'] = (rslt_opt[6] not in [1, 2])
            rslt['message'] = 'Optimization terminated successfully.'
            if rslt_opt[5] == 1:
                rslt['message'] = 'Maximum number of iterations exceeded.'
            elif rslt_opt[5] == 2:
                rslt['message'] = 'Gradient and/or function calls not changing.'

        else:
            raise NotImplementedError

        # Finishing
        return rslt

    def _options_distribute(self, optimizer_used):
        """ Distribute the optimizer specific options.
        """
        # Distribute class attributes
        options = self.attr['optimizer_options']

        # Extract optimizer-specific options
        options_opt = options[optimizer_used]

        # Construct options
        opts = None
        if optimizer_used == 'SCIPY-POWELL':
            opts = (options_opt['xtol'], options_opt['ftol'])
            opts += (options_opt['maxfun'],)

        elif optimizer_used == 'SCIPY-BFGS':
            opts = (options_opt['gtol'], options_opt['epsilon'])

        # Finishing
        return opts

    def lock(self):
        """ Lock class instance.
        """
        # Antibugging.
        assert (not self.attr['is_locked'])

        # Check optimizer options
        self._options_check()

        # Update status indicator
        self.attr['is_locked'] = True

        # Checks
        self._check_integrity_attributes()

    def unlock(self):
        """ Unlock class instance.
        """
        # Antibugging
        assert self.attr['is_locked']

        # Update status indicator
        self.attr['is_locked'] = False

    def _check_key(self, key):
        """ Check that key is present.
        """
        # Check presence
        assert (key in self.attr.keys())

        # Finishing.
        return True

    def _check_integrity_attributes(self):
        """ Check integrity of class instance. This testing is done the first
        time the class is locked and if the package is running in debug mode.
        """
        # Distribute class attributes
        optimizer_options = self.attr['optimizer_options']

        optimizer_used = self.attr['optimizer_used']

        maxiter = self.attr['maxiter']

        version = self.attr['version']

        # Check that the options for the requested optimizer are available.
        assert (optimizer_used in optimizer_options.keys())

        # Check that version is available
        assert (version in ['F2PY', 'FORTRAN', 'PYTHON'])

        # Check that the requested number of iterations is valid
        assert isinstance(maxiter, int)
        assert (maxiter >= 0)

    def crit_func(self, x_free_curre, *args):
        """ This method serves as a wrapper around the alternative
        implementations of the criterion function.
        """
        # Distribute class attributes
        version = self.attr['version']

        # Get all parameters for the current evaluation
        x_all_curre = self._get_all_parameters(x_free_curre)

        # Evaluate criterion function
        if version == 'PYTHON':
            crit_val = pyth_criterion(x_all_curre, *args)
        elif version in ['F2PY', 'FORTRAN']:
            crit_val = f2py_criterion(x_all_curre, *args)
        else:
            raise NotImplementedError

        # Antibugging.
        assert np.isfinite(crit_val)

        # Document progress
        self._logging_interim(x_all_curre, crit_val)

        # Finishing
        return crit_val

    def _get_all_parameters(self, x_free_curr):
        """ This method constructs the full set of optimization parameters
        relevant for the current evaluation.
        """
        # Distribute class attributes
        x_all_start, paras_fixed = self.attr['x_info']

        # Initialize objects
        x_all_curre = []

        # Construct the relevant parameters
        j = 0
        for i in range(26):
            if paras_fixed[i]:
                x_all_curre += [float(x_all_start[i])]
            else:
                x_all_curre += [float(x_free_curr[j])]
                j += 1

        x_all_curre = np.array(x_all_curre)

        # Antibugging
        assert np.all(np.isfinite(x_all_curre))

        # Finishing
        return x_all_curre

    def _options_check(self):
        """ Check the options for all defined optimizers. Regardless of
        whether they are used for the estimation or not.
        """
        # Check options for the SCIPY-BFGS algorithm
        if 'SCIPY-BFGS' in self.attr['optimizer_options'].keys():
            options = self.attr['optimizer_options']['SCIPY-BFGS']
            gtol, epsilon = options['gtol'], options['epsilon']

            assert isinstance(gtol, float)
            assert (gtol > 0)

            assert isinstance(epsilon, float)
            assert (epsilon > 0)

        # Check options for the SCIPY-POWELL algorithm
        if 'SCIPY-POWELL' in self.attr['optimizer_options'].keys():
            options = self.attr['optimizer_options']['SCIPY-POWELL']
            xtol, ftol = options['xtol'], options['ftol']
            maxfun = options['maxfun']

            assert isinstance(maxfun, int)
            assert (maxfun > 0)

            assert isinstance(xtol, float)
            assert (xtol > 0)

            assert isinstance(ftol, float)
            assert (ftol > 0)

    def _logging_interim(self, x, crit_val):
        """ This method write out some information during the optimization.
        """
        # Recording of current evaluation
        self.attr['num_evals'] += 1
        self.attr['value_curre'] = crit_val
        self.attr['paras_curre'] = x

        # Distribute class attributes
        paras_curre = self.attr['paras_curre']

        value_curre = self.attr['value_curre']
        value_steps = self.attr['value_steps']

        num_steps = self.attr['num_steps']
        num_evals = self.attr['num_evals']

        is_first = self.attr['is_first']

        np.savetxt(open('paras_curre.respy.log', 'wb'), x, fmt='%15.8f')

        # Recording of starting information
        if is_first:
            self.attr['value_start'] = crit_val
            self.attr['paras_start'] = x
            np.savetxt(open('paras_start.respy.log', 'wb'), x, fmt='%15.8f')
            if os.path.exists('optimization.respy.log'):
                os.unlink('optimization.respy.log')

        paras_start = self.attr['paras_start']
        value_start = self.attr['value_start']

        # Recording of information about each step.
        if crit_val < value_steps:
            np.savetxt(open('paras_steps.respy.log', 'wb'), x, fmt='%15.8f')
            with open('optimization.respy.log', 'a') as out_file:
                fmt_ = '{0:<10} {1:<25}\n'
                out_file.write(fmt_.format('Step', int(num_steps)))
                out_file.write(fmt_.format('Criterion', crit_val))
                out_file.write(fmt_.format('Time', time.ctime()))
                out_file.write('\n\n')

            # Update class attributes
            self.attr['paras_steps'] = x
            self.attr['value_steps'] = crit_val
            self.attr['num_steps'] = num_steps + 1
            self.attr['is_first'] = False

        paras_steps = self.attr['paras_steps']
        value_steps = self.attr['value_steps']

        # Write information to file.
        with open('optimization.respy.info', 'w') as out_file:
            # Write out information about criterion function
            out_file.write('\n Criterion Function\n\n')
            fmt_ = '{0:>15}    {1:>15}    {2:>15}    {3:>15}\n\n'
            out_file.write(fmt_.format(*['', 'Start', 'Step', 'Current']))
            fmt_ = '{0:>15}    {1:15.4f}    {2:15.4f}    {3:15.4f}\n\n'
            paras = ['', value_start, value_steps, value_curre]
            out_file.write(fmt_.format(*paras))

            # Write out information about the optimization parameters directly.
            out_file.write('\n Optimization Parameters\n\n')
            fmt_ = '{0:>15}    {1:>15}    {2:>15}    {3:>15}\n\n'
            out_file.write(fmt_.format(*['Identifier', 'Start', 'Step', 'Current']))
            fmt_ = '{0:>15}    {1:15.4f}    {2:15.4f}    {3:15.4f}\n'
            for i, _ in enumerate(paras_curre):
                paras = [i, paras_start[i], paras_steps[i], paras_curre[i]]
                out_file.write(fmt_.format(*paras))

            # Write out the current covariance matrix of the reward shocks.
            out_file.write('\n\n Covariance Matrix \n\n')

            for which in ['Start', 'Step', 'Current']:
                if which == 'Start':
                    paras = paras_start
                elif which == 'Step':
                    paras = paras_steps
                else:
                    paras = paras_curre
                fmt_ = '{0:>15}   \n\n'
                out_file.write(fmt_.format(*[which]))
                shocks_cholesky = dist_optim_paras(paras, True)[-1]
                shocks_cov = np.matmul(shocks_cholesky, shocks_cholesky.T)
                fmt_ = '{0:15.4f}    {1:15.4f}    {2:15.4f}    {3:15.4f}\n'
                for i in range(4):
                    out_file.write(fmt_.format(*shocks_cov[i, :]))
                out_file.write('\n')

            fmt_ = '\n{0:<25}{1:>15}\n'
            out_file.write(fmt_.format(*[' Number of Steps', num_steps]))
            out_file.write(fmt_.format(*[' Number of Evaluations', num_evals]))

    def _logging_final(self, rslt):
        """ This method writes out some information when the optimization is
        finished.
        """
        fmt_ = '{0:<10} {1:<25}\n'
        with open('optimization.respy.log', 'a') as out_file:
            out_file.write('Final Report\n\n')
            out_file.write(fmt_.format('Success', str(rslt['success'])))
            out_file.write(fmt_.format('Message', rslt['message']))
            out_file.write(fmt_.format('Criterion', self.attr['value_steps']))
            out_file.write(fmt_.format('Time', time.ctime()))

        with open('optimization.respy.info', 'a') as out_file:
            out_file.write('\n TERMINATED')

