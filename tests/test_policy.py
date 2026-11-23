from unittest import TestCase

import numpy as np
from retail_decisions.policy import fit_buffer, policy_replay


class PolicyTests(TestCase):
    def test_units_and_euros(self):
        report = policy_replay(np.array([20, 6]), np.array([18, 10]), 0)
        self.assertEqual((report['short_units'], report['excess_units']), (2, 4))
        self.assertAlmostEqual(report['scenario_cost_eur'], 8.4)

    def test_buffer_follows_cost_ratio(self):
        actual, forecast = np.array([0, 0, 4, 10]), np.zeros(4)
        self.assertGreater(fit_buffer(actual, forecast, 9, 1), fit_buffer(actual, forecast, 1, 9))
