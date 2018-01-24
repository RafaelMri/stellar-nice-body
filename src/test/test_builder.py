import unittest

from tnb.builder import Builder
from tnb.design import Design

from .util import load_yaml


class BaseTest:
    def from_string(self, f):
        return Design.from_string(load_yaml(f))


class TestBuilder(unittest.TestCase, BaseTest):
    def test_basic(self):
        builder = Builder(self.from_string('safe-builder'))
        quorums = builder.make_quorums()

        self.assertNotEqual(quorums, None)
