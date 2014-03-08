// Cypress FX2 register definitions

typedef unsigned char BYTE;

// Special Function Registers
__sfr __at 0x80 IOA;
__sfr __at 0x90 IOB;
__sfr __at 0xB0 IOD;
__sfr __at 0xB2 OEA;
__sfr __at 0xB3 OEB;
__sfr __at 0xB5 OED;

// External RAM Registers
__xdata __at 0xE600 volatile BYTE CPUCS;
__xdata __at 0xE601 volatile BYTE IFCONFIG;
__xdata __at 0xE604 volatile BYTE FIFORESET;
__xdata __at 0xE60B volatile BYTE REVCTL;
__xdata __at 0xE612 volatile BYTE EP2CFG;
__xdata __at 0xE614 volatile BYTE EP6CFG;
__xdata __at 0xE618 volatile BYTE EP2FIFOCFG;
__xdata __at 0xE649 volatile BYTE OUTPKTEND;
__xdata __at 0xE670 volatile BYTE PORTACFG;
__xdata __at 0xE684 volatile BYTE USBFRAMEH;
__xdata __at 0xE685 volatile BYTE USBFRAMEL;
__xdata __at 0xE690 volatile BYTE EP2BCH;
__xdata __at 0xE691 volatile BYTE EP2BCL;
__xdata __at 0xE698 volatile BYTE EP6BCH;
__xdata __at 0xE699 volatile BYTE EP6BCL;
__xdata __at 0xE6A3 volatile BYTE EP2CS;
__xdata __at 0xE6A5 volatile BYTE EP6CS;

// Endpoint FIFO Buffers
__xdata __at 0xF000 volatile BYTE EP2FIFOBUF[1024];
__xdata __at 0xF800 volatile BYTE EP6FIFOBUF[1024];
