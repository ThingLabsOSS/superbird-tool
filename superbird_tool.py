#!/usr/bin/env python3
"""
Tool for working with Spotify Car Thing, aka superbird
"""
# pylint: disable=line-too-long,broad-except

import argparse
import functools
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Resolved once so the tool works regardless of CWD.
SCRIPT_DIR = Path(__file__).resolve().parent
STOCK_ENV_PATH = SCRIPT_DIR / 'stock_env.txt'

from superbird_device import (
    SuperbirdDevice,
    IMAGES_PATH,
    check_device_mode,
    enter_burn_mode,
    find_device,
)
from uboot_env import read_environ

VERSION = '0.2.0'

# ---------------------------------------------------------------------------
# Tables that drive --dump_device / --restore_device.
# Bootloader, env, data, settings are special-cased in the handlers below.
# ---------------------------------------------------------------------------

STANDARD_PARTITIONS = [
    ('fip_a',    'fip_a.dump'),
    ('fip_b',    'fip_b.dump'),
    ('logo',     'logo.dump'),
    ('dtbo_a',   'dtbo_a.dump'),
    ('dtbo_b',   'dtbo_b.dump'),
    ('vbmeta_a', 'vbmeta_a.dump'),
    ('vbmeta_b', 'vbmeta_b.dump'),
    ('boot_a',   'boot_a.dump'),
    ('boot_b',   'boot_b.dump'),
    ('misc',     'misc.dump'),
]
SYSTEM_PARTITIONS = [
    ('system_a', 'system_a.ext2'),
    ('system_b', 'system_b.ext2'),
]
# Userdata partitions get the optional --dont_reset / factory-reset treatment.
USERDATA_PARTITIONS = [
    ('data',     'data.ext4',     'factory resetting instead'),
    ('settings', 'settings.ext4', 'erasing settings partition instead'),
]

# When restoring, these are the legacy-style .dump filenames we rename
# system_a.dump → system_a.ext2 etc. before looking them up.
RENAME_ON_RESTORE = {
    'system_a.dump':  'system_a.ext2',
    'system_b.dump':  'system_b.ext2',
    'settings.dump':  'settings.ext4',
    'data.dump':      'data.ext4',
}

# ---------------------------------------------------------------------------
# u-boot setenv sequences. Each is a list of bulkcmds run under `amlmmc env`,
# finishing with `env save`. Driving them off data deduplicates the giant
# storeargs reconstruction that used to be copy-pasted inline.
# ---------------------------------------------------------------------------

# initargs block shared by --enable_uart_shell and --disable_avb2
_INITARGS_COMMON = [
    'setenv initargs init=/sbin/pre-init',
    r'setenv initargs "${initargs} ramoops.pstore_en=1"',
    r'setenv initargs "${initargs} ramoops.record_size=0x8000"',
    r'setenv initargs "${initargs} ramoops.console_size=0x4000"',
    r'setenv initargs "${initargs} rootfstype=ext4"',
    r'setenv initargs "${initargs} console=ttyS0,115200n8"',
    r'setenv initargs "${initargs} no_console_suspend"',
    r'setenv initargs "${initargs} earlycon=aml-uart,0xff803000"',
]

# Note: enable_uart_shell uses unquoted ${initargs} expansion; disable_avb2 uses
# the quoted form. That's how the original code was written so we preserve it.
_INITARGS_UNQUOTED = [
    'setenv initargs init=/sbin/pre-init',
    r'setenv initargs ${initargs} ramoops.pstore_en=1',
    r'setenv initargs ${initargs} ramoops.record_size=0x8000',
    r'setenv initargs ${initargs} ramoops.console_size=0x4000',
    r'setenv initargs ${initargs} rootfstype=ext4',
    r'setenv initargs ${initargs} console=ttyS0,115200n8',
    r'setenv initargs ${initargs} no_console_suspend',
    r'setenv initargs ${initargs} earlycon=aml-uart,0xff803000',
]

ENABLE_UART_SHELL_CMDS = _INITARGS_UNQUOTED

DISABLE_AVB2_BASE = [
    r'setenv storeargs ${storeargs} setenv avb2 0\;',
] + _INITARGS_COMMON

