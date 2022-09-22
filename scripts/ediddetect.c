/******************************************************************************
 *
 * Copyright (C) 2009 - 2014 Xilinx, Inc.  All rights reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * Use of the Software is limited solely to applications:
 * (a) running on a Xilinx device, or
 * (b) that interact with a Xilinx device through a bus or interconnect.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * XILINX  BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF
 * OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 * Except as contained in this notice, the name of the Xilinx shall not be used
 * in advertising or otherwise to promote the sale, use or other dealings in
 * this Software without prior written authorization from Xilinx.
 *
 ******************************************************************************/

/*
 * helloworld.c: simple test application
 *
 * This application configures UART 16550 to baud rate 9600.
 * PS7 UART (Zynq) is not initialized by this application, since
 * bootrom/bsp configures it to baud rate 115200
 *
 * ------------------------------------------------
 * | UART TYPE   BAUD RATE                        |
 * ------------------------------------------------
 *   uartns550   9600
 *   uartlite    Configurable only in HW design
 *   ps7_uart    115200 (configured by bootrom/bsp)
 */

#include <stdio.h>
#include "platform.h"
#include "xil_printf.h"
#include "xil_exception.h"
#include "xparameters.h"
#include "xiicps.h"
#include "xscugic.h"

/************************** Constant Definitions ******************************/

/*
 * The following constants map to the XPAR parameters created in the
 * xparameters.h file. They are defined here such that a user can easily
 * change all the needed parameters in one place.
 */
#define IIC_DEVICE_ID		XPAR_XIICPS_0_DEVICE_ID
#define INTC_DEVICE_ID		XPAR_SCUGIC_SINGLE_DEVICE_ID
#define IIC_INT_VEC_ID		XPAR_XIICPS_0_INTR

XIicPs Iic;
XScuGic InterruptController;
u32 LastEvent = 0;
u8 RxBuf[128];

void Handler(void *CallBackRef, u32 Event) {
	LastEvent = Event;
}

s32 EdidReadAddr(u8 UseEddc, u8 SegmentPointer, u8 DdcWordOffset, u8 DdcReadLength, u8* RxBuf, u8 IicAddress) {

	XIicPs_SetOptions(&Iic, XIICPS_REP_START_OPTION);
	if (IicAddress == 0x50 && UseEddc) {

		LastEvent = 0;
		XIicPs_MasterSend(&Iic, &SegmentPointer, 1, 0x30);
		while (LastEvent == 0) {
			;
		}

		if (!(LastEvent & XIICPS_EVENT_COMPLETE_SEND)) {
			xil_printf("Error writing segment pointer : Event %04x\r\n", LastEvent);
		}
	}

	LastEvent = 0;
	XIicPs_MasterSend(&Iic, &DdcWordOffset, 1, IicAddress);
	while (LastEvent == 0) {
		;
	}
	if (!(LastEvent & XIICPS_EVENT_COMPLETE_SEND)) {
				xil_printf("Error writing word offset : Event %04x\r\n", LastEvent);
				return XST_FAILURE;
			}

	XIicPs_ClearOptions(&Iic, XIICPS_REP_START_OPTION);
	LastEvent = 0;
	XIicPs_MasterRecv(&Iic, RxBuf, DdcReadLength, IicAddress);
	while (LastEvent == 0) {
		;
	}
	if (!(LastEvent & XIICPS_EVENT_COMPLETE_RECV)) {
		xil_printf("Error reading Edid : Event %04x\r\n", LastEvent);
		return XST_FAILURE;
	}

	return XST_SUCCESS;
}

s32 EdidRead(u8 UseEddc, u8 SegmentPointer, u8 DdcWordOffset, u8 DdcReadLength, u8* RxBuf) {
	return EdidReadAddr(UseEddc, SegmentPointer, DdcWordOffset, DdcReadLength, RxBuf, 0x50);
}

