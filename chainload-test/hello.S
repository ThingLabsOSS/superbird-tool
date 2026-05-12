// Minimal aarch64 "hello from chainload" smoke test for Spotify Car Thing.
//
// Pumps a banner string out the AMLogic UART at 0xff803000 (the one already
// wired up to /dev/ttyUSB0 via the FTDI header), then halts on WFE so we
// don't fly off into stale RAM. Position-independent (uses ADR for the
// string) so it doesn't matter what address we load to — though by default
// we use 0x01080000 (existing ADDR_KERNEL slot in superbird_tool).
//
// AMLogic UART register layout (from drivers/tty/serial/meson_uart.c):
//   +0x00  WFIFO   write byte to TX
//   +0x0c  STATUS  bit 21 = TX_FULL (must wait for clear before writing)

    .section .text
    .global _start

_start:
    // x0 = AML_UART base 0xff803000
    movz    x0, #0xff80, lsl #16
    movk    x0, #0x3000

    // x1 = pointer to message
    adr     x1, message

send_loop:
    ldrb    w2, [x1], #1            // load + post-increment
    cbz     w2, halt                // NUL = done

wait_tx:
    ldr     w3, [x0, #0x0c]         // STATUS
    tbnz    w3, #21, wait_tx        // spin while TX_FULL
    str     w2, [x0]                // WFIFO ← char
    b       send_loop

halt:
    wfe
    b       halt

message:
    .ascii  "\r\n"
    .ascii  "===========================================\r\n"
    .ascii  "  HELLO FROM CUSTOM CHAINLOAD (aarch64)\r\n"
    .ascii  "===========================================\r\n"
    .byte   0
