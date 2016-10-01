#!/usr/bin/env python
import argparse
import os

from respy import estimate
from respy import RespyCls


def dist_input_arguments(parser):
    """ Check input for estimation script.
    """
    # Parse arguments
    args = parser.parse_args()

    # Distribute arguments
    init_file = args.init_file
    single = args.single

    # Check attributes
    assert (single in [True, False])
    assert (os.path.exists(init_file))

    # Finishing
    return single, init_file


def scripts_estimate(single, init_file):
    """ Wrapper for the estimation.
    """
    # Read in baseline model specification.
    respy_obj = RespyCls(init_file)

    # Set maximum iteration count when only an evaluation of the criterion
    # function is requested.
    if single:
        respy_obj.unlock()
        respy_obj.set_attr('maxfun', 0)
        respy_obj.set_attr('preconditioning', ['identity', 0.01, 0.01])
        respy_obj.lock()

    # Optimize the criterion function.
    estimate(respy_obj)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=
        'Start of estimation run with the RESPY package.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--single', action='store_true', dest='single',
        default=False, help='single evaluation')

    parser.add_argument('--init_file', action='store', dest='init_file',
        default='model.respy.ini', help='initialization file')

    # Process command line arguments
    args = dist_input_arguments(parser)

    # Run estimation
    scripts_estimate(*args)
