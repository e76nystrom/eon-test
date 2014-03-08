/*
 *usbpar_2.c -- FX2 USB Interface for the MSA.
 *
 * Copyright (c) 2006--2008 by Wolfgang Wieser ] wwieser (a) gmx <*> de [
 *
 * This file may be distributed and/or modified under the terms of the
 * GNU General Public License version 2 as published by the Free Software
 * Foundation. (See COPYING.GPL for details.)
 *
 * This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
 * WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
 *
 */

#define USBPAR_MAJOR_REV    0
#define USBPAR_MINOR_REV    1

#include <fx2regs2.h>

// Read TRM p.15-115 for an explanation on this.
// A single nop is sufficient for default setup but like that we're on
// the safe side.
#define NOP     __asm nop __endasm
#define SYNCDELAY   NOP; NOP; NOP; NOP
#define DELAY(n) for (len = n; len > 0; --len) NOP

// MSA "control" port bits
#define P1strobe 0x01    // latches data into port P1
#define P2strobe 0x02    // latches data into port P2
#define P3strobe 0x04    // latches data into port P3
#define P4strobe 0x08    // latches data into port P4

// MSA 'port' bits
#define P3_ADCONV   0x80
#define P3_ADSERCLK 0x40

#if 0
#define MAG   0x20
#define PHASE 0x10
#endif

static void InitializeUSB(void)
{
    CPUCS = 0x10;                  // 48 MHz, CLKOUT output disabled.

    IFCONFIG = 0xc0;               // Internal IFCLK, 48MHz; A,B as normal ports.
    SYNCDELAY;

    REVCTL = 0x03;                 // See TRM...
    SYNCDELAY;

    EP6CFG = 0xe2;                 // 1110 0010 (bulk IN, 512 bytes, double-buffered)
    SYNCDELAY;

    EP2CFG = 0xa2;                 // 1010 0010 (bulk OUT, 512 bytes, double-buffered)
    SYNCDELAY;

    FIFORESET = 0x80;  SYNCDELAY;  // NAK all requests from host.
    FIFORESET = 0x82;  SYNCDELAY;  // Reset individual EP (2,4,6,8)
    FIFORESET = 0x84;  SYNCDELAY;
    FIFORESET = 0x86;  SYNCDELAY;
    FIFORESET = 0x88;  SYNCDELAY;
    FIFORESET = 0x00;  SYNCDELAY;  // Resume normal operation.

    EP2FIFOCFG = 0x00;             // Make sure AUTOOUT=0.
    SYNCDELAY;

    // Be sure to clear the 2 buffers (double-buffered) (required!).
    OUTPKTEND = 0x82;  SYNCDELAY;
    OUTPKTEND = 0x82;  SYNCDELAY;
}

static void InitializePorts(void)
{
    // status port, port A
    PORTACFG = 0x00;
    OEA = 0x00;
    // data port, port B
    OEB = 0x00;
    OEB = 0xff;
    // control port, port D
    IOD = 0x0d;
    OED = 0x0f;
}

void main(void)
{
    __xdata BYTE *src;
    __xdata BYTE *dest;
    char cmd;
    BYTE arg1, len, byte;
    unsigned int inlen, outlen, frame;
#if 0
    unsigned short mag, phase;
#endif

    InitializeUSB();
    InitializePorts();

    dest = EP6FIFOBUF;
    outlen = 0;

    for (;;)
    {
        // Wait for input on EP2 (EP2 non-empty).
        if (!(EP2CS & (1 << 2)))
        {
            inlen = ((int)EP2BCH) << 8 | EP2BCL;
            src = EP2FIFOBUF;
            while (inlen > 0)
            {
                // dispatch on command byte
                cmd = *src++;
                arg1 = *src++;
                inlen -= 2;
                switch (cmd)
                {
                    case 'D': // Data port write
                        IOB = arg1;
                        break;

                    case 'C': // Control port write
                        IOD = arg1;
                        break;

                    case 'P': // PLL and DDC reg data out port P1
                        len = *src++;
                        inlen -= 1 + len;
                        for (; len > 0; len--)
                        {
                            byte = *src++;
                            IOB = byte;
                            IOD = P1strobe;
			    SYNCDELAY;
                            IOD = 0;
                            IOB = byte + arg1;
                            IOD = P1strobe;
			    SYNCDELAY;
                            IOD = 0;
                        }
                        break;

                    case 'W': // Wait given number of milliseconds, 1-255:
                        // read the 1-millisecond 11-bit USB Frame counter
                        frame = (USBFRAMEH << 8) + USBFRAMEL;
                        // and wait until it reaches our desired future time
                        frame = (frame + arg1) & 0x7ff;
                        while (((USBFRAMEH << 8) + USBFRAMEL) != frame)
                            ;
                        break;

                    case 'F': // Flush read buffer:
                        if (outlen > 0)
                        {
                            // Arm the endpoint. Be sure to set BCH before BCL because BCL access
                            // actually arms the endpoint.
                            SYNCDELAY;  EP6BCH = outlen >> 8;
                            SYNCDELAY;  EP6BCL = outlen & 0xff;
                            dest = EP6FIFOBUF;
                            outlen = 0;
                        }
                        break;

                    case 'S': // Status read:
                        // Wait for EP6 buffer to become non-full
                        while (EP6CS & (1 << 3))
                            ;
                        if (outlen > 512-2)
                        {
                            // EP6 buffer full: send it-- arm the endpoint
                            SYNCDELAY;  EP6BCH = outlen >> 8;
                            SYNCDELAY;  EP6BCL = outlen & 0xff;
                            dest = EP6FIFOBUF;
                            outlen = 0;
                        }
                        *dest++ = IOA;
                        *dest++ = arg1;
                        outlen += 2;
                        break;

                    case 'A': // ADC read:
                        // Wait for EP6 buffer to become non-full
                        while (EP6CS & (1 << 3))
                            ;
                        if (outlen > 512-arg1)
                        {
                            // EP6 buffer full: send it-- arm the endpoint
                            SYNCDELAY;  EP6BCH = outlen >> 8;
                            SYNCDELAY;  EP6BCL = outlen & 0xff;
                            dest = EP6FIFOBUF;
                            outlen = 0;
                        }
                        outlen += arg1;
                        IOB = P3_ADCONV;
                        IOD = P3strobe;
			DELAY(15);
			IOB = 0;
			DELAY(3);
			byte = 0xf;
                        for (; arg1 > 0; arg1--)
                        {
                            IOB = P3_ADSERCLK;
			    byte |= IOA & 0x30;
                            *dest++ = byte;
			    byte = arg1 & 0x7;
			    IOB = 0;
			    DELAY(5);
                        }
			NOP;
			IOD = 0;
                        break;

                    case 'V': // Version of code
                        // Wait for EP6 buffer to become non-full
                        while (EP6CS & (1 << 3))
                            ;
                        if (outlen > 512-2)
                        {
                            // EP6 buffer full: send it-- arm the endpoint
                            SYNCDELAY;  EP6BCH = outlen >> 8;
                            SYNCDELAY;  EP6BCL = outlen & 0xff;
                            dest = EP6FIFOBUF;
                            outlen = 0;
                        }
                        // send 2-byte version number
                        *dest++ = USBPAR_MAJOR_REV;
                        *dest++ = USBPAR_MINOR_REV;
                        outlen += 2;
                        break;

                    default:
                        break;
                }
            }
            // "Skip" the received OUT packet to "forget" it (see TRM p. 9-26):
            SYNCDELAY;  OUTPKTEND = 0x82;
        }
    }
}