int main() {
	init_platform();

	int Status;
	xil_printf("IIC Master Interrupt Example Test \r\n");

	XIicPs_Config *Config;
	Config = XIicPs_LookupConfig(IIC_DEVICE_ID);
	Status = XIicPs_CfgInitialize(&Iic, Config, Config->BaseAddress);
	Status = XIicPs_SelfTest(&Iic);
	xil_printf("SCLK: %u\r\n", XIicPs_GetSClk(&Iic));
	Status = XIicPs_SetSClk(&Iic, 100000); // Slow down

	// Set up interrupt system
	XScuGic_Config *IntcConfig;
	Xil_ExceptionInit(); // Exception is lowest level

	IntcConfig = XScuGic_LookupConfig(INTC_DEVICE_ID);

	Status = XScuGic_CfgInitialize(&InterruptController, IntcConfig,
			IntcConfig->CpuBaseAddress);

	Status = XScuGic_SelfTest(&InterruptController);

	Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_IRQ_INT,
			(Xil_ExceptionHandler) XScuGic_InterruptHandler,
			&InterruptController);
	// Attach IRQ to interrupt controller

	Status = XScuGic_Connect(&InterruptController, IIC_INT_VEC_ID,
			(Xil_InterruptHandler) XIicPs_MasterInterruptHandler, &Iic);

	XScuGic_Enable(&InterruptController, IIC_INT_VEC_ID);

	Xil_ExceptionEnable()
	;

	XIicPs_SetStatusHandler(&Iic, &Iic, Handler);

	// IicDetect
	for (int IicAddr = 3; IicAddr <= 0x77; IicAddr++) {
		LastEvent = 0;
		XIicPs_MasterRecv(&Iic, RxBuf, 128, IicAddr);
		while (LastEvent == 0) {
			;
		}
		xil_printf("Addr 0x%02x : Event %04x\r\n", IicAddr, LastEvent);
	}

	LastEvent = 0;
		XIicPs_MasterRecv(&Iic, RxBuf, 128, 0x50);
		while (LastEvent == 0) {
			;
		}
	if (LastEvent & XIICPS_EVENT_ERROR) {
		xil_printf("Edid not detected. Event %04x\r\n", LastEvent);
	} else {
		xil_printf("Edid detected on 0x50\r\n");
	}

	Status = EdidRead(0, 0, 0, 128, RxBuf);

	for (int ByteIndex = 0; ByteIndex < 128; ByteIndex++) {
		xil_printf("%02x ", RxBuf[ByteIndex]);
		if ((ByteIndex + 1) % 16 == 0) {
			xil_printf("\r\n");
		}
	}

	if (RxBuf[126] != 0) {
		xil_printf("EDID extension blocks supported. Count = %u\r\n", RxBuf[126]);
	}

	Status = EdidRead(0, 0, 128, 128, RxBuf);

	for (int ByteIndex = 0; ByteIndex < 128; ByteIndex++) {
		xil_printf("%02x ", RxBuf[ByteIndex]);
		if ((ByteIndex + 1) % 16 == 0) {
			xil_printf("\r\n");
		}
	}


	LastEvent = 0;
		XIicPs_MasterRecv(&Iic, RxBuf, 128, 0x50);
		while (LastEvent == 0) {
			;
		}
	if (LastEvent & XIICPS_EVENT_ERROR) {
		xil_printf("SCDC not detected. Event %04x\r\n", LastEvent);
	} else {
		xil_printf("SCDC detected on 0x54\r\n");
	}

	Status = EdidReadAddr(0, 0, 0, 128, RxBuf, 0x54);

	for (int ByteIndex = 0; ByteIndex < 128; ByteIndex++) {
		xil_printf("%02x ", RxBuf[ByteIndex]);
		if ((ByteIndex + 1) % 16 == 0) {
			xil_printf("\r\n");
		}
	}

	Status = EdidReadAddr(0, 0, 128, 128, RxBuf, 0x54);

	for (int ByteIndex = 0; ByteIndex < 128; ByteIndex++) {
		xil_printf("%02x ", RxBuf[ByteIndex]);
		if ((ByteIndex + 1) % 16 == 0) {
			xil_printf("\r\n");
		}
	}

	cleanup_platform();
	return 0;
}

