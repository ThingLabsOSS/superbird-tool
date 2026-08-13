#!/usr/bin/env python3
"""
Partitions for superbird, extracted from output of: bulkcmd 'amlmmc part 1'
"""
# pylint: disable=line-too-long

# TODO we have an alternate size for data partition, but is the offset always the same?

# offset is in bytes
# size is in 512-byte sectors

SUPERBIRD_PARTITIONS = {
    'bootloader': {
        'offset': 0,
        'size': 4096,
    },
    'reserved': {
        'offset': 73728,
        'size': 131072,
    },
    'cache': {
        'offset': 221184,
        'size': 0,
    },
    'env': {
        'offset': 237568,
        'size': 16384,
    },
    'fip_a': {
        'offset': 270336,
        'size': 8192,
    },
    'fip_b': {
        'offset': 294912,
        'size': 8192,
    },
    'logo': {
        'offset': 319488,
        'size': 16384,
    },
    'dtbo_a': {
        'offset': 352256,
        'size': 8192,
    },
    'dtbo_b': {
        'offset': 376832,
        'size': 8192,
    },
    'vbmeta_a': {
        'offset': 401408,
        'size': 2048,
    },
    'vbmeta_b': {
        'offset': 419840,
        'size': 2048,
    },
    'boot_a': {
        'offset': 438272,
        'size': 32768,
    },
    'boot_b': {
        'offset': 487424,
        'size': 32768,
    },
    'system_a': {
        'offset': 536576,
        'size': 1056856,
    },
    'system_b': {
        'offset': 1609816,
        'size': 1056856,
    },
    'misc': {
        'offset': 2683056,
        'size': 16384,
    },
    'settings': {
        'offset': 2715824,
        'size': 524288,
    },
    'data': {
        'offset': 3256496,
        'size': 4476752,
        'size_alt': 4378448,  # some devices have a smaller data partition
    },
}


# Provenance: the table above was transcribed from `bulkcmd 'amlmmc part 1'`
# and the kernel's partition log on a reference unit. Both are reproducible on
# any stock device, so the raw output is not kept here.
#
# Beware the data-partition naming: `size` (0x889ea000) is the LARGER variant,
# `size_alt` (0x859ea000) is what the reference unit itself reported. So
# `size_alt` is not "the odd one out" — it is the one that unit had, and the
# primary is the value seen on other devices. Don't "correct" this.
