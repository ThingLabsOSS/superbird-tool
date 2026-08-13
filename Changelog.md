# Changelog

## Unreleased

Shipped on `main` since 0.2.0. `VERSION` in `superbird_tool.py` still reads
`0.2.0` — bump it when these are cut as a release.

* Added `--chainload BINFILE` — load an aarch64 binary into RAM from burn mode
  and `go` to it. `--load_addr ADDR` overrides the default `0x01080000`.
* `--burn_mode` now takes an optional `CUSTOM_FIP` path, RAM-loading a custom
  signed FIP body instead of vendor burn-mode u-boot. The FIP must be signed
  with a key matching the SoC's fused ROM key hash.
* Added fast partition dump/restore via the upload/download-store path, now the
  default. `--legacy_transfer` forces the old `amlmmc` read/write path.
  `--slow_burn` / `--slower_burn` also force the legacy path.
* `--restore_partition` auto-strips a leading info_sector when writing the
  bootloader partition, so a full boot-partition image can be restored directly.
* `--burn_mode` polls for u-boot readiness after `bl2_boot` instead of racing it.
* `stock_env.txt` is now located independently of the current working directory.
* Root is no longer required (see the udev rule in the Readme).


## 0.2.0
* Added `--bulkcmd_shell`

## 0.1.9
* Now runs `amlmmc env` before trying to read env

## 0.1.8
* Small change to --dont_reset command. Sets firstboot to 0 to ensure erases don't happen

## 0.1.7
* Added `--slow_burn` and `--slower_burn` to slow down restore speed. This can help in cases where flashing fails in the middle of
bigger partitions.

## 0.1.6
* Increased flashing speed
* Improved readability
* Updated documentation

## 0.1.5
* Change the flashing logic to trigger the standard factory reset behavior to avoid a corrupted data/settings partition
  * Added `--dont_reset` option to skip the factory reset step when doing `--restore_device`

## 0.1.4
* Introduced DHCP server and client over RNDIS - Refer to [scripts/usb-gadget/README.md](scripts/usb-gadget/README.md)
  * Rewrote S49usbgadget
  * Added supporting files
  * setup_host_usbnet.sh is now deprecated

## 0.1.3
* `--burn_mode`
  * Fixed --burn_mode bug causing false positive error message
  * Added message when using --burn_mode while in Burn Mode
* Housekeeping
  * Added 0.1.0 to Changelog
  * Updated CLI attribution message, added Car-Thing-Hax-Community name/repo link and specified using fork from bishopdynamics in cli output

## 0.1.1 & 0.1.2
* Made some changes to the flashing logic to account for missing/misnamed files

## 0.1.0 [f371ff7](https://github.com/bishopdynamics/superbird-tool/tree/f371ff715ee4b0ba4f689d9785a7513731242d38)
* Latest @bishopdynamics release, no official changelog available

## 0.0.8
* fix rare divide-by-zero case when reading or writing partitions
* tweaked how experimental `make-binary.sh` works

## 0.0.7
* reduced write single-chunk threshold to 2MB, seems 4MB was too ambitious to be reliable

## 0.0.6
* options that require USB Burn Mode will now attempt to enter USB Burn Mode automatically
* added `--restore_partition` to restore individual partitions from file
* added `--restore_device` to restore whole device from a folder
  * expects files: `bootloader.dump, env.dump, fip_a.dump, fip_b.dump, logo.dump, dtbo_a.dump, dtbo_b.dump, vbmeta_a.dump, vbmeta_b.dump, boot_a.dump, boot_b.dump, misc.dump, settings.ext4, system_a.ext2, system_b.ext2`
  * if the dump file `data.ext4` is missing, or is actually empty (all zeros), will just wipe the data partition to save time
* corrected `bootloader` partition size. 
  * The partition is 4MB, but device will only accept up to 2MB when writing
  * partition is zero-padded and the actual bootloader is about 1.3MB
  * starting with this version, `--dump_partition` and `--dump_device` will produce 2MB dumps of `bootloader` partition
  * `--restore_partition` and `--restore_device`, if they find a 4MB `bootloader.dump` will only restore first 2MB of it
* fixed issue where `bootloader` dumps started with 512 Bytes of padding
* option `--dump_device` will convert `env.dump` into `env.txt` (keeping both)

## 0.0.5
* Added boot slot selection to `--boot_adb_kernel` & `--disable_avb`.

## 0.0.4
* fixed #2 & #4 - wrong encoding when sending env to device

## 0.0.3
* added `--enable_burn_mode_button` thanks to lmore337!

## 0.0.2 November 1, 2022

* added `--restore_stock_env` - wipe uboot env partition, then restore it to stock values by importing `stock_env.txt`
* added `--send_env` <env.txt> - send given `env.txt`, import it into the existing env. Will NOT wipe first, just overwrite
* added `--send_full_env` <env.txt> - wipe uboot env partition, then import the given `env.txt`
* added `--convert_env_dump` <env.dump> - convert a partition dump file, into a readable `env.txt` which you can edit
* added `--get_env` <env.txt> - dump the device env partition and convert it to `env.txt` 


## 0.0.1 - October 20, 2022
* initial release
* fixed issue #1: not sending env with --boot_adb_kernel