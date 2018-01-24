import unittest

from tnb.design import (
    Design,
    Network,
)
from tnb.validator import Validator
from tnb.exceptions import ValidationError

from .util import load_yaml


class BaseTest:
    o = dict(nodes=dict(node=dict(allow_missing_fields=('secret_seed',))))

    def validate_from_string(self, f):
        return Validator(Design.from_string(load_yaml(f))).validate(**self.o)


class TestDesignValidation(unittest.TestCase, BaseTest):
    def test_basic(self):
        self.assertEqual(self.validate_from_string('safe-design'), None)

    def test_missing_network_passphrase(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('network-passphrase-missing'),
        )
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('network-passphrase-empty'),
        )

    def test_wrong_base_safety(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('wrong-base-safety'),
        )

    def test_low_base_safety(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('low-base-safety'),
        )

    def test_too_high_base_safety(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('too-high-base-safety'),
        )


class TestInstancesValidation(unittest.TestCase, BaseTest):
    def test_missing_instances(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('missing-instances'),
        )

    def test_wrong_instances(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('wrong-instances'),
        )

    def test_missing_internal_ip(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('missing-internal_ip-instances'),
        )

    def test_empty_internal_ip(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('empty-internal_ip-instances'),
        )

    def test_wrong_internal_ip(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('wrong-internal_ip-instances'),
        )


class TestDatabasesValidation(unittest.TestCase, BaseTest):
    def test_missing_databases(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('missing-databases'),
        )

    def test_empty_databases(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('empty-databases'),
        )

    def test_missing_port_postgresql_database(self):
        self.assertEqual(
            self.validate_from_string('missing-port-postgresql-database'),
            None,
        )

    def test_unknown_engine_database(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('unknown-engine-database'),
        )


class TestHistoryValidation(unittest.TestCase, BaseTest):
    def test_missing_history(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('missing-history'),
        )

    def test_duplicated_nodes(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('duplicated-trusted-history'),
        )


class TestNodesValidation(unittest.TestCase, BaseTest):
    def test_missing_nodes(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('missing-nodes'),
        )

    def test_empty_nodes(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('empty-nodes'),
        )

    def test_duplicated_common_in_node(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('duplicated-common-node'),
        )

    def test_unknown_database(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('unknown-database'),
        )

    def test_unknown_history(self):
        self.assertRaises(
            ValidationError,
            lambda: self.validate_from_string('unknown-history'),
        )

    def test_bad_secret_seed(self):
        self.assertRaises(
            ValidationError,
            lambda: Validator(Design.from_string(load_yaml('bad-secret_seed'))).validate(),
        )

    def test_duplicated_secret_seed(self):
        self.assertRaises(
            ValidationError,
            lambda: Validator(Design.from_string(load_yaml('duplicated-secret_seed'))).validate(),
        )


class TestFailureSafety(unittest.TestCase, BaseTest):
    def test_basic(self):
        design = Design.from_string(load_yaml('safe-design'))
        network = Network.from_design(design)
        self.assertEqual(network.default_settings['failure_safety'], 1)
