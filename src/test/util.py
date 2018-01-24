import pathlib


def load_yaml(name):
    return pathlib.Path(__file__).parent.joinpath('files').joinpath(name + '.yml').read_text()
