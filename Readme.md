# Cross-Platform Spotify Car Thing (superbird) hacking toolkit

This toolkit re-implements most of the functionality from [frederic's scripts](https://github.com/frederic/superbird-bulkcmd).
The key difference here is that this tool uses [`pyamlboot`](https://github.com/superna9999/pyamlboot) instead of the proprietary `update` binary from Amlogic, 
which allows it to work on many more platforms!

Everything in [`images/`](images/) came directly from [frederic's repo](https://github.com/frederic/superbird-bulkcmd).

The fast partition-dump path (`upload store` AMLC envelope protocol) was ported from [dustinlieu/car-thing-bootloader-tool](https://github.com/dustinlieu/car-thing-bootloader-tool), which is MIT-licensed. The full license text and scope of the port is in [`LICENSES/car-thing-bootloader-tool-MIT.txt`](LICENSES/car-thing-bootloader-tool-MIT.txt).

The purpose of this tool is to provide useful, working examples for how to use `pyamlboot` to perform development-related tasks on the Spotify Car Thing.

Contributions are welcome. This code is unlicensed: you can do whatever you want with it.
 `pyamlboot` is Apache-2.0, `libusb` is LGPL-2.1

A [Changelog can be found here](Changelog.md)

### Want an easier way to flash your Car Thing? Try [https://terbium.app](https://terbium.app)!

## Warranty and Liability
This tool is provided without any warranty or guarantee of performance. While there have been no reported instances of this tool permanently damaging a Car Thing, such a risk exists.  By using this tool, you acknowledge this risk and assume full responsibility for any potential issues that may arise.

## Note about slow flashing/dumping speed
[dustinlieu](https://github.com/dustinlieu) has reimplemented the commands/protocol that the original `update` binary from Amlogic uses to read/write directly to the flash chip. You can find their code [here.](https://github.com/dustinlieu/car-thing-bootloader-tool)

### Original note:

This tool tries to replace the proprietary `update` binary from Amlogic, and it covers enough functionality to be useful for superbird.
However, dumping partitions is MUCH slower.

The original tool from Amlogic manages to read directly from the mmc, without having to first read it into memory, 
so it is a lot faster at about `12MB/s` or about 7 minutes to dump all partitions.
Unfortunately, we cannot currently replicate this method using `pyamlboot`.

Instead, to dump partitions we first have to tell the device to read a chunk (128KB) into memory, and then we can read it from memory out to a file, one chunk at a time.
The copy rate for reading is about `545KB/s`, and in my testing on Ubuntu x86_64 it takes about 110 minutes to dump all partitions!

The same thing must be done in reverse to restore a partition, but writing is much faster, and we can use larger chunks (512KB), 
so copy rate for writing is about `5.1MB/s`, and it takes about 11 minutes to write all partitions. If the `data` and `settings` partitions are omitted,
it takes about 4 minutes to write.


## Supported Platforms

The only requirements to run this are:
1. python3
2. libusb
3. pyamlboot from [github master branch](https://github.com/superna9999/pyamlboot)

You need to install pyamlboot from the [master branch](https://github.com/superna9999/pyamlboot) on GitHub because the current pypy package is too old,
and is missing `bulkcmd` functionality.

### macOS
Tested on `aarch64` and `x86_64`

On macOS, you must install `libusb` from homebrew. Additionally, if you have a `aarch64` mac, you will also need to install `pyusb` from the master branch as you'll need a workaround that is not present is the current pypy package.

Tested with python `3.13.0`, installed via [pyenv](https://github.com/pyenv/pyenv).

```bash
brew install libusb
python3 -m venv .venv 
source ./venv/bin/activate
python3 -m pip install git+https://github.com/pyusb/pyusb # Only needed on MacOS w/ Apple Silicon
python3 -m pip install git+https://github.com/superna9999/pyamlboot
python3 superbird_tool.py --find_device
```

### Linux
Tested on `aarch64` and `x86_64`

On Linux, you need to install pyamlboot and you might need to add a udev rule.
```bash
python3 -m venv .venv 
source ./venv/bin/activate
python3 -m pip install git+https://github.com/superna9999/pyamlboot
./superbird_tool.py --find_device

# If you get "Access Denied" errors, run the following commands (alternatively you can run superbird_tool as root)
sudo tee /etc/udev/rules.d/60-superbird.rules >/dev/null <<EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="1b8e", ATTRS{idProduct}=="c003", GROUP="$USER", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Windows

Tested on `x86_64`, but it seems really difficult to get this working consistently on Windows. I recommend Linux or macOS.

On Windows, setup is a little more involved. First download and install [python for windows](https://www.python.org/downloads/windows/) (tested with 3.10 and 3.11).
Next you need to setup a virtual enviroment and install pyamlboot:
```bash
python3 -m venv .venv 
.venv/Scripts/activate
python -m pip install pyusb git+https://github.com/superna9999/pyamlboot
```

After doing the above, you'll need to install the correct driver. Start off by downloading [Zadig](https://zadig.akeo.ie/).
- Once you have it downloaded, open it then put your Car Thing into USB Burn Mode by holding the preset 1 & 4 buttons while plugging it in. The screen should stay black.
- In Zadig you should see a `GX-CHIP` device appear. When it shows up, click `Edit` then configure Zadig so the options are like this:
![image](https://github.com/user-attachments/assets/69da7f52-876e-4172-b4fe-dd2732c3c6ee)
- Click `Install Driver` and wait for it to finish.

Note: If commands like `--find_device` or `--burn_mode` don't work, try installing the WinUSB driver instead of libusb

Finally, you should be able to run the tool
```bash
python superbird_tool.py --find_device
```

Confirm things actually work by connecting device in USB Mode (hold buttons 1 & 4 while connecting), and then entering USB Burn Mode:
```bash
python superbird_tool.py --burn_mode
```

## Usage

```
General:
  -h, --help            Show this help message and exit
  --find_device         Find superbird device and show its current boot mode
  --burn_mode [CUSTOM_FIP]
                        Enter USB Burn Mode (if currently in USB Mode).
                        With a CUSTOM_FIP path, RAM-load a custom signed FIP
                        body (e.g. aml_encrypt_g12a --bootsig output) instead
                        of vendor burn-mode u-boot. Must be signed with a key
                        matching the SoC's fused secure-boot ROM key hash.
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
  --chainload BINFILE   Load an aarch64 binary into RAM and `go` to it.
                        Use --load_addr ADDR to override default (0x01080000).
  --enable_uart_shell   Enable Linux UART shell
```

## Boot Modes
There are four possible boot modes

### USB Mode
This is what you get if you hold buttons 1 & 4 while plugging in the device.

The UART console will print: 
```
G12A:BL:0253b8:61aa2d;FEAT:F0F821B0:12020;POC:D;RCY:0;USB:0;
```

In this mode, the device shows up on USB as: `1b8e:c003 Amlogic, Inc. GX-CHIP`

### Burn Mode
Amlogic devices have an `update` command in U-Boot which allows you to talk to the bootloader.
The UART console output will typicaly end with:
```
U-Boot 2015.01 (Jan 21 2022 - 08:55:34 - v1.0-57-gec3ec936c2)

DRAM:  512 MiB
Relocation Offset is: 16e42000
InUsbBurn
[MSG]sof
Set Addr 11
Get DT cfg
Get DT cfg
set CFG
``` 
Which indicates it is ready to receive commands

In this mode, the device shows up on USB as: `1b8e:c003 Amlogic, Inc.`

### Normal Bootup
If USB Burn mode is not enabled at every boot, or if you use `--continue_boot`, the device will boot up normally and launch the Spotify app.

In this mode, the device does not show up on USB (unless custom firmware has already been flashed).

### RAM Bootup with USB Gadget
If you use `--boot_adb_kernel`, a modified kernel and image will be written to RAM (non-persistent) and executed, which temporarily enables USB Gadget.

The USB Gadget is configured to provide `adb` (like an Android phone), among other possible functionality including `rndis` for usb networking.

In this mode, the device shows up on USB as: `18d1:4e40 Google Inc. Nexus 7 (fastboot)`

## Persistent USB Gadget with USB Networking
If you just want to enable ADB and USB Networking, we recommend flashing the Thing Labs firmware from [here.](https://thingify.tools/firmware/P3QZbZIDWnp5m_azQFQqP)

If you want to add ADB and USB Networking to an image from scratch, we have provided a script that will push all of the needed files over ADB. You can find it, along with documentation in the [scripts/usb-gadget](scripts/usb-gadget) folder.

This is a heavily modified version of what [frederic provided](https://github.com/frederic/superbird-bulkcmd/blob/main/scripts/enable-adb.sh.client)

## Example Usage

As an example (on Linux), here are steps to enable persistent adb and usbnet, disable a/b booting, and disable charger check, on a fresh device.

```
# starting from a fresh device

# plug in with buttons 1 & 4 held
sudo ./superbird_tool.py --find_device  # check that it is in usb mode
sudo ./superbird_tool.py --burn_mode
sudo ./superbird_tool.py --enable_burn_mode_button
sudo ./superbird_tool.py --disable_avb2 a # disable A/B, lock to A
sudo ./superbird_tool.py --disable_charger_check

# unplug and replug while holding button 4

sudo ./superbird_tool.py --find_device   # check that it is in usb burn mode
sudo ./superbird_tool.py --boot_adb_kernel a

# device boots to spotify logo, but app does not launch

adb devices  # check that your device shows up in adb

# setup persistent USB Gadget (adb and usbnet)
cd scripts/usb-gadget
./push_usbgadget.sh

# unplug and replug without holding any buttons
#   it should boot normally (app should launch), now with adb and usbnet enabled
adb devices # you should see your Car Things serial number
ip addr  # you should see usb0 listed
```

## Known Issues
* Sometimes flashing can fail mid flash, especially while flashing bigger partitions like `system`. If this happens, try running the command again but with `--slow_burn` before the `--restore-` flag. If you're still having issues, try `--slower_burn` instead. 
* Multiple people have reported issues with trying to use superbird-tool on AMD systems, specifically 5000 series systems. Sometimes a BIOS update can fix this issue but you may just need to use another computer.
* The option `--enable_uart_shell` is really only meant to be run on a fresh device. It will rewrite `initargs` env var, removing any other changes you made like using a particular system partition every boot.
  * The option `--disable_avb2` will ALSO enable the uart shell; consider using that instead.
* If you boot from USB mode into burn mode (using `--burn_mode`), `--boot_adb_kernel` won't work. This is due to u-boot not setting up some parts of the hardware.
* In some cases you might get a Timeout Error. This happens sometimes if a previous command failed, and you just need to power cycle the device (actually unplug and plug it back in), and try again. 
  * If you keep having timeout issues, try different USB cables and/or USB ports, including ports on USB hubs. The Car Thing has a slight hardware flaw that makes it very picky about what USB cables and ports actually work.


# Disclaimer
"Spotify", "Car Thing" and the Spotify logo are registered trademarks or trademarks of Spotify AB. Thing Labs is not affiliated with, endorsed by, or sponsored by Spotify AB. All other trademarks, service marks, and trade names are the property of their respective owners.
