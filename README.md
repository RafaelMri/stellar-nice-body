# `stellar-nice-body`

## How To Make Quorums

The most important rule to compose quorums is, to connect heavily each validators.

1. select common and extra validators in each instance
    - common validators is selected from all the validators by sampling, sampling number is `number_of_common`
    - extra validators is not in common validators
1. select validators from same instance
    - select from extra validators by sampling, sampling number is `number_of_extra`
    - select from common validator by sampling, sampling number is `number_of_common`
1. if found orphan nodes in same instance, assign orphans to the other nodes
1. select validators by the distance between instances, the number of instances can be set by `number_of_connected_instances`
    1. select validators in one nearest instance
        1. select all the common validators of the instance
    1. select validators in one midest instance
        1. select all the common validators of the instance
    1. select validators in one farest instance
        1. select all the common validators of the instance


# Install

```
$ virtualenv stellar-nice-body
$ cd stellar-nice-body
$ source bin/activate
```

```
$ python setup.py develop
```

# Test

```
$ cd src
$ python -m unittest -v -f
```

# Make Quorum

```
$ bin/stellar-nice-body -v -d design-test.yml make -template ./template -output /tmp/stellar-nice-body-saved/
```
