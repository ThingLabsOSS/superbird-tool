# Tiny aarch64 binary that prints a banner over the AMLogic UART then halts.
# Used as a smoke test for the --chainload path in superbird_tool.
#
# Needs `binutils-aarch64-linux-gnu` (Debian) — no C compiler required.

PREFIX  ?= aarch64-linux-gnu-
AS      := $(PREFIX)as
LD      := $(PREFIX)ld
OBJCOPY := $(PREFIX)objcopy

# Default load address matches superbird_device.SuperbirdDevice.ADDR_KERNEL.
# Code is PC-relative so this can change without rebuilding, but we pin it
# anyway for clarity.
LOAD_ADDR ?= 0x01080000

.PHONY: all clean

all: hello.bin

hello.o: hello.S
	$(AS) -o $@ $<

hello.elf: hello.o
	$(LD) -Ttext=$(LOAD_ADDR) -o $@ $<

hello.bin: hello.elf
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f hello.o hello.elf hello.bin
