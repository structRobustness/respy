import numpy as np
import pytest

from respy.python.shared.shared_auxiliary import dist_class_attributes
from respy.python.shared.shared_auxiliary import dist_optim_paras
from respy.python.shared.shared_auxiliary import get_optim_paras
from codes.auxiliary import simulate_observed
from codes.random_init import generate_init
from respy import simulate
from respy import RespyCls


@pytest.mark.usefixtures('fresh_directory', 'set_seed')
class TestClass(object):
    """ This class groups together some tests.
    """
    def test_1(self):
        """ Testing ten admissible realizations of state space for the first three periods.
        """
        edu = np.random.randint(5, 10)

        constr = dict()
        constr['periods'] = np.random.randint(3, 5)
        constr['types'] = 1
        constr['edu'] = (edu, edu + 8)

        # Generate random initialization file
        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls('test.respy.ini')

        respy_obj = simulate_observed(respy_obj)

        # Distribute class attributes
        states_number_period = respy_obj.get_attr('states_number_period')

        states_all = respy_obj.get_attr('states_all')

        # The next hard-coded results assume that at least two more years of education are
        # admissible.
        edu_spec = respy_obj.get_attr('edu_spec')
        if edu_spec['max'] - max(edu_spec['start']) < 2:
            return

        # The number of admissible states in the first three periods
        for j, number_period in enumerate([1, 4, 13]):
            assert (states_number_period[j] == number_period)

        # The actual realizations of admissible states in period one
        assert ((states_all[0, 0, :-1] == [0, 0, edu, 1]).all())

        # The actual realizations of admissible states in period two
        states = [[0, 0, edu, 0], [0, 0, edu + 1, 1], [0, 1, edu, 0], [1, 0, edu, 0]]

        for j, state in enumerate(states):
            assert ((states_all[1, j, :-1] == state).all())

        # The actual realizations of admissible states in period three
        states = [[0, 0, edu, 0], [0, 0, edu + 1, 0], [0, 0, edu + 1, 1]]
        states += [[0, 0, edu + 2, 1], [0, 1, edu + 0, 0], [0, 1, edu + 1, 0]]
        states += [[0, 1, edu + 1, 1], [0, 2, edu + 0, 0], [1, 0, edu + 0, 0]]
        states += [[1, 0, edu + 1, 0], [1, 0, edu + 1, 1], [1, 1, edu + 0, 0]]
        states += [[2, 0, edu + 0, 0]]

        for j, state in enumerate(states):
            assert ((states_all[2, j, :-1] == state).all())

    def test_2(self):
        """ Testing whether back-and-forth transformation have no effect.
        """
        for i in range(10):
            num_types = np.random.randint(1, 5)
            num_paras = 43 + 1 + (num_types - 1) * 5

            # Create random parameter vector
            base = np.random.uniform(size=num_paras)

            # We need to manually ensure that the sum of the shares is equal to one.
            base[43:43 + num_types] /= np.sum(base[43:43 + num_types])

            x = base.copy()

            # Apply numerous transformations
            for j in range(10):
                optim_paras = dist_optim_paras(x, is_debug=True)
                args = (optim_paras, num_paras, 'all', True)
                x = get_optim_paras(*args)

            # Checks
            np.testing.assert_allclose(base, x)

    def test_3(self):
        """ Testing whether the back and forth transformation works.
        """
        for _ in range(100):

            # Generate random request
            generate_init()

            # Process request and write out again.
            respy_obj = RespyCls('test.respy.ini')
            respy_obj.write_out('alt.respy.ini')

            # Read both initialization files and compare
            base_ini = open('test.respy.ini', 'r').read()
            alt_ini = open('alt.respy.ini', 'r').read()
            assert base_ini == alt_ini

    def test_4(self):
        """ Testing some of the relationships in the simulated dataset.
        """
        # Generate constraint periods
        constr = dict()
        constr['flag_deterministic'] = np.random.choice([True, False])
        constr['flag_myopic'] = np.random.choice([True, False])

        # Generate random initialization file
        generate_init(constr)

        # Perform toolbox actions
        respy_obj = RespyCls('test.respy.ini')
        _, df = simulate(respy_obj)

        # Check special case
        optim_paras, num_types, edu_spec, num_periods = dist_class_attributes(respy_obj,
            'optim_paras', 'num_types', 'edu_spec', 'num_periods')

        shocks_cholesky = optim_paras['shocks_cholesky']

        is_deterministic = (np.count_nonzero(shocks_cholesky) == 0)

        # The wage entries should correspond to the ex-post rewards
        for choice in [1, 2]:
            cond = (df['Choice'] == choice)
            label_sys = 'Systematic_Reward_{}'.format(choice)
            label_sho = 'Shock_Reward_{}'.format(choice)
            df['Ex_Post_Reward'] = df[label_sys] * df[label_sho]

            col_1 = df['Ex_Post_Reward'].loc[:, cond]
            col_2 = df['Wage'].loc[:, cond]
            np.testing.assert_array_almost_equal(col_1, col_2)

        # The systematic component for the alternative to stay home should always be identical
        # by type, at least within periods.
        for period in range(num_periods):
            assert (df['Systematic_Reward_4'].loc[:, period].nunique() <= num_types)

        # In the myopic case, the total reward should the equal to the ex post rewards.
        if respy_obj.get_attr('is_myopic'):
            for i in range(1, 5):
                label = 'Ex_Post_Reward_{}'.format(i)
                label_sys = 'Systematic_Reward_{}'.format(i)
                label_sho = 'Shock_Reward_{}'.format(i)

                if i in [1, 2]:
                    df[label] = df[label_sys] * df[label_sho]
                else:
                    df[label] = df[label_sys] + df[label_sho]

                # The equality does not hold if a state is inadmissible.
                cond = (df['Years_Schooling'] != edu_spec['max'])

                col_1 = df['Total_Reward_' + str(i)].loc[:, cond]
                col_2 = df[label].loc[:, cond]

                np.testing.assert_array_almost_equal(col_1, col_2)

        # If the model is deterministic, all shocks should be equal to zero. Of course,
        # one after exponentiation for wages.
        if is_deterministic:
            for i in range(1, 5):
                label = 'Shock_Reward_{}'.format(i)
                if i in [1, 2]:
                    cond = (df[label] == 1)
                else:
                    cond = (df[label] == 0)
                assert np.all(cond)