DISABLE_AVB2_SLOT_CMDS = {
    'a': [
        r'setenv initargs "${initargs} ro root=/dev/mmcblk0p14"',
        'setenv active_slot _a',
        'setenv boot_part boot_a',
    ],
    'b': [
        r'setenv initargs "${initargs} ro root=/dev/mmcblk0p15"',
        'setenv active_slot _b',
        'setenv boot_part boot_b',
    ],
}

ENABLE_BURN_MODE_CMDS         = [r'setenv storeargs "${storeargs} run update\;"']
ENABLE_BURN_MODE_BUTTON_CMDS  = [r'setenv storeargs "${storeargs} if gpio input GPIOA_3; then run update; fi;"']

# Rebuild a clean stock storeargs (counterpart to ENABLE_BURN_MODE_CMDS).
DISABLE_BURN_MODE_CMDS = [
    r'setenv storeargs "setenv bootargs \${initargs} \${fs_type}"',
    r'setenv storeargs "${storeargs} reboot_mode_android=\${reboot_mode_android}"',
    r'setenv storeargs "${storeargs} logo=\${display_layer},loaded,\${fb_addr}"',
    r'setenv storeargs "${storeargs} fb_width=\${fb_width} fb_height=\${fb_height}"',
    r'setenv storeargs "${storeargs} vout=\${outputmode},enable"',
    r'setenv storeargs "${storeargs} panel_type=\${panel_type}"',
    r'setenv storeargs "${storeargs} frac_rate_policy=\${frac_rate_policy}"',
    r'setenv storeargs "${storeargs} osd_reverse=\${osd_reverse}"',
    r'setenv storeargs "${storeargs} video_reverse=\${video_reverse}"',
    r'setenv storeargs "${storeargs} irq_check_en=\${Irq_check_en}"',
    r'setenv storeargs "${storeargs} androidboot.selinux=\${EnableSelinux}"',
    r'setenv storeargs "${storeargs} androidboot.firstboot=\${firstboot}"',
    r'setenv storeargs "${storeargs} jtag=\${jtag} uboot_version=\${gitver}\;"',
    r'setenv storeargs "${storeargs} setenv bootargs \${bootargs} androidboot.hardware=amlogic\;"',
    r'setenv storeargs "${storeargs} setenv avb2 0\;"',
]

DISABLE_CHARGER_CHECK_CMDS = ['setenv bootcmd "run storeboot"']
ENABLE_CHARGER_CHECK_CMDS  = ['setenv bootcmd "run check_charger"']


def run_env_sequence(dev, cmds, *, init=True, save=True):
    """Run a list of bulkcmds wrapped by the standard `amlmmc env` / `env save` pair."""
    if init:
        dev.bulkcmd('amlmmc env')
    for cmd in cmds:
        dev.bulkcmd(cmd)
    if save:
        dev.bulkcmd('env save')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def convert_env_dump(env_dump:str, env_file:str):
    """Convert a dumped env partition image into a human-readable text file."""
    print(f'Converting partition dump: {env_dump} to textfile: {env_file}')
    (environ, _length, _crc) = read_environ(env_dump)
    with open(env_file, 'w', encoding='utf-8') as oef:
        oef.writelines(f'{key}={value}\n' for key, value in environ.items())


def rename_legacy_dumps(folderpath):
    """Map older .dump filenames to current .ext2/.ext4 names so old dumps still restore."""
    for old, new in RENAME_ON_RESTORE.items():
        src = os.path.join(folderpath, old)
        if os.path.isfile(src):
            os.rename(src, os.path.join(folderpath, new))
            print(f'Renamed {old} -> {new}')


def validate_slot(value, fallback='a'):
    """Normalise a slot argument to 'a' or 'b'."""
    if value.lower() in ('a', 'b'):
        return value.lower()
    print(f'Invalid slot provided, using slot {fallback}')
    return fallback


def requires_burn_mode(handler):
    """Decorator: enter burn mode before invoking handler, exit cleanly on failure."""
    @functools.wraps(handler)
    def wrapper(args, dev):
        dev = enter_burn_mode(dev)
        if dev is None:
            sys.exit(1)
        return handler(args, dev)
    return wrapper


# ---------------------------------------------------------------------------
# Handlers — each takes (args, dev). The decorator guarantees `dev` is in burn
# mode when the body runs.
# ---------------------------------------------------------------------------

def cmd_find_device(args, dev):
    find_device()