/* Result from asus mon
 * Edid detected on 0x50
00 FF FF FF FF FF FF 00 06 B3 CC 23 01 01 01 01
24 1C 01 03 80 33 1D 78 EA D9 05 A5 57 51 9E 27
0F 50 54 AF CF 80 71 4F 81 80 81 8F B3 00 81 40
95 00 A9 40 8B C0 02 3A 80 18 71 38 2D 40 58 2C
45 00 FD 1E 11 00 00 1E 00 00 00 FD 00 30 4C 1E
55 11 00 0A 20 20 20 20 20 20 00 00 00 FC 00 56
5A 32 33 39 0A 20 20 20 20 20 20 20 00 00 00 FF
00 4A 39 4C 4D 52 53 30 30 38 34 33 35 0A 01 3E
EDID extension blocks supported. Count = 1
02 03 1D F1 4A 90 04 03 01 14 12 05 1F 10 13 23
09 07 07 83 01 00 00 65 03 0C 00 10 00 02 3A 80
18 71 38 2D 40 58 2C 45 00 FD 1E 11 00 00 1E 01
1D 80 18 71 1C 16 20 58 2C 25 00 FD 1E 11 00 00
9E 01 1D 00 72 51 D0 1E 20 6E 28 55 00 FD 1E 11
00 00 1E 8C 0A D0 8A 20 E0 2D 10 10 3E 96 00 FD
1E 11 00 00 18 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 FA
 *
 */

/* Result from fake dongle (works at megahertz rates lol)
 * Edid detected on 0x50
00 FF FF FF FF FF FF 00 61 A4 9A 00 00 00 00 00
27 1B 01 03 80 3C 22 78 0A CF 74 A3 57 4C B0 23
09 48 4C 21 08 00 81 80 81 00 61 40 95 00 A9 C0
B3 00 A9 40 D1 00 02 3A 80 18 71 38 2D 40 58 2C
45 00 E0 0E 11 00 00 1E 3C 41 40 96 B0 08 24 70
1E 0A 48 04 D0 C2 21 00 00 1E 00 00 00 FC 00 4D
69 20 54 56 0A 20 20 20 20 20 20 20 00 00 00 FD
00 31 50 0F 8C 3C 00 0A 20 20 20 20 20 20 01 D7
EDID extension blocks supported. Count = 1
02 03 3B 71 4F 5F 03 04 05 64 90 12 13 14 16 20
21 22 1F 3F 29 09 07 07 11 17 50 51 07 00 83 01
00 00 6E 03 0C 00 30 00 F8 76 20 80 80 01 02 03
04 E5 0E 60 61 65 66 E3 06 05 01 E2 68 00 A0 A0
40 2E 60 30 20 36 00 80 90 21 00 00 1E 56 5E 00
A0 A0 A0 29 50 30 20 36 00 80 68 21 00 00 1E 66
21 56 AA 51 00 1E 30 46 8F 33 00 55 C0 10 00 00
1E 00 00 00 00 00 00 00 00 00 00 00 00 00 00 F2
 */

/* LG tv hdmi input
 * Edid detected on 0x50
00 FF FF FF FF FF FF 00 1E 6D C8 C0 01 01 01 01
01 1F 01 03 80 A0 5A 78 0A EE 91 A3 54 4C 99 26
0F 50 54 A1 08 00 31 40 45 40 61 40 71 40 81 80
D1 C0 01 01 01 01 08 E8 00 30 F2 70 5A 80 B0 58
8A 00 40 84 63 00 00 1E 6F C2 00 A0 A0 A0 55 50
30 20 35 00 40 84 63 00 00 1E 00 00 00 FD 00 18
78 1E FF 77 00 0A 20 20 20 20 20 20 00 00 00 FC
00 4C 47 20 54 56 20 53 53 43 52 32 0A 20 01 65
EDID extension blocks supported. Count = 1
02 03 64 F1 5E 61 60 76 75 66 65 DB DA 10 1F 04
13 05 14 03 02 12 20 21 22 15 01 5D 5E 5F 62 63
64 3F 40 2C 09 57 07 15 07 50 57 07 01 67 04 03
6E 03 0C 00 20 00 B8 3C 2C 00 80 01 02 03 04 6A
D8 5D C4 01 78 80 5B 02 28 78 E2 00 CF E3 05 C0
00 E3 06 0D 01 E2 0F FF EB 01 46 D0 00 48 03 76
82 5E 6D 95 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1A

Supports PQ and HLG in DRMIF
CTA-861 contains info frame definitions
Ref HDMI 1.4 for deep color packing
TMDS clock is pixel clock (say 165 MHz)
Speed increases if deep color is used
Need to implement general control packet
*/