def cmd_convert_env_dump(args, dev):
    convert_env_dump(args.convert_env_dump[0], args.convert_env_dump[1])


def cmd_burn_mode(args, dev):
    if check_device_mode('usb-burn', silent=True):
        print('Device already in USB Burn Mode')
        return
    # enter_burn_mode prints its own "Device is now in USB Burn Mode" on success.
    if enter_burn_mode(dev) is None:
        sys.exit(1)


def cmd_continue_boot(args, dev):
    if check_device_mode('usb-burn'):
        print('Continuing boot...')
        dev.bulkcmd('mw.b 0x17f89754 1')


@requires_burn_mode
def cmd_bulkcmd(args, dev):
    dev.bulkcmd(args.bulkcmd[0])


@requires_burn_mode
def cmd_bulkcmd_shell(args, dev):
    print("Entering shell. Use Ctrl+C to exit\n"
          "If valid commands fail, u-boot may be in a bad state.\n"
          "Just a note, bulkcmd is unable to display the output of commands.\n"
          "Refer to 'uboot-command-reference.txt' to get a list of commands.")
    while True:
        try:
            cmd = input("bulkcmd: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            return
        dev.bulkcmd(cmd, is_shell=True)


@requires_burn_mode
def cmd_boot_adb_kernel(args, dev):
    slot = validate_slot(args.boot_adb_kernel[0])
    print('Booting adb kernel on slot', slot)
    env_file = str(IMAGES_PATH / f'env_{slot}.txt')
    kernel   = str(IMAGES_PATH / 'superbird.kernel.img')
    initrd   = str(IMAGES_PATH / 'superbird.initrd.img')
    dev.boot(env_file, kernel, initrd)


@requires_burn_mode
def cmd_enable_uart_shell(args, dev):
    print('Enabling UART shell')
    run_env_sequence(dev, ENABLE_UART_SHELL_CMDS)


@requires_burn_mode
def cmd_disable_avb2(args, dev):
    slot = validate_slot(args.disable_avb2[0])
    print('Disabling A/B booting locking to slot:', slot)
    run_env_sequence(dev, DISABLE_AVB2_BASE + DISABLE_AVB2_SLOT_CMDS[slot])


@requires_burn_mode
def cmd_enable_burn_mode(args, dev):
    print('Enabling USB Burn Mode at every boot (if USB host connected)')
    run_env_sequence(dev, ENABLE_BURN_MODE_CMDS)
    print('Every time the device boots, if usb is connected it will boot into USB Burn Mode')


@requires_burn_mode
def cmd_enable_burn_mode_button(args, dev):
    print('Enabling USB Burn Mode at boot if preset button 4 is held')
    run_env_sequence(dev, ENABLE_BURN_MODE_BUTTON_CMDS)
    print('Every time the device boots, if usb is connected AND preset button 4 is held, it will boot into USB Burn Mode')


@requires_burn_mode
def cmd_disable_burn_mode(args, dev):
    print('Disabling USB Burn Mode at every boot (if USB host connected)')
    run_env_sequence(dev, DISABLE_BURN_MODE_CMDS)
    print('The device will now boot normally, and will NOT boot into USB Burn Mode')


@requires_burn_mode
def cmd_disable_charger_check(args, dev):
    print('Disabling check for valid charger')
    # bootcmd is normally `run check_charger`; the check then calls `run storeboot`.
    # Skipping the check is just calling storeboot directly.
    run_env_sequence(dev, DISABLE_CHARGER_CHECK_CMDS)
    print('The device will not check for valid charger')


@requires_burn_mode
def cmd_enable_charger_check(args, dev):
    run_env_sequence(dev, ENABLE_CHARGER_CHECK_CMDS)
    print('The device will now check for valid charger, requiring you to press menu button to bypass')


@requires_burn_mode
def cmd_dump_partition(args, dev):
    part_name, outfile = args.dump_partition
    dev.dump_partition(part_name, outfile)
    print(f'dumped partition to {outfile}')


@requires_burn_mode
def cmd_restore_partition(args, dev):
    part_name, infile = args.restore_partition
    dev.restore_partition(part_name, infile)
    print(f'restored partition from {infile}')


@requires_burn_mode
def cmd_dump_device(args, dev):
    folder = args.dump_device[0]
    print(f'dumping entire device to {folder}')
    shutil.rmtree(folder, ignore_errors=True)
    os.mkdir(folder)
    dev.dump_partition('bootloader', f'{folder}/bootloader.dump')
    dev.dump_partition('env',        f'{folder}/env.dump')
    # convert env dump to txt for easy access and so it's present on restore
    convert_env_dump(f'{folder}/env.dump', f'{folder}/env.txt')
    for part, fname in STANDARD_PARTITIONS + SYSTEM_PARTITIONS:
        dev.dump_partition(part, f'{folder}/{fname}')
    for part, fname, _action in USERDATA_PARTITIONS:
        dev.dump_partition(part, f'{folder}/{fname}')
    print('device dump complete')


@requires_burn_mode
def cmd_restore_device(args, dev):
    folder = args.restore_device[0]
    rename_legacy_dumps(folder)
    print(f'restoring entire device from dumpfiles in {folder}')

    # Verify required files are present before doing anything destructive.
    required = [fname for _part, fname in STANDARD_PARTITIONS + SYSTEM_PARTITIONS]
    for fname in required:
        if not os.path.isfile(f'{folder}/{fname}'):
            print(f'Error: missing expected dump file: {folder}/{fname}')
            sys.exit(1)

    # env.txt is the canonical form — partition sizes can drift, txt is safer.
    if not os.path.isfile(f'{folder}/env.txt'):
        if not os.path.isfile(f'{folder}/env.dump'):
            print(f'Error: missing expected dump file: {folder}/env.dump')
            sys.exit(1)
        convert_env_dump(f'{folder}/env.dump', f'{folder}/env.txt')

    dev.send_env_file(f'{folder}/env.txt')
    dev.bulkcmd('env save')

    for part, fname in STANDARD_PARTITIONS + SYSTEM_PARTITIONS:
        dev.restore_partition(part, f'{folder}/{fname}')

    reset_recommended = False
    for part, fname, action in USERDATA_PARTITIONS:
        path = f'{folder}/{fname}'
        if not os.path.exists(path):
            print(f'did not find {path}, {action}')
            try:
                firstboot = '0' if args.dont_reset else '1'
                if args.dont_reset:
                    print(f'--dont_reset specified. Not erasing {part}.')
                dev.bulkcmd(f'setenv firstboot {firstboot}')
                dev.bulkcmd('saveenv')
            except Exception:
                print(f"\nErasing {part} failed. A factory reset is recommended\n")
                reset_recommended = True
        else:
            dev.restore_partition(part, path)

    # bootloader always last
    try:
        dev.restore_partition('bootloader', f'{folder}/bootloader.dump')
    except Exception:
        print("Flashing bootloader failed. If you encounter any issues, try flashing again.")

    print('Device restore complete. Replug your Car Thing to start using it.')
    if reset_recommended:
        print("\n\nFactory reseting your Car Thing is recommended. You can do this by "
              "unplugging your device then replugging it while holding the preset 2 and "
              "back buttons. You can let go of the buttons when the Spotify logo appears.")


@requires_burn_mode
def cmd_restore_stock_env(args, dev):
    print('Restoring env by first wiping env, then importing stock_env.txt')
    dev.bulkcmd('amlmmc env')
    time.sleep(1)
    dev.bulkcmd('amlmmc erase env')
    time.sleep(1)
    dev.send_env_file(str(STOCK_ENV_PATH))
    dev.bulkcmd('env save')


@requires_burn_mode
def cmd_send_env(args, dev):
    env_file = args.send_env[0]
    print(f'Importing the contents of {env_file}')
    dev.bulkcmd('amlmmc env')
    dev.send_env_file(env_file)
    dev.bulkcmd('env save')


@requires_burn_mode
def cmd_send_full_env(args, dev):
    env_file = args.send_full_env[0]
    print('Wiping env partition')
    dev.bulkcmd('amlmmc env')
    time.sleep(1)
    dev.bulkcmd('amlmmc erase env')
    time.sleep(1)
    print(f'Importing the contents of {env_file}')
    dev.send_env_file(env_file)
    dev.bulkcmd('env save')


@requires_burn_mode
def cmd_get_env(args, dev):
    env_file = args.get_env[0]
    with tempfile.NamedTemporaryFile() as tmp:
        print(f'Getting current env and writing to text file: {env_file}')
        dev.bulkcmd('amlmmc env')
        dev.dump_partition('env', tmp.name)
        convert_env_dump(tmp.name, env_file)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

# Order matters — first matching flag wins, mirroring the original if/elif chain.
# (flag, handler, needs_device). When needs_device is False, the handler runs
# without constructing a SuperbirdDevice — used for purely-local operations.
DISPATCH = [
    ('find_device',             cmd_find_device,             False),
    ('convert_env_dump',        cmd_convert_env_dump,        False),
    ('bulkcmd',                 cmd_bulkcmd,                 True),
    ('bulkcmd_shell',           cmd_bulkcmd_shell,           True),
    ('boot_adb_kernel',         cmd_boot_adb_kernel,         True),
    ('enable_uart_shell',       cmd_enable_uart_shell,       True),
    ('disable_avb2',            cmd_disable_avb2,            True),
    ('enable_burn_mode',        cmd_enable_burn_mode,        True),
    ('enable_burn_mode_button', cmd_enable_burn_mode_button, True),
    ('disable_burn_mode',       cmd_disable_burn_mode,       True),
    ('dump_partition',          cmd_dump_partition,          True),
    ('restore_partition',       cmd_restore_partition,       True),
    ('dump_device',             cmd_dump_device,             True),
    ('restore_device',          cmd_restore_device,          True),
    ('disable_charger_check',   cmd_disable_charger_check,   True),
    ('enable_charger_check',    cmd_enable_charger_check,    True),
    ('burn_mode',               cmd_burn_mode,               True),
    ('continue_boot',           cmd_continue_boot,           True),
    ('restore_stock_env',       cmd_restore_stock_env,       True),
    ('send_env',                cmd_send_env,                True),
    ('send_full_env',           cmd_send_full_env,           True),
    ('get_env',                 cmd_get_env,                 True),
]


def build_device(args):
    """Construct the SuperbirdDevice with whatever burn-speed / transfer flags were set."""
    if args.slower_burn:
        print("Using slower burn speed (forces legacy transfer path)")
        return SuperbirdDevice(slowerBurn=True)
    if args.slow_burn:
        print("Using slow burn speed (forces legacy transfer path)")
        return SuperbirdDevice(slowBurn=True)
    if args.legacy_transfer:
        print("Using legacy transfer path (amlmmc read/write)")
        return SuperbirdDevice(legacy_transfer=True)
    return SuperbirdDevice()


# ---------------------------------------------------------------------------
# Help text — hand-rolled because argparse's auto-help doesn't group sections.
# ---------------------------------------------------------------------------

HELP_TEXT = """General:
  -h, --help            Show this help message and exit
  --find_device         Find superbird device and show its current boot mode
  --burn_mode           Enter USB Burn Mode (if currently in USB Mode)
  --continue_boot       Continue booting normally (if currently in USB Burn Mode)

Booting:
  --boot_adb_kernel BOOT_SLOT
                        Boot a kernel with adb enabled on chosen slot (A or B)(not persistent)
  --disable_avb2 BOOT_SLOT
                        Disable A/B booting, lock to chosen slot(A or B)
  --enable_burn_mode    Enable USB Burn Mode at every boot (when connected to USB host)
  --enable_burn_mode_button
                        Enable USB Burn Mode if preset button 4 is held while booting (when connected to USB host)
  --disable_burn_mode   Disable USB Burn Mode
  --disable_charger_check
                        Disable check for valid charger at boot
  --enable_charger_check
                        Enable check for valid charger at boot

Restoring:
  --restore_device INPUT_FOLDER
                        Restore all partitions from a folder
  --restore_partition PARTITION_NAME INPUT_FILE
                        Restore a partition from a dump file
  --dont_reset          Don't factory reset when restoring device. Use in combination with restore commands.
  --slow_burn           Use a slower burning speed. Use this if restoring crashes mid-flash. (forces legacy path)
  --slower_burn         Use an even slower burning speed. (forces legacy path)
  --legacy_transfer     Force the old (slow) amlmmc read/write transfer path.
                        Default is the faster upload/download store path. Try this if dump/restore misbehaves.

Dumping:
  --dump_device OUTPUT_FOLDER
                        Dump all partitions to a folder
  --dump_partition PARTITION_NAME OUTPUT_FILE
                        Dump a partition to a file

U-Boot Enviroment:
  --get_env ENV_TXT     Dump device env partition, and convert it to env.txt format
  --send_env ENV_TXT    Import contents of given env.txt file (without wiping)
  --send_full_env ENV_TXT
                        Wipe env, then import contents of given env.txt file
  --restore_stock_env   Wipe env, then restore default env values from stock_env.txt
  --convert_env_dump ENV_DUMP OUTPUT_TXT
                        Convert a local dump of env partition into text format
Advanced:
  --bulkcmd COMMAND     Run a uboot command on the device
  --bulkcmd_shell       Open a pseudo-shell for sending uboot commands
  --enable_uart_shell   Enable Linux UART shell
"""


def build_parser():
    p = argparse.ArgumentParser(description='Options cannot be combined; do one thing at a time :)',
                                add_help=False)
    # commands
    p.add_argument('--find_device',             action='store_true')
    p.add_argument('--burn_mode',               action='store_true')
    p.add_argument('--continue_boot',           action='store_true')
    p.add_argument('--bulkcmd',                 type=str, nargs=1, metavar='COMMAND')
    p.add_argument('--bulkcmd_shell',           action='store_true')
    p.add_argument('--boot_adb_kernel',         type=str, nargs=1, metavar='BOOT_SLOT')
    p.add_argument('--enable_uart_shell',       action='store_true')
    p.add_argument('--disable_avb2',            type=str, nargs=1, metavar='BOOT_SLOT')
    p.add_argument('--enable_burn_mode',        action='store_true')
    p.add_argument('--enable_burn_mode_button', action='store_true')
    p.add_argument('--disable_burn_mode',       action='store_true')
    p.add_argument('--disable_charger_check',   action='store_true')
    p.add_argument('--enable_charger_check',    action='store_true')
    p.add_argument('--dump_device',             type=str, nargs=1, metavar='OUTPUT_FOLDER')
    p.add_argument('--restore_device',          type=str, nargs=1, metavar='INPUT_FOLDER')
    p.add_argument('--dump_partition',          type=str, nargs=2, metavar=('PARTITION_NAME', 'OUTPUT_FILE'))
    p.add_argument('--restore_partition',       type=str, nargs=2, metavar=('PARTITION_NAME', 'INPUT_FILE'))
    p.add_argument('--restore_stock_env',       action='store_true')
    p.add_argument('--send_env',                type=str, nargs=1, metavar='ENV_TXT')
    p.add_argument('--send_full_env',           type=str, nargs=1, metavar='ENV_TXT')
    p.add_argument('--convert_env_dump',        type=str, nargs=2, metavar=('ENV_DUMP', 'OUTPUT_TXT'))
    p.add_argument('--get_env',                 type=str, nargs=1, metavar='ENV_TXT')
    # modifiers
    p.add_argument('--dont_reset',     action='store_true')
    p.add_argument('--slow_burn',      action='store_true')
    p.add_argument('--slower_burn',    action='store_true')
    p.add_argument('--legacy_transfer', action='store_true')
    p.add_argument('--help', '-h', action='store_true', dest='help')
    return p


def main():
    print(f'Spotify Car Thing (superbird) toolkit, v{VERSION}, by Thing Labs and Bishop Dynamics')
    print('     https://github.com/thinglabsoss/superbird-tool   ')
    print('     Forked from https://github.com/bishopdynamics/superbird-tool')
    print('')

    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit(1)

    args = build_parser().parse_args()

    if platform.system() == 'Linux' and os.geteuid() != 0:
        print('NOTE: Not running as root. If you get "Access Denied" errors, run as root or add to your udev rules.')

    if args.help:
        print(HELP_TEXT)
        return

    # Find the chosen command. First match wins, preserving the original precedence.
    chosen = next(((flag, handler, needs_dev) for flag, handler, needs_dev in DISPATCH if getattr(args, flag)), None)
    if chosen is None:
        print(HELP_TEXT)
        sys.exit(1)
    flag, handler, needs_dev = chosen

    start_time = time.time()
    dev = build_device(args) if needs_dev else None
    handler(args, dev)
    print(f'Operation took: {time.time() - start_time:.2f}s')


if __name__ == '__main__':
    main()
