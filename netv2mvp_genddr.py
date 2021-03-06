#!/usr/bin/env python3

# lxbuildenv must be imported first, because it has a chance to re-exec Python.
# This module ensures the dependencies are present and the environment variables
# are all set appropriately.  Additionally, the PATH will include toolchains,
# and all dependencies get verified.
import lxbuildenv

# This variable defines all the external programs that this module
# relies on.  lxbuildenv reads this variable in order to ensure
# the build will finish without exiting due to missing third-party
# programs.
LX_DEPENDENCIES = ["riscv", "vivado"]

import sys
import os
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, VivadoProgrammer

from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, xadc
from litex.soc.cores.frequency_meter import FrequencyMeter

from litedram.modules import K4B2G1646FBCK0
from litedram.phy import a7ddrphy
from litedram.core import ControllerSettings

from litevideo.input import HDMIIn
from litevideo.output.hdmi.s7 import S7HDMIOutEncoderSerializer, S7HDMIOutPHY

from litevideo.output.common import *
from litevideo.output.core import VideoOutCore
from litevideo.output.hdmi.encoder import Encoder

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *

from liteeth.common import *

from migen.genlib.cdc import MultiReg

from litex.soc.cores import spi_flash
from litex.soc.integration.soc_core import mem_decoder

_io = [
    ("clk50", 0, Pins("J19"), IOStandard("LVCMOS33")),

    ("fpga_led0", 0, Pins("M21"), IOStandard("LVCMOS33")),
    ("fpga_led1", 0, Pins("N20"), IOStandard("LVCMOS33")),
    ("fpga_led2", 0, Pins("L21"), IOStandard("LVCMOS33")),
    ("fpga_led3", 0, Pins("AA21"), IOStandard("LVCMOS33")),
    ("fpga_led4", 0, Pins("R19"), IOStandard("LVCMOS33")),
    ("fpga_led5", 0, Pins("M16"), IOStandard("LVCMOS33")),
    ("fan_pwm", 0, Pins("L14"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("E14")),
        Subsignal("rx", Pins("E13")),
        IOStandard("LVCMOS33"),
    ),

    ("serial", 1,
        Subsignal("tx", Pins("B17")), # hax 7
        Subsignal("rx", Pins("A18")), # hax 8
        IOStandard("LVCMOS33")
    ),

    ("pcie_x1", 0,
        Subsignal("rst_n", Pins("E18"), IOStandard("LVCMOS33")),
        Subsignal("clk_p", Pins("F10")),
        Subsignal("clk_n", Pins("E10")),
        Subsignal("rx_p", Pins("D11")),
        Subsignal("rx_n", Pins("C11")),
        Subsignal("tx_p", Pins("D5")),
        Subsignal("tx_n", Pins("C5"))
    ),

    ("pcie_x2", 0,
        Subsignal("rst_n", Pins("E18"), IOStandard("LVCMOS33")),
        Subsignal("clk_p", Pins("F10")),
        Subsignal("clk_n", Pins("E10")),
        Subsignal("rx_p", Pins("D11 B10")),
        Subsignal("rx_n", Pins("C11 A10")),
        Subsignal("tx_p", Pins("D5 B6")),
        Subsignal("tx_n", Pins("C5 A6"))
    ),

    ("pcie_x4", 0,
        Subsignal("rst_n", Pins("E18"), IOStandard("LVCMOS33")),
        Subsignal("clk_p", Pins("F10")),
        Subsignal("clk_n", Pins("E10")),
        Subsignal("rx_p", Pins("D11 B10 D9 B8")),
        Subsignal("rx_n", Pins("C11 A10 C9 A8")),
        Subsignal("tx_p", Pins("D5 B6 D7 B4")),
        Subsignal("tx_n", Pins("C5 A6 C7 A4"))
    ),

    ("hdmi_in", 0,
        Subsignal("clk_p", Pins("L19"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("clk_n", Pins("L20"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data0_p", Pins("K21"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data0_n", Pins("K22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data1_p", Pins("J20"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data1_n", Pins("J21"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data2_p", Pins("J22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data2_n", Pins("H22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("scl", Pins("T18"), IOStandard("LVCMOS33")),
        Subsignal("sda", Pins("V18"), IOStandard("LVCMOS33")),
        Subsignal("hpd_notif", Pins("U17"), IOStandard("LVCMOS33"), Inverted()),  # HDMI_HPD_LL_N (note active low)
    ),

    # Use this block if connecting a normal HDMI cable to the overlay port
    # ("hdmi_in", 1,
    #     Subsignal("clk_p", Pins("Y18"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("clk_n", Pins("Y19"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("data0_p", Pins("AA18"), IOStandard("TMDS_33")),
    #     Subsignal("data0_n", Pins("AB18"), IOStandard("TMDS_33")),
    #     Subsignal("data1_p", Pins("AA19"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("data1_n", Pins("AB20"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("data2_p", Pins("AB21"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("data2_n", Pins("AB22"), IOStandard("TMDS_33"), Inverted()),
    #     Subsignal("scl", Pins("W17"), IOStandard("LVCMOS33"), Inverted()),
    #     Subsignal("sda", Pins("R17"), IOStandard("LVCMOS33")),
    # ),

    # Use this block if connecting the M2M jumper to the Raspberry Pi
    # All pairs inverted to simplify/clean-up routing between the two boards
    ("hdmi_in", 1,
     Subsignal("clk_p", Pins("Y18"), IOStandard("TMDS_33")),
     Subsignal("clk_n", Pins("Y19"), IOStandard("TMDS_33")),
     Subsignal("data0_p", Pins("AA18"), IOStandard("TMDS_33"), Inverted()),
     Subsignal("data0_n", Pins("AB18"), IOStandard("TMDS_33"), Inverted()),
     Subsignal("data1_p", Pins("AA19"), IOStandard("TMDS_33")),
     Subsignal("data1_n", Pins("AB20"), IOStandard("TMDS_33")),
     Subsignal("data2_p", Pins("AB21"), IOStandard("TMDS_33")),
     Subsignal("data2_n", Pins("AB22"), IOStandard("TMDS_33")),
     Subsignal("scl", Pins("W17"), IOStandard("LVCMOS33"), Inverted()),
     Subsignal("sda", Pins("R17"), IOStandard("LVCMOS33")),
     ),

    ("hdmi_out", 0,
        Subsignal("clk_p", Pins("W19"), Inverted(), IOStandard("TMDS_33")),
        Subsignal("clk_n", Pins("W20"), Inverted(), IOStandard("TMDS_33")),
        Subsignal("data0_p", Pins("W21"), IOStandard("TMDS_33")),
        Subsignal("data0_n", Pins("W22"), IOStandard("TMDS_33")),
        Subsignal("data1_p", Pins("U20"), IOStandard("TMDS_33")),
        Subsignal("data1_n", Pins("V20"), IOStandard("TMDS_33")),
        Subsignal("data2_p", Pins("T21"), IOStandard("TMDS_33")),
        Subsignal("data2_n", Pins("U21"), IOStandard("TMDS_33"))
    ),

    ("hdmi_out", 1,
        Subsignal("clk_p", Pins("G21"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("clk_n", Pins("G22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data0_p", Pins("E22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data0_n", Pins("D22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data1_p", Pins("C22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data1_n", Pins("B22"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data2_p", Pins("B21"), IOStandard("TMDS_33"), Inverted()),
        Subsignal("data2_n", Pins("A21"), IOStandard("TMDS_33"), Inverted()),
    ),

    ("hdmi_sda_over_up", 0, Pins("G20"), IOStandard("LVCMOS33")),
    ("hdmi_sda_over_dn", 0, Pins("F20"), IOStandard("LVCMOS33")), # must be mutex with the above

    ("hdmi_rx0_forceunplug", 0, Pins("M22"), IOStandard("LVCMOS33")), # forces an HPD on the RX0/TX0 path
    ("hdmi_rx0_forceplug", 0, Pins("N22"), IOStandard("LVCMOS33")),   # this needs to be mutex with the above

    ("hdmi_tx1_hpd_n", 0, Pins("U18"), IOStandard("LVCMOS33")),  # this is the internal hdmi-D port

    ("hdmi_tx1_cec", 0, Pins("P17"), IOStandard("LVCMOS33")),  # tx1/rx1 path
    ("hdmi_tx0_cec", 0, Pins("P20"), IOStandard("LVCMOS33")),  # tx0/rx0 path

    ("hdmi_ov0_cec", 0, Pins("P19"), IOStandard("LVCMOS33")),  # dedicated to the overlay input
    ("hdmi_ov0_hpd_n", 0, Pins("V17"), IOStandard("LVCMOS33")), # if the overlay input is plugged in

    # RMII PHY Pads
    ("rmii_eth_clocks", 0,
     Subsignal("ref_clk", Pins("D17"), IOStandard("LVCMOS33"))
     ),
    ("rmii_eth", 0,
     Subsignal("rst_n", Pins("F16"), IOStandard("LVCMOS33")),
     Subsignal("rx_data", Pins("A20 B18"), IOStandard("LVCMOS33")),
     Subsignal("crs_dv", Pins("C20"), IOStandard("LVCMOS33")),
     Subsignal("tx_en", Pins("A19"), IOStandard("LVCMOS33")),
     Subsignal("tx_data", Pins("C18 C19"), IOStandard("LVCMOS33")),
     Subsignal("mdc", Pins("F14"), IOStandard("LVCMOS33")),
     Subsignal("mdio", Pins("F13"), IOStandard("LVCMOS33")),
     Subsignal("rx_er", Pins("B20"), IOStandard("LVCMOS33")),
     Subsignal("int_n", Pins("D21"), IOStandard("LVCMOS33")),
     ),

    # SPI Flash
    ("spiflash_4x", 0,  # clock needs to be accessed through STARTUPE2
     Subsignal("cs_n", Pins("T19")),
     Subsignal("dq", Pins("P22", "R22", "P21", "R21")),
     IOStandard("LVCMOS33")
     ),
    ("spiflash_1x", 0,  # clock needs to be accessed through STARTUPE2
     Subsignal("cs_n", Pins("T19")),
     Subsignal("mosi", Pins("P22")),
     Subsignal("miso", Pins("R22")),
     Subsignal("wp", Pins("P21")),
     Subsignal("hold", Pins("R21")),
     IOStandard("LVCMOS33")
     ),
]


class Platform(XilinxPlatform):
    def __init__(self, toolchain="vivado", programmer="vivado", part="35"):
        part = "xc7a" + part + "t-fgg484-2"
        XilinxPlatform.__init__(self, part, _io,
                                toolchain=toolchain)

        # NOTE: to do quad-SPI mode, the QE bit has to be set in the SPINOR status register
        # OpenOCD won't do this natively, have to find a work-around (like using iMPACT to set it once)
        self.add_platform_command(
            "set_property CONFIG_VOLTAGE 3.3 [current_design]")
        self.add_platform_command(
            "set_property CFGBVS VCCO [current_design]")
        self.add_platform_command(
            "set_property BITSTREAM.CONFIG.CONFIGRATE 66 [current_design]")
        self.add_platform_command(
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 2 [current_design]")
        self.toolchain.bitstream_commands = [
            "set_property CONFIG_VOLTAGE 3.3 [current_design]",
            "set_property CFGBVS VCCO [current_design]",
            "set_property BITSTREAM.CONFIG.CONFIGRATE 66 [current_design]",
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 2 [current_design]",
        ]
        self.toolchain.additional_commands = \
            ["write_cfgmem -verbose -force -format bin -interface spix2 -size 64 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer

    def create_programmer(self):
        if self.programmer == "vivado":
            return VivadoProgrammer(flash_part="n25q128-3.3v-spi-x1_x2_x4")
        else:
            raise ValueError("{} programmer is not supported"
                             .format(self.programmer))

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)


def csr_map_update(csr_map, csr_peripherals):
    csr_map.update(dict((n, v)
        for v, n in enumerate(csr_peripherals, start=max(csr_map.values()) + 1)))


def period_ns(freq):
    return 1e9/freq

# valid values are 200e6, 300e6, and 400e6
iodelay_clk_freq = int(300e6)  # set for multiple functions, valid values are 200e6 and 400e6

class CRG(Module, AutoCSR):
    def __init__(self, platform, use_ss=False, dqs_phase=112.5): # dqs_phase is multiple of 22.50
        # DRP
        self._mmcm_read = CSR()
        self._mmcm_write = CSR()
        self._mmcm_drdy = CSRStatus()
        self._mmcm_adr = CSRStorage(7)
        self._mmcm_dat_w = CSRStorage(16)
        self._mmcm_dat_r = CSRStatus(16)

        # use_ss when True enables spread spectrum clocking
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_ac = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys2x = ClockDomain()
        self.clock_domains.cd_delayrefclk = ClockDomain()

        self.clock_domains.cd_eth = ClockDomain()

        clk50 = platform.request("clk50")
        rst = Signal()

        pll_locked = Signal()
        slave_locked = Signal()
        pll_fb = Signal()
        self.pll_sys = Signal()
        pll_sys4x = Signal()
        pll_sys4x_dqs = Signal()
        pll_clk200 = Signal()
        pll_clk50 = Signal()
        clk50_distbuf = Signal()

        self.specials += [
            Instance("BUFG", i_I=clk50, o_O=clk50_distbuf), # this allows PLLs/MMCMEs to be placed anywhere and reference the input clock
        ]

        refclk_freq = 50e6
        if iodelay_clk_freq == int(400e6) or iodelay_clk_freq == int(200e6):
            clkfbout_mult = 16
        elif iodelay_clk_freq == int(300e6):
            clkfbout_mult = 12

        print("Using dqsphase argument of " + str(dqs_phase))

        if use_ss == False:
            pll_fb_bufg = Signal()
            mmcm_rhs_fb_d = Signal()
            mmcm_rhs_fb_d_g = Signal()
            mmcm_rhs_fb_ac = Signal()
            mmcm_rhs_fb_ac_g = Signal()
            delayrefclk = Signal()
            pll_sys2x = Signal()
            pll_sys2x_route = Signal()
            pll_sys4x_ac = Signal()
            mmcm_drdy = Signal()
            self.specials += [
                # This PLL could be merged into the _ac MMCME2, but it's separated because we have the extra PLLs
                # and it allows us to set different bandwidths for the oscillator to optimize the jitter profiles
                Instance("PLLE2_BASE",
                         p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,
                         p_BANDWIDTH="LOW",  # HIGH minimizes VCO-origin jitter, at expense of transferred jitter from clock reference
                         # LOW maximizes input jitter filtering at expense of greater static phase offsets

                         # VCO @ 1200 MHz per clocking wizard
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=(1/refclk_freq)*1e9,
                         p_CLKFBOUT_MULT=24, p_DIVCLK_DIVIDE=1,
                         i_CLKIN1=clk50_distbuf, i_CLKFBIN=pll_fb_bufg, o_CLKFBOUT=pll_fb,

                         # based on iodelay_clk_freq
                         p_CLKOUT0_DIVIDE=refclk_freq*24/iodelay_clk_freq, p_CLKOUT0_PHASE=0.0,
                         o_CLKOUT0=delayrefclk,
                         ),
                
                # these generators should be on the right hand side (closest to DDR memory IOs)
                # This MMCME2 generates clocks for the data/dqs pins, closely coupled via BUFIOs
                Instance("MMCME2_ADV",
                         p_STARTUP_WAIT="FALSE", o_LOCKED=slave_locked,
                         p_BANDWIDTH="OPTIMIZED",

                         # VCO @ 800 MHz or 600 MHz
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=(1/refclk_freq)*1e9,
                         p_CLKFBOUT_MULT_F=clkfbout_mult, p_DIVCLK_DIVIDE=1,
                         i_CLKIN1=clk50_distbuf, i_CLKFBIN=mmcm_rhs_fb_d_g, o_CLKFBOUT=mmcm_rhs_fb_d,

                         # 400 MHz - BUFIO
                         p_CLKOUT0_DIVIDE_F=2, p_CLKOUT0_PHASE=0.0,
                         o_CLKOUT0=pll_sys4x,

                         # 200 MHz - BUFR
                         p_CLKOUT1_DIVIDE=4, p_CLKOUT1_PHASE=0.0,
                         o_CLKOUT1=pll_sys2x,

                         # 400 MHz dqs - BUFIO
                         p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=dqs_phase,  # should be a multiple of 22.50
                         o_CLKOUT2=pll_sys4x_dqs,

                         # 100 MHz - routing fabric
                         p_CLKOUT5_DIVIDE=8, p_CLKOUT5_PHASE=0.0,
                         o_CLKOUT5=self.pll_sys,

                         # 50 MHz, this one is constant across 200/300/400 MHz IDELAYCTRL variants
                         p_CLKOUT4_DIVIDE=clkfbout_mult, p_CLKOUT4_PHASE=0.0,
                         o_CLKOUT4=pll_clk50,

                         # DRP
                         i_DCLK=ClockSignal(),
                         i_DWE=self._mmcm_write.re,
                         i_DEN=self._mmcm_read.re | self._mmcm_write.re,
                         o_DRDY=mmcm_drdy,
                         i_DADDR=self._mmcm_adr.storage,
                         i_DI=self._mmcm_dat_w.storage,
                         o_DO=self._mmcm_dat_r.status
                         ),

                # This PLL is separate from the above because it needs to be placed in the same bank as the
                # address/control pins to route the outputs to BUFIOs
                Instance("MMCME2_ADV",
                         p_STARTUP_WAIT="FALSE",
                         p_BANDWIDTH="OPTIMIZED",

                         # VCO @ 800 MHz
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=20.0,
                         p_CLKFBOUT_MULT_F=clkfbout_mult, p_DIVCLK_DIVIDE=1,
                         i_CLKIN1=clk50_distbuf, i_CLKFBIN=mmcm_rhs_fb_ac_g, o_CLKFBOUT=mmcm_rhs_fb_ac,

                         # 400 MHz - BUFIO
                         p_CLKOUT0_DIVIDE_F=2, p_CLKOUT0_PHASE=0.0,
                         o_CLKOUT0=pll_sys4x_ac,
                ),
                # feedback delay compensation buffers
                Instance("BUFG", i_I=pll_fb, o_O=pll_fb_bufg),
                Instance("BUFG", i_I=mmcm_rhs_fb_d, o_O=mmcm_rhs_fb_d_g),
                Instance("BUFG", i_I=mmcm_rhs_fb_ac, o_O=mmcm_rhs_fb_ac_g),

                # global distribution buffers
                Instance("BUFG", i_I=self.pll_sys, o_O=self.cd_sys.clk),
                Instance("BUFG", i_I=pll_clk50, o_O=self.cd_eth.clk),
                Instance("BUFG", i_I=delayrefclk, o_O=self.cd_delayrefclk.clk),

                # local IO clocks for DDR
                Instance("BUFIO", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
                Instance("BUFR", i_I=pll_sys4x, o_O=self.cd_sys2x.clk, i_CLR=0, i_CE=1, p_BUFR_DIVIDE="2"),
                Instance("BUFIO", i_I=pll_sys4x_dqs, o_O=self.cd_sys4x_dqs.clk),

                Instance("BUFIO", i_I=pll_sys4x_ac, o_O=self.cd_sys4x_ac.clk),

                AsyncResetSynchronizer(self.cd_sys, ~pll_locked | rst | ~slave_locked),
                AsyncResetSynchronizer(self.cd_eth, ~pll_locked | rst | ~slave_locked),
                AsyncResetSynchronizer(self.cd_delayrefclk, ~pll_locked | rst | ~slave_locked),
                AsyncResetSynchronizer(self.cd_sys2x, ~pll_locked | rst | ~slave_locked),
            ]
            self.sync += [
                If(self._mmcm_read.re | self._mmcm_write.re,
                    self._mmcm_drdy.status.eq(0)
                ).Elif(mmcm_drdy,
                    self._mmcm_drdy.status.eq(1)
                )
            ]
        else:
            ss_fb = Signal()
            clk50_ss = Signal()
            clk50_ss_buf = Signal()
            pll_ss_locked = Signal()

            self.specials += [
                Instance("MMCME2_ADV",
                         p_BANDWIDTH="LOW", p_SS_EN="TRUE", p_SS_MODE="DOWN_HIGH",  # DOWN_HIGH for greater spreading
                         o_LOCKED=pll_ss_locked,

                         # VCO
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=20.0,
                         p_CLKFBOUT_MULT_F=56.0, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=4,
                         i_CLKIN1=clk50_distbuf, i_CLKFBIN=ss_fb, o_CLKFBOUT=ss_fb,

                         # pix clk
                         p_CLKOUT0_DIVIDE_F=14, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=clk50_ss,
                         ),
                Instance("BUFG", i_I=clk50_ss, o_O=clk50_ss_buf),
            ]

            pll_fb_bufg = Signal()
            self.specials += [
                Instance("PLLE2_BASE",
                         p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                         # VCO @ 1600 MHz
                         p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=20.0,
                         p_CLKFBOUT_MULT=32, p_DIVCLK_DIVIDE=1,
                         i_CLKIN1=clk50_ss_buf, i_CLKFBIN=pll_fb_bufg, o_CLKFBOUT=pll_fb,

                         # 100 MHz
                         p_CLKOUT0_DIVIDE=16, p_CLKOUT0_PHASE=0.0,
                         o_CLKOUT0=self.pll_sys,

                         # 400 MHz
                         p_CLKOUT1_DIVIDE=4, p_CLKOUT1_PHASE=0.0,
                         o_CLKOUT1=pll_sys4x,

                         # 400 MHz dqs
                         p_CLKOUT2_DIVIDE=4, p_CLKOUT2_PHASE=dqs_phase,
                         o_CLKOUT2=pll_sys4x_dqs,

                         # 200 MHz
                         p_CLKOUT3_DIVIDE=8, p_CLKOUT3_PHASE=0.0,
                         o_CLKOUT3=pll_clk200,

                         ),
                Instance("BUFG", i_I=pll_fb, o_O=pll_fb_bufg),

                Instance("BUFG", i_I=self.pll_sys, o_O=self.cd_sys.clk),
                Instance("BUFG", i_I=pll_clk200, o_O=self.cd_clk200.clk),
                Instance("BUFG", i_I=pll_sys4x, o_O=self.cd_sys4x.clk),
                Instance("BUFG", i_I=pll_sys4x_dqs, o_O=self.cd_sys4x_dqs.clk),
                AsyncResetSynchronizer(self.cd_sys, ~pll_locked | rst | ~pll_ss_locked),
                AsyncResetSynchronizer(self.cd_clk200, ~pll_locked | rst),

                AsyncResetSynchronizer(self.cd_eth, ~pll_locked | rst | ~pll_ss_locked),
            ]
            self.comb += self.cd_eth.clk.eq(clk50_distbuf)

        reset_counter = Signal(4, reset=31)  # 77.5ns @ 400MHz, min 59.28ns
        ic_reset = Signal(reset=1)
        self.sync.delayrefclk += \
            If(reset_counter != 0,
                reset_counter.eq(reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        self.specials += Instance("IDELAYCTRL", i_REFCLK=ClockSignal("delayrefclk"), i_RST=ic_reset)

class BaseSoC(SoCSDRAM):
    csr_peripherals = [
        "ddrphy",
        "xadc",
        "dna",
        "cpu_or_bridge",
        "spiflash",
        "crg",
    ]
    csr_map_update(SoCSDRAM.csr_map, csr_peripherals)

    mem_map = {
        "spiflash" : 0x20000000, # (default shadow @0xa0000000)
    }
    mem_map.update(SoCSDRAM.mem_map)

    def __init__(self, platform, dqs_phase="112.5", strength="40ohm", spiflash="spiflash_1x", **kwargs):
        if iodelay_clk_freq == int(400e6) or iodelay_clk_freq == int(200e6):
            clk_freq = int(100e6)
        elif iodelay_clk_freq == int(300e6):
            clk_freq = int(75e6)  # we achieve 300e6 by changing the master divider so the whole system goes slower

        SoCSDRAM.__init__(self, platform, clk_freq,
            integrated_rom_size=0x6000,
            integrated_sram_size=0x1000,
            ident="NeTV2 LiteX Base SoC",
            reserve_nmi_interrupt=False,
            cpu_type="vexriscv",
#            cpu_variant="debug",
            **kwargs)

#        self.register_mem("vexriscv_debug", 0xf00f0000, self.cpu_or_bridge.debug_bus, 0x10)

        self.submodules.crg = CRG(platform, use_ss=False, dqs_phase=float(dqs_phase))
        self.submodules.dna = dna.DNA()
        self.submodules.xadc = xadc.XADC()

        self.crg.cd_sys.clk.attr.add("keep")
        platform.add_period_constraint(self.crg.cd_sys.clk, period_ns(clk_freq))

        # sdram
        print("using drive strength of " + strength)
        self.submodules.ddrphy = a7ddrphy.A7DDRPHY(platform.request("ddram"), iodelay_clk_freq=iodelay_clk_freq)
        self.ddrphy.settings.add_electrical_settings(rtt_nom='20ohm', rtt_wr='disabled', ron=strength)
        self.add_constant("IDELAYCTRL_CLOCK_FREQUENCY", int(iodelay_clk_freq))
        sdram_module = K4B2G1646FBCK0(self.clk_freq, "1:4", speedgrade='1600')
        self.add_constant("READ_LEVELING_BITSLIP", 3)
        self.add_constant("READ_LEVELING_DELAY", 14)
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings,
                            controller_settings=ControllerSettings(with_bandwidth=True,
                                                                   cmd_buffer_depth=8,
                                                                   with_refresh=True,
                                                                   with_auto_precharge=True))

        # common led
        self.sys_led = Signal()
        self.pcie_led = Signal()
        self.comb += platform.request("fpga_led0", 0).eq(self.sys_led ^ self.pcie_led) #TX0 green
        self.comb += platform.request("fpga_led1", 0).eq(0) #TX0 red

        self.fan_pwm = Signal()
        self.comb += platform.request("fan_pwm", 0).eq(1) # lock the fan to the "on" position


        # sys led
        sys_counter = Signal(32)
        self.sync += sys_counter.eq(sys_counter + 1)
        self.comb += self.sys_led.eq(sys_counter[26])

        # spi flash
        spiflash_pads = platform.request(spiflash)
        spiflash_pads.clk = Signal()
        self.specials += Instance("STARTUPE2",
                                  i_CLK=0, i_GSR=0, i_GTS=0, i_KEYCLEARB=0, i_PACK=0,
                                  i_USRCCLKO=spiflash_pads.clk, i_USRCCLKTS=0, i_USRDONEO=1, i_USRDONETS=1)
        spiflash_dummy = {
            "spiflash_1x": 8,  # this is specific to the device populated on the board -- if it changes, must be updated
            "spiflash_4x": 12, # this is almost certainly wrong
        }
        self.submodules.spiflash = spi_flash.SpiFlash(
                spiflash_pads,
                dummy=spiflash_dummy[spiflash],
                div=2)
        self.add_constant("SPIFLASH_PAGE_SIZE", 256)
        self.add_constant("SPIFLASH_SECTOR_SIZE", 0x10000)
        self.add_wb_slave(mem_decoder(self.mem_map["spiflash"]), self.spiflash.bus)
        self.add_memory_region(
            "spiflash", self.mem_map["spiflash"] | self.shadow_base, 8*1024*1024)

        self.flash_boot_address = 0x207b0000  # hard-coded to be just above the second copy of 100T bitfile


class I2Csnoop(Module, AutoCSR):
    def __init__(self, pads):
        self.edid_snoop_adr = CSRStorage(8)
        self.edid_snoop_dat = CSRStatus(8)

        reg_dout = Signal(8)
        self.An = Signal(64)   # An as read out
        self.Aksv14_write = Signal()  # Ksv byte 14 complete strobe
        self.specials += [
            Instance("i2c_snoop",
                     i_SDA=~pads.sda,
                     i_SCL=~pads.scl,
                     i_clk=ClockSignal("eth"),
                     i_reset=ResetSignal("eth"),
                     i_i2c_snoop_addr=0x74,
                     i_reg_addr=self.edid_snoop_adr.storage,
                     o_reg_dout=reg_dout,
                     o_An=self.An,
                     o_Aksv14_write=self.Aksv14_write,
                     )
        ]
        self.comb += self.edid_snoop_dat.status.eq(reg_dout)

class HDCP(Module, AutoCSR):
    def __init__(self, timing_stream):

        self.de = timing_stream.de
        self.hsync = timing_stream.hsync
        self.vsync = timing_stream.vsync

        self.line_end = Signal() # early line end comes from outside this module

        self.hpd = Signal()
        self.hdcp_ena = Signal()
        self.Aksv14_write = Signal()
        self.Aksv14_write_level = Signal()
        self.ctl_code = Signal(4)
        self.An = Signal(64)

        self.Km = CSRStorage(56)
        self.Km_valid = CSRStorage()
        self.hpd_ena = CSRStorage()
        self.Aksv_mode = CSRStorage()  # set to 0 = auto Aksv; set to 1 then Aksv_manual
        self.Aksv_manual = CSRStorage() # set to 1 to initiate HDCP rekey based on Aksv updates
        self.debug = CSRStorage()

        self.cipher_stream = Signal(24)
        self.stream_ready = Signal()

        self.submodules.ev = EventManager()
        self.ev.aksv = EventSourcePulse()
        self.ev.finalize()

        # synchronize Aksv14_auto into sysclock domain
        Aksv14_sys = Signal()
        self.specials += MultiReg(self.Aksv14_write_level, Aksv14_sys)
        self.comb += self.ev.aksv.trigger.eq(Aksv14_sys)  # convert this to EventSourcePulse so pulse converter redundant

        self.Aksv14_auto = Signal()
        # install a mux so we can select either auto behavior, or manual override
        self.comb += [
            If(self.Aksv_mode.storage == 0,
               self.Aksv14_auto.eq(self.Aksv14_write)
            ).Else(
                self.Aksv14_auto.eq(self.Aksv_manual.storage)
            )
        ]

        self.specials += [
            Instance("hdcp_mod",
                     i_clk=ClockSignal("pix_o"),
                     i_rst=ResetSignal("pix_o"),
                     i_de=self.de,
                     i_hsync=self.hsync,
                     i_vsync=self.vsync,
                     i_ctl_code=self.ctl_code,
                     i_line_end=self.line_end,
                     i_hpd=self.hpd,
                     i_Aksv14_write = self.Aksv14_auto,
                     i_An = self.An,
                     i_Km = self.Km.storage,
                     i_Km_valid = self.Km_valid.storage,
                     i_hdcp_ena = self.hdcp_ena,
                     o_cipher_stream = self.cipher_stream,
                     o_stream_ready = self.stream_ready,
                     )
        ]


class RectOpening(Module, AutoCSR):
    def __init__(self, timing_stream):

        self.hrect_start = CSRStorage(12)
        self.hrect_end = CSRStorage(12)
        self.vrect_start = CSRStorage(12)
        self.vrect_end = CSRStorage(12)
        self.rect_thresh = CSRStorage(8)

        self.pipe_override = CSRStorage(1)

        self.rect_on = Signal()

        # counter for pixel position based on the incoming HDMI0 stream.
        # use this instead of programmed values because we want to sync to non-compliant data streams
        self.hcounter = hcounter = Signal(hbits)
        self.vcounter = vcounter = Signal(vbits)

        in0_de = Signal()
        in0_de_r = Signal()
        in0_vsync = Signal()
        in0_vsync_r = Signal()
        in0_hsync = Signal()
        in0_hsync_r = Signal()
        self.sync += [  # rename this to the pix_o domain for the NeTV2 application
            in0_de.eq(timing_stream.de),
            in0_de_r.eq(in0_de),
            in0_vsync.eq(timing_stream.vsync),
            in0_vsync_r.eq(in0_vsync),
            in0_hsync.eq(timing_stream.hsync),
            in0_hsync_r.eq(in0_hsync),

            If(in0_vsync & ~in0_vsync_r,
               vcounter.eq(0)
               ).Elif(in0_de & ~in0_de_r,
                      vcounter.eq(vcounter + 1)
                      ),
            If(in0_de & ~in0_de_r,
               hcounter.eq(0),
               ).Elif(in0_de,
                      hcounter.eq(hcounter + 1)
                      )
        ]

        self.comb += self.rect_on.eq(((hcounter > self.hrect_start.storage) & (hcounter < self.hrect_end.storage) &
                                      (vcounter > self.vrect_start.storage) & (vcounter < self.vrect_end.storage))  == 1)



rgb_layout = [
    ("r", 8),
    ("g", 8),
    ("b", 8)
]

class TimingDelayRGB(Module):
    def __init__(self, latency):
        self.sink = stream.Endpoint(rgb_layout)
        self.source = stream.Endpoint(rgb_layout)

        # # #

        for name in list_signals(rgb_layout):
            s = getattr(self.sink, name)
            for i in range(latency):
                next_s = Signal(len(s))  # without len(s), this makes only one-bit wide delay lines
                self.sync += next_s.eq(s)
                s = next_s
            self.comb += getattr(self.source, name).eq(s)

class VideoOverlaySoC(BaseSoC):

    csr_peripherals = [
        "hdmi_core_out0",
        "hdmi_in0",
        "hdmi_in0_freq",
        "hdmi_in0_edid_mem",
        "hdmi_in1",
        "hdmi_in1_freq",
        "hdmi_in1_edid_mem",  
        "rectangle",
        "hdcp",
        "i2c_snoop",
        "analyzer",
        "phy",
        "core",
    ]
    csr_map_update(BaseSoC.csr_map, csr_peripherals)

    interrupt_map = {
        "hdmi_in1": 3,
        "hdcp" : 4,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    def __init__(self, platform, part, dqs_phase, strength, *args, **kwargs):
        BaseSoC.__init__(self, platform, dqs_phase, strength, *args, **kwargs)

        # # #
        self.add_constant("BOOT_MEMTEST", 1) # add extra boot memory testing/characterization features to BIOS image

        pix_freq = 148.50e6

        platform.add_source(os.path.join("overlay", "delay_controller.v"))
        platform.add_source(os.path.join("overlay", "phsaligner.v"))
        platform.add_source(os.path.join("overlay", "DRAM16XN.v"))
        platform.add_source(os.path.join("overlay", "chnlbond.v"))

        ########## hdmi in 0 (raw tmds)
        hdmi_in0_pads = platform.request("hdmi_in", 0)
        self.submodules.hdmi_in0_freq = FrequencyMeter(period=self.clk_freq)
        self.submodules.hdmi_in0 = hdmi_in0 = HDMIIn(hdmi_in0_pads, device="xc7", split_mmcm=True, hdmi=True, iodelay_clk_freq=iodelay_clk_freq, alt_delay=True)
        self.comb += self.hdmi_in0_freq.clk.eq(self.hdmi_in0.clocking.cd_pix.clk)
        # don't add clock timings here, we add a root clock constraint that derives the rest automatically

        # define path constraints individually to sysclk to avoid accidentally declaring other inter-clock paths as false paths
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in0.clocking.cd_pix.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in0.clocking.cd_pix1p25x.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in0.clocking.cd_pix5x.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in0.clocking.cd_pix_o.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in0.clocking.cd_pix5x_o.clk
        )

        hdmi_out0_pads = platform.request("hdmi_out", 0)  ## TODO: pull latest litevideo and re-validate pix_o mapping
        self.submodules.hdmi_out0_clk_gen = ClockDomainsRenamer({"pix":"pix_o", "pix5x":"pix5x_o"})(S7HDMIOutEncoderSerializer(hdmi_out0_pads.clk_p, hdmi_out0_pads.clk_n, bypass_encoder=True))
        self.comb += self.hdmi_out0_clk_gen.data.eq(Signal(10, reset=0b0000011111))
        self.submodules.hdmi_out0_phy = ClockDomainsRenamer({"pix":"pix_o", "pix5x":"pix5x_o"})(S7HDMIOutPHY(hdmi_out0_pads, mode="raw"))

        # hdmi over
        self.comb += [
            platform.request("hdmi_sda_over_up").eq(0),
            platform.request("hdmi_sda_over_dn").eq(0),
        ]

        # extract timing info from HDMI input 0, and put it into a stream that we can pass later on as a genlock object
        self.hdmi_in0_timing = hdmi_in0_timing = stream.Endpoint(frame_timing_layout)
        self.sync.pix_o += [
            hdmi_in0_timing.de.eq(self.hdmi_in0.syncpol.de),
            hdmi_in0_timing.hsync.eq(self.hdmi_in0.syncpol.hsync),
            hdmi_in0_timing.vsync.eq(self.hdmi_in0.syncpol.vsync),
            If(self.hdmi_in0.syncpol.valid_o,
                hdmi_in0_timing.valid.eq(1),
            ).Else(
                hdmi_in0_timing.valid.eq(0),
            )
        ]
        early_line_end = Signal()
        self.comb += early_line_end.eq(hdmi_in0_timing.de & ~self.hdmi_in0.syncpol.de)

        ########## hdmi in 1
        hdmi_in1_pads = platform.request("hdmi_in", 1)
        self.submodules.hdmi_in1_freq = FrequencyMeter(period=self.clk_freq)
        # maybe this core gets precedence in round-robin arbitration, but this FIFO can be smaller than
        # the output FIFO. fifo_depth=256 was tested and works, but it turns out it doesn't save any
        # area over fifo_depth=512 due to the granularity of BRAM blocks. If some BRAMs are needed, try
        # trimming to 128 and see if that actually saves any space without breaking anything...
        self.submodules.hdmi_in1 = self.hdmi_in1 = HDMIIn(hdmi_in1_pads,
                                         self.sdram.crossbar.get_port(mode="write"),
                                         fifo_depth=512,
                                         device="xc7",
                                         split_mmcm=False,
                                         mode="rgb",
                                         hdmi=True,
                                         n_dma_slots=2,
                                         iodelay_clk_freq = iodelay_clk_freq,
                                         alt_delay=True,
                                          )
        self.comb += self.hdmi_in1_freq.clk.eq(self.hdmi_in1.clocking.cd_pix.clk)

        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in1.clocking.cd_pix.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in1.clocking.cd_pix1p25x.clk
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.hdmi_in1.clocking.cd_pix5x.clk
        )

        ######## Constraints
        # instantiate fundamental clocks -- Vivado will derive the rest via PLL programmings
        self.platform.add_platform_command(
            "create_clock -name clk50 -period 20.0 [get_nets clk50]")
        self.platform.add_platform_command(
            "create_clock -name hdmi_in0_clk_p -period 6.734006734006734 [get_nets hdmi_in0_clk_p]")
        self.platform.add_platform_command(
            "create_clock -name hdmi_in1_clk_p -period 6.734006734006734 [get_nets hdmi_in1_clk_p]")

        # exclude all generated clocks from the fundamental HDMI clocks and sys clocks
        self.platform.add_platform_command("set_clock_groups -group [get_clocks -include_generated_clocks -of [get_nets sys_clk]] -group [get_clocks -include_generated_clocks -of [get_nets hdmi_in0_clk_p]] -asynchronous")
        self.platform.add_platform_command("set_clock_groups -group [get_clocks -include_generated_clocks -of [get_nets sys_clk]] -group [get_clocks -include_generated_clocks -of [get_nets hdmi_in1_clk_p]] -asynchronous")

        # don't time the high-fanout reset paths
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in0_pix_rst]")
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in1_pix_rst]")
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in0_pix1p25x_rst]")  # degenerate, throws warning
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in0_pix1p25x_r_rst]")
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in1_pix1p25x_rst]")  # degenerate, throws warning
        self.platform.add_platform_command("set_false_path -through [get_nets hdmi_in1_pix1p25x_r_rst]")
        self.platform.add_platform_command("set_false_path -through [get_nets pix_o_rst]")
        self.platform.add_platform_command("set_false_path -through [get_nets soc_videooverlaysoc_s7hdmioutencoderserializer_ce]") # derived from reset

        # gearbox timing is a multi-cycle path: FAST to SLOW synchronous clock domains
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk1] -to [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk1] -to [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk1] -to [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk1] -to [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0]")
        # add _r variant (BUFR, same domain, different source)
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks hdmi_in0_pix1p25x_r_clk] -to [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks hdmi_in0_pix1p25x_r_clk] -to [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks hdmi_in1_pix1p25x_r_clk] -to [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks hdmi_in1_pix1p25x_r_clk] -to [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0]")
        # bitslip timing is also multi-cycle path
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0] -to [get_clocks hdmi_in0_pix1p25x_r_clk]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks soc_videooverlaysoc_hdmi_in0_mmcm_clk0] -to [get_clocks hdmi_in0_pix1p25x_r_clk]")
        self.platform.add_platform_command("set_multicycle_path 2 -setup -start -from [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0] -to [get_clocks hdmi_in1_pix1p25x_r_clk]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -from [get_clocks soc_videooverlaysoc_hdmi_in1_mmcm_clk0] -to [get_clocks hdmi_in1_pix1p25x_r_clk]")

        # This prevents the tri-state timing on DQ being a limiting path -- however, this should probably be a multi-cycle path
        # and not a straight false_path. May need to adjust if the DQ tri-state timing seems to be a problem
        # self.platform.add_platform_command("set_false_path -through [get_nets soc_videooverlaysoc_videooverlaysoc_a7ddrphy_oe_dq]")
        self.platform.add_platform_command("set_multicycle_path 2 -setup -through [get_nets soc_videooverlaysoc_videooverlaysoc_a7ddrphy_oe_dq]")
        self.platform.add_platform_command("set_multicycle_path 1 -hold -through [get_nets soc_videooverlaysoc_videooverlaysoc_a7ddrphy_oe_dq]")

        input_clock = "dqsin"     # Name of input clock
        input_clock_period = 2.5  # Period of input clock (full-period)
        for i in range(0,4):
            self.platform.add_platform_command(
                "create_clock -period " + str(input_clock_period) + " -name " + input_clock + str(i) + " [get_ports ddram_dqs_p[" + str(i) + "] ]"
            )

        """
        ### Constrain the output DQS-to-data relationship so the DRAM data is centered correctly
        #  Double Data Rate Source Synchronous Outputs
        #
        #  Source synchronous output interfaces can be constrained either by the max data skew
        #  relative to the generated clock or by the destination device setup/hold requirements.
        #
        #  Setup/Hold Case:
        #  Setup and hold requirements for the destination device and board trace delays are known.
        #
        # forwarded                        _________________________________
        # clock                 __________|                                 |______________
        #                                 |                                 |
        #                           tsu_r |  thd_r                    tsu_f | thd_f
        #                         <------>|<------->                <------>|<----->
        #                         ________|_________                ________|_______
        # data @ destination   XXX__________________XXXXXXXXXXXXXXXX________________XXXXX
        #
        # Example of creating generated clock at clock output port
        # create_generated_clock -name <gen_clock_name> -multiply_by 1 -source [get_pins <source_pin>] [get_ports <output_clock_port>]
        # gen_clock_name is the name of forwarded clock here. It should be used below for defining "fwclk".

        # report_timing -rise_to [get_ports ddram_dq] -max_paths 20 -nworst 2 -delay_type min_max -name src_sync_ddr_out_rise
        # report_timing -fall_to [get_ports ddram_dq] -max_paths 20 -nworst 2 -delay_type min_max -name src_sync_ddr_out_fall

        tsu_r = 10.0 / 1000  # vivado units in ns, datasheet units in ps
        thd_r = 45.0 / 1000
        tsu_f = 10.0 / 1000
        thd_f = 45.0 / 1000
        trce_dly_max = 0.000  # maximum board trace delay
        trce_dly_min = 0.000  # minimum board trace delay
        output_ports = []
        for i in range(0,32):
            output_ports.append('ddram_dq[' + str(i) + ']')

        # Output Delay Constraints
        for i in range(0,32):
            self.platform.add_platform_command(
                "set_output_delay -clock soc_videooverlaysoc_videooverlaysoc_crg_pll_sys4x_dqs -max " + str(trce_dly_max + tsu_r) + " [get_ports " + output_ports[i] + "]"
            )
            self.platform.add_platform_command(
                "set_output_delay -clock soc_videooverlaysoc_videooverlaysoc_crg_pll_sys4x_dqs -min " + str(trce_dly_min + thd_r) + " [get_ports " + output_ports[i] + "]"
            )
            self.platform.add_platform_command(
                "set_output_delay -clock soc_videooverlaysoc_videooverlaysoc_crg_pll_sys4x_dqs -max " + str(trce_dly_max + tsu_f) + " [get_ports " + output_ports[i] + "] -clock_fall -add_delay"
            )
            self.platform.add_platform_command(
                "set_output_delay -clock soc_videooverlaysoc_videooverlaysoc_crg_pll_sys4x_dqs -min " + str(trce_dly_min + thd_f) + " [get_ports " + output_ports[i] + "] -clock_fall -add_delay"
            )
        """

        """     # We don't need these constraints because we calibrate this delay on boot

        # Center-Aligned Double Data Rate Source Synchronous Inputs
        #
        # For a center-aligned Source Synchronous interface, the clock
        # transition is aligned with the center of the data valid window.
        # The same clock edge is used for launching and capturing the
        # data. The constraints below rely on the default timing
        # analysis (setup = 1/2 cycle, hold = 0 cycle).
        #
        # input                  ____________________
        # clock    _____________|                    |_____________
        #                       |                    |
        #                dv_bre | dv_are      dv_bfe | dv_afe
        #               <------>|<------>    <------>|<------>
        #          _    ________|________    ________|________    _
        # data     _XXXX____Rise_Data____XXXX____Fall_Data____XXXX_
        #

        # Report Timing template
        # report_timing -rise_from [get_ports ddram_dq] -max_paths 20 -nworst 2 -delay_type min_max -name src_sync_cntr_ddr_in_rise
        # report_timing -fall_from [get_ports ddram_dq] -max_paths 20 -nworst 2 -delay_type min_max -name src_sync_cntr_ddr_in_fall

        input_clock = "dqsin"     # Name of input clock
        input_clock_period = 2.5  # Period of input clock (full-period)
        for i in range(0,4):
            self.platform.add_platform_command(
                "create_clock -period " + str(input_clock_period) + " -name " + input_clock + str(i) + " [get_ports ddram_dqs_p[" + str(i) + "] ]"
            )

        dv_bre = (input_clock_period/2) - 100.0 / 10000 # Data valid before the rising clock edge
        dv_are = (input_clock_period/2) * 0.38
        dv_bfe = (input_clock_period/2) - 100.0 / 10000 # Data valid before the falling clock edge
        dv_afe = (input_clock_period/2) * 0.38 # Data valid after the falling clock edge
        input_ports = "ddram_dq"  # List of input ports

        # Input Delay Constraint
        for i in range(0, 32):
            self.platform.add_platform_command(
                "set_input_delay -clock " + input_clock + str(i//8) + " -max " + str(input_clock_period/2 - dv_bfe) + " [get_ports ddram_dq[" + str(i) +"] ]"
            )
            self.platform.add_platform_command(
                "set_input_delay -clock " + input_clock + str(i//8) + " -min " + str(dv_are) + " [get_ports ddram_dq[" + str(i) + "] ]"
            )
            self.platform.add_platform_command(
                "set_input_delay -clock " + input_clock + str(i//8) + " -max " + str(input_clock_period/2 - dv_bre) + " [get_ports ddram_dq[" + str(i) + "] ] -clock_fall -add_delay"
            )
            self.platform.add_platform_command(
                "set_input_delay -clock " + input_clock + str(i//8) + " -min " + str(dv_afe) + " [get_ports ddram_dq[" + str(i) + "] ] -clock_fall -add_delay"
            )
        """

        ###############  hdmi out 1 (overlay rgb)

        out_dram_port = self.sdram.crossbar.get_port(mode="read", clock_domain="pix_o", data_width=32, reverse=True)
        # this core seems to starve more than the in core, so the FIFO is deeper at 2048. A 1024 depth leads to some frame tearing
        # especially when the CPU activity is high when loaded at 1080p60
        self.submodules.hdmi_core_out0 = VideoOutCore(out_dram_port, mode="rgb", fifo_depth=4096, genlock_stream=hdmi_in0_timing)

        core_source_valid_d = Signal()
        core_source_data_d = Signal(32)
        sync_cd = getattr(self.sync, out_dram_port.cd)
        sync_cd += [
            core_source_valid_d.eq(self.hdmi_core_out0.source.valid),
            core_source_data_d.eq(self.hdmi_core_out0.source.data),
        ]

        ####### timing stream extraction
        timing_rgb_delay = TimingDelayRGB(4) # create the delay element with specified delay...note if you say TimingDelay() the code runs happily with no error, because Python doesn't typecheck
        timing_rgb_delay = ClockDomainsRenamer("pix_o")(timing_rgb_delay) # assign a clock domain to the delay element
        self.submodules += timing_rgb_delay  # DONT FORGET THIS LINE OR ELSE NOTHING HAPPENS....
        self.hdmi_out0_rgb = hdmi_out0_rgb = stream.Endpoint(rgb_layout) # instantiate the input record
        self.hdmi_out0_rgb_d = hdmi_out0_rgb_d = stream.Endpoint(rgb_layout) # instantiate the output record
        self.comb += [
            self.hdmi_core_out0.source.ready.eq(1), # don't forget to tell the upstream component that we're ready, or we get a monochrome screen...
            hdmi_out0_rgb.b.eq(core_source_data_d[0:8]),  # wire up the specific elements of the input record
            hdmi_out0_rgb.g.eq(core_source_data_d[8:16]),
            hdmi_out0_rgb.r.eq(core_source_data_d[16:24]),
            hdmi_out0_rgb.valid.eq(core_source_valid_d),  # not used, but hook it up anyways in case we need it later...
            timing_rgb_delay.sink.eq(hdmi_out0_rgb), # assign input stream to the delay element
            hdmi_out0_rgb_d.eq(timing_rgb_delay.source) # grab output stream from the delay element
            # the output records are directly consumed down below
        ]

        ##### HDCP engine
        platform.add_source(os.path.join("overlay", "i2c_snoop.v"))
        platform.add_source(os.path.join("overlay", "diff_network.v"))
        platform.add_source(os.path.join("overlay", "hdcp_block.v"))
        platform.add_source(os.path.join("overlay", "hdcp_cipher.v"))
        platform.add_source(os.path.join("overlay", "hdcp_lfsr.v"))
        platform.add_source(os.path.join("overlay", "shuffle_network.v"))
        platform.add_source(os.path.join("overlay", "hdcp_mod.v"))

        self.submodules.i2c_snoop = i2c_snoop = I2Csnoop(hdmi_in0_pads)
        self.submodules.hdcp = hdcp = HDCP(hdmi_in0_timing)
        self.comb += hdcp.line_end.eq(early_line_end)  # wire up an early line-end signal to meet rekey timing
        Aksv14 = Signal()
        Aksv14_r = Signal()
        self.specials += MultiReg(i2c_snoop.Aksv14_write, Aksv14, odomain="pix_o")
        self.sync.pix_o += [
            Aksv14_r.eq(Aksv14),
            hdcp.Aksv14_write.eq(Aksv14 & ~Aksv14_r), # should be a rising-edge strobe only
            hdcp.Aksv14_write_level.eq(Aksv14),
            hdcp.hdcp_ena.eq(hdmi_in0.decode_terc4.encrypting_video | hdmi_in0.decode_terc4.encrypting_data),
            hdcp.hpd.eq(hdmi_in0_pads.hpd_notif),
            hdcp.An.eq(i2c_snoop.An),
            hdcp.ctl_code.eq(hdmi_in0.decode_terc4.ctl_code),
        ]
        self.comb += platform.request("hdmi_rx0_forceunplug").eq(hdcp.hpd_ena.storage)

        ###### overlay pixel encoders
        self.submodules.encoder_red = encoder_red = ClockDomainsRenamer("pix_o")(Encoder())
        self.submodules.encoder_grn = encoder_grn = ClockDomainsRenamer("pix_o")(Encoder())
        self.submodules.encoder_blu = encoder_blu = ClockDomainsRenamer("pix_o")(Encoder())

        self.comb += [
            If(hdcp.Km_valid.storage,  # this is a proxy for HDCP being initialized
               encoder_red.d.eq(hdmi_out0_rgb.r ^ hdcp.cipher_stream[16:]), # 23:16
               encoder_grn.d.eq(hdmi_out0_rgb.g ^ hdcp.cipher_stream[8:16]),  # 15:8
               encoder_blu.d.eq( (hdmi_out0_rgb.b ^ hdcp.cipher_stream[0:8])),  # 7:0
               ).Else(
                encoder_red.d.eq(hdmi_out0_rgb.r),
                encoder_grn.d.eq(hdmi_out0_rgb.g),
                encoder_blu.d.eq(hdmi_out0_rgb.b),
            ),
            encoder_red.de.eq(1),
            encoder_red.c.eq(0), # we promise to use this only during video areas, so "c" is always 0

            encoder_grn.de.eq(1),
            encoder_grn.c.eq(0),

            encoder_blu.de.eq(1),
            encoder_blu.c.eq(0),
        ]

        # hdmi in to hdmi out
        c0_pix_o = Signal(10)
        c1_pix_o = Signal(10)
        c2_pix_o = Signal(10)
        c0 = Signal(10)
        c1 = Signal(10)
        c2 = Signal(10)
        self.comb += [
            c0.eq(self.hdmi_in0.syncpol.c0),
            c1.eq(self.hdmi_in0.syncpol.c1),
            c2.eq(self.hdmi_in0.syncpol.c2),
        ]
        for i in range(6): # either 5 or 6; 5 if the first pixel is encrypted by the idle cipher; 6 if the cipher has to be pumped before encryption
            c0_next = Signal(10)
            c1_next = Signal(10)
            c2_next = Signal(10)
            self.sync.pix_o += [  # extra delay to absorb cross-domain jitter & routing
                c0_next.eq(c0),
                c1_next.eq(c1),
                c2_next.eq(c2),
            ]
            c0 = c0_next
            c1 = c1_next
            c2 = c2_next

        self.sync.pix_o += [  # extra delay to absorb cross-domain jitter & routing
            c0_pix_o.eq(c0_next),
            c1_pix_o.eq(c1_next),
            c2_pix_o.eq(c2_next)
        ]

        rect_on = Signal()
        rect_thresh = Signal(8)

        self.submodules.rectangle = rectangle = ClockDomainsRenamer("pix_o")( RectOpening(hdmi_in0_timing) )
        self.comb += rect_on.eq(rectangle.rect_on)
        self.comb += rect_thresh.eq(rectangle.rect_thresh.storage)

        self.sync.pix_o += [
            If(rectangle.pipe_override.storage,
                 self.hdmi_out0_phy.sink.c0.eq(self.hdmi_in0.data0_cap.d),
                 self.hdmi_out0_phy.sink.c1.eq(self.hdmi_in0.data1_cap.d),
                 self.hdmi_out0_phy.sink.c2.eq(self.hdmi_in0.data2_cap.d),
            ).Elif(rect_on & (hdmi_out0_rgb_d.r >= rect_thresh) & (hdmi_out0_rgb_d.g >= rect_thresh) & (hdmi_out0_rgb_d.b >= rect_thresh),
                    self.hdmi_out0_phy.sink.c0.eq(encoder_blu.out),
                    self.hdmi_out0_phy.sink.c1.eq(encoder_grn.out),
                    self.hdmi_out0_phy.sink.c2.eq(encoder_red.out),
            ).Else(
                    self.hdmi_out0_phy.sink.c0.eq(c0_pix_o),
                    self.hdmi_out0_phy.sink.c1.eq(c1_pix_o),
                    self.hdmi_out0_phy.sink.c2.eq(c2_pix_o),
            )
        ]

        self.comb += platform.request("fpga_led2", 0).eq(self.hdmi_in0.clocking.locked)  # RX0 green
        self.comb += platform.request("fpga_led3", 0).eq(0)  # RX0 red

        # set an internal LED color based on the FPGA type installed -- for quick factory determination of PCB type (FPGA P/N covered by heatsink)
        if part == "35": # green if 35T
            self.comb += platform.request("fpga_led4", 0).eq(0)  # OV0 red
            self.comb += platform.request("fpga_led5", 0).eq(1)  # OV0 green
        else: # red if 100T
            self.comb += platform.request("fpga_led4", 0).eq(1)  # OV0 red
            self.comb += platform.request("fpga_led5", 0).eq(0)  # OV0 green

        # analyzer ethernet
        from liteeth.phy.rmii import LiteEthPHYRMII
        from liteeth.core import LiteEthUDPIPCore
        from liteeth.frontend.etherbone import LiteEthEtherbone

        fast_eth = False  # fast_eth puts etherbone in 100MHz domain; otherwise try to put it in 50MHz domain.
        # 100 MHz domain works but timing closure is hard
        # 50 MHz domain should also work but I'm not 100% of the syntax to create the clock domains correctly
        if fast_eth:
            self.submodules.phy = phy = LiteEthPHYRMII(platform.request("rmii_eth_clocks"), platform.request("rmii_eth"))
            mac_address = 0x1337320dbabe
            ip_address="10.0.11.2"
            self.submodules.core = LiteEthUDPIPCore(self.phy, mac_address, convert_ip(ip_address), int(100e6))
            self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 1234, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)
        else:
            phy = LiteEthPHYRMII(platform.request("rmii_eth_clocks"),
                                                       platform.request("rmii_eth"))
            phy = ClockDomainsRenamer("eth")(phy)
            mac_address = 0x1337320dbabe
            ip_address="10.0.11.2"
            core = LiteEthUDPIPCore(phy, mac_address, convert_ip(ip_address), int(50e6), with_icmp=True)
            core = ClockDomainsRenamer("eth")(core)
            self.submodules += phy, core

            etherbone_cd = ClockDomain("etherbone")
            self.clock_domains += etherbone_cd
            self.comb += [
                etherbone_cd.clk.eq(ClockSignal("sys")),
                etherbone_cd.rst.eq(ResetSignal("sys"))
            ]
            self.submodules.etherbone = LiteEthEtherbone(core.udp, 1234, mode="master", cd="etherbone")
            self.add_wb_master(self.etherbone.wishbone.bus)

        self.platform.add_false_path_constraints(
           self.crg.cd_sys.clk,
           self.crg.cd_eth.clk
        )

        # analyzer UART
#        from litex.soc.cores.uart import UARTWishboneBridge
        #            platform.request("serial",1), self.clk_freq, baudrate=3000000)
#        self.submodules.bridge = UARTWishboneBridge(
#            platform.request("serial",1), self.clk_freq, baudrate=115200)
#        self.add_wb_master(self.bridge.wishbone)

        from litescope import LiteScopeAnalyzer

        analyzer_signals = [
            self.hdmi_in0.use_alt_bond,
            self.hdmi_in0.syncpol.data_in0,
            self.hdmi_in0.syncpol.valid_i,
            self.hdmi_in0.syncpol.de,
            self.hdmi_in0.syncpol.vsync,
            c0_pix_o,
            c1_pix_o,
            c2_pix_o,
            encoder_blu.out,
            encoder_grn.out,
            encoder_red.out,
        ]
        self.platform.add_false_path_constraints( # for I2C snoop -> HDCP, and also covers logic analyzer path when configured
           self.crg.cd_eth.clk,
           self.hdmi_in0.clocking.cd_pix_o.clk
        )
        # WHEN NOT USING ANALYZER, COMMENT OUT FOR FASTER COMPILE TIMES
#        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 64, clock_domain="hdmi_in0_pix", trigger_depth=8)
#    def do_exit(self, vns):
#        self.analyzer.export_csv(vns, "test/analyzer.csv")

"""     # just to remember some ways to debug/combine data
        pix_aggregate = Signal(24)
        t4d_aggregate = Signal(12)
        self.comb += pix_aggregate.eq(Cat(self.hdmi_in0.syncpol.b,self.hdmi_in0.syncpol.g,self.hdmi_in0.syncpol.r))
        self.comb += t4d_aggregate.eq(Cat(self.hdmi_in0.decode_terc4.data0_dect4.decval.d,
                                          self.hdmi_in0.decode_terc4.data1_dect4.decval.d,
                                          self.hdmi_in0.decode_terc4.data2_dect4.decval.d))
        t4d_crypto = Signal(12)
        self.comb += t4d_crypto.eq(Cat(0,0,self.hdcp.cipher_stream[2],0,self.hdcp.cipher_stream[8:12],self.hdcp.cipher_stream[16:20]))
        main_raw = Signal(30)
        self.comb += main_raw.eq(Cat(c0_pix_o,c1_pix_o,c2_pix_o))
        overlay_raw = Signal(30)
        self.comb += overlay_raw.eq(Cat(encoder_blu.out,encoder_grn.out,encoder_red.out))
"""

def main():
    if os.environ['PYTHONHASHSEED'] != "1":
        print( "PYTHONHASHEED must be set to 1 for consistent validation results. Failing to set this results in non-deterministic compilation results")
        exit()

    parser = argparse.ArgumentParser(description="Build an NeTV2 bitstream and firmware")
    parser.add_argument(
        "-p", "--part", help="specify which FPGA part to build for", choices=["35", "50", "100"], default="35"
    )
    parser.add_argument(
        "-t", "--target", help="which FPGA environment to build for", choices=["base", "video_overlay", "pcie"], default="video_overlay"
    )
    parser.add_argument(
        "-d", "--dqsphase", help="set DQS phase offset", choices=["45.0", "67.5", "90.0", "112.5", "135.0", "157.5", "180.0"], default="112.5"
    )
    parser.add_argument(
        "-i", "--interm", help="input termination of FPGA", choices=["NONE", "40", "50", "60"], default="60"
    )
    parser.add_argument(
        "-s", "--strength", help="DDR3 drive strength", choices=["34ohm", "40ohm"], default="40ohm"
    )
    args = parser.parse_args()

    global _io
    if args.interm == "40":
        _io += [("ddram", 0,
            Subsignal("a", Pins(
                "U6 V4 W5 V5 AA1 Y2 AB1 AB3",
                "AB2 Y3 W6 Y1 V2 AA3"
                ),
                IOStandard("SSTL15_R")),
            Subsignal("ba", Pins("U5 W4 V7"), IOStandard("SSTL15_R")),
            Subsignal("ras_n", Pins("Y9"), IOStandard("SSTL15_R")),
            Subsignal("cas_n", Pins("Y7"), IOStandard("SSTL15_R")),
            Subsignal("we_n", Pins("V8"), IOStandard("SSTL15_R")),
            Subsignal("dm", Pins("G1 H4 M5 L3"), IOStandard("SSTL15_R")),
            Subsignal("dq", Pins(
                "C2 F1 B1 F3 A1 D2 B2 E2 "
                "J5 H3 K1 H2 J1 G2 H5 G3 "
                "N2 M6 P1 N5 P2 N4 R1 P6 "
                "K3 M2 K4 M3 J6 L5 J4 K6 "
                ),
                IOStandard("SSTL15_R"),
                Misc("IN_TERM=UNTUNED_SPLIT_40")),  # alt is UNTUNED_SPLIT_60 but NONE seems to work better
            Subsignal("dqs_p", Pins("E1 K2 P5 M1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_40")),
            Subsignal("dqs_n", Pins("D1 J2 P4 L1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_40")),
            Subsignal("clk_p", Pins("R3"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("clk_n", Pins("R2"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("cke", Pins("Y8"), IOStandard("SSTL15_R")),
            Subsignal("odt", Pins("W9"), IOStandard("SSTL15_R")),
            Subsignal("reset_n", Pins("AB5"), IOStandard("LVCMOS15")),
            Subsignal("cs_n", Pins("V9"), IOStandard("SSTL15_R")),
            Misc("SLEW=FAST"),
        )]
        print("using IN_TERM=UNTUNED_SPLIT_40")
    elif args.interm == "50":
        _io += [("ddram", 0,
            Subsignal("a", Pins(
                "U6 V4 W5 V5 AA1 Y2 AB1 AB3",
                "AB2 Y3 W6 Y1 V2 AA3"
                ),
                IOStandard("SSTL15_R")),
            Subsignal("ba", Pins("U5 W4 V7"), IOStandard("SSTL15_R")),
            Subsignal("ras_n", Pins("Y9"), IOStandard("SSTL15_R")),
            Subsignal("cas_n", Pins("Y7"), IOStandard("SSTL15_R")),
            Subsignal("we_n", Pins("V8"), IOStandard("SSTL15_R")),
            Subsignal("dm", Pins("G1 H4 M5 L3"), IOStandard("SSTL15_R")),
            Subsignal("dq", Pins(
                "C2 F1 B1 F3 A1 D2 B2 E2 "
                "J5 H3 K1 H2 J1 G2 H5 G3 "
                "N2 M6 P1 N5 P2 N4 R1 P6 "
                "K3 M2 K4 M3 J6 L5 J4 K6 "
                ),
                IOStandard("SSTL15_R"),
                Misc("IN_TERM=UNTUNED_SPLIT_50")),  # alt is UNTUNED_SPLIT_60 but NONE seems to work better
            Subsignal("dqs_p", Pins("E1 K2 P5 M1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_50")),
            Subsignal("dqs_n", Pins("D1 J2 P4 L1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_50")),
            Subsignal("clk_p", Pins("R3"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("clk_n", Pins("R2"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("cke", Pins("Y8"), IOStandard("SSTL15_R")),
            Subsignal("odt", Pins("W9"), IOStandard("SSTL15_R")),
            Subsignal("reset_n", Pins("AB5"), IOStandard("LVCMOS15")),
            Subsignal("cs_n", Pins("V9"), IOStandard("SSTL15_R")),
            Misc("SLEW=FAST"),
        )]
        print("using IN_TERM=UNTUNED_SPLIT_50")
    elif args.interm == "60":
        _io += [("ddram", 0,
            Subsignal("a", Pins(
                "U6 V4 W5 V5 AA1 Y2 AB1 AB3",
                "AB2 Y3 W6 Y1 V2 AA3"
                ),
                IOStandard("SSTL15_R")),
            Subsignal("ba", Pins("U5 W4 V7"), IOStandard("SSTL15_R")),
            Subsignal("ras_n", Pins("Y9"), IOStandard("SSTL15_R")),
            Subsignal("cas_n", Pins("Y7"), IOStandard("SSTL15_R")),
            Subsignal("we_n", Pins("V8"), IOStandard("SSTL15_R")),
            Subsignal("dm", Pins("G1 H4 M5 L3"), IOStandard("SSTL15_R")),
            Subsignal("dq", Pins(
                "C2 F1 B1 F3 A1 D2 B2 E2 "
                "J5 H3 K1 H2 J1 G2 H5 G3 "
                "N2 M6 P1 N5 P2 N4 R1 P6 "
                "K3 M2 K4 M3 J6 L5 J4 K6 "
                ),
                IOStandard("SSTL15_R"),
                Misc("IN_TERM=UNTUNED_SPLIT_60")),  # alt is UNTUNED_SPLIT_60 but NONE seems to work better
            Subsignal("dqs_p", Pins("E1 K2 P5 M1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_60")),
            Subsignal("dqs_n", Pins("D1 J2 P4 L1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=UNTUNED_SPLIT_60")),
            Subsignal("clk_p", Pins("R3"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("clk_n", Pins("R2"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("cke", Pins("Y8"), IOStandard("SSTL15_R")),
            Subsignal("odt", Pins("W9"), IOStandard("SSTL15_R")),
            Subsignal("reset_n", Pins("AB5"), IOStandard("LVCMOS15")),
            Subsignal("cs_n", Pins("V9"), IOStandard("SSTL15_R")),
            Misc("SLEW=FAST"),
        )]
        print("using IN_TERM=UNTUNED_SPLIT_60")
    elif args.interm == "NONE":
        _io += [("ddram", 0,
            Subsignal("a", Pins(
                "U6 V4 W5 V5 AA1 Y2 AB1 AB3",
                "AB2 Y3 W6 Y1 V2 AA3"
                ),
                IOStandard("SSTL15_R")),
            Subsignal("ba", Pins("U5 W4 V7"), IOStandard("SSTL15_R")),
            Subsignal("ras_n", Pins("Y9"), IOStandard("SSTL15_R")),
            Subsignal("cas_n", Pins("Y7"), IOStandard("SSTL15_R")),
            Subsignal("we_n", Pins("V8"), IOStandard("SSTL15_R")),
            Subsignal("dm", Pins("G1 H4 M5 L3"), IOStandard("SSTL15_R")),
            Subsignal("dq", Pins(
                "C2 F1 B1 F3 A1 D2 B2 E2 "
                "J5 H3 K1 H2 J1 G2 H5 G3 "
                "N2 M6 P1 N5 P2 N4 R1 P6 "
                "K3 M2 K4 M3 J6 L5 J4 K6 "
                ),
                IOStandard("SSTL15_R"),
                Misc("IN_TERM=NONE")),  # alt is UNTUNED_SPLIT_60 but NONE seems to work better
            Subsignal("dqs_p", Pins("E1 K2 P5 M1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=NONE")),
            Subsignal("dqs_n", Pins("D1 J2 P4 L1"), IOStandard("DIFF_SSTL15_R"), Misc("IN_TERM=NONE")),
            Subsignal("clk_p", Pins("R3"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("clk_n", Pins("R2"), IOStandard("DIFF_SSTL15_R")),
            Subsignal("cke", Pins("Y8"), IOStandard("SSTL15_R")),
            Subsignal("odt", Pins("W9"), IOStandard("SSTL15_R")),
            Subsignal("reset_n", Pins("AB5"), IOStandard("LVCMOS15")),
            Subsignal("cs_n", Pins("V9"), IOStandard("SSTL15_R")),
            Misc("SLEW=FAST"),
        )]
        print("using IN_TERM=NONE")

    platform = Platform(part=args.part)
    if args.target == "base":
        soc = BaseSoC(platform)
    elif args.target == "video_overlay":
        soc = VideoOverlaySoC(platform, part=args.part, dqs_phase=args.dqsphase, strength=args.strength)
    builder = Builder(soc, output_dir="build", csr_csv="test/csr.csv")
    vns = builder.build()
    soc.do_exit(vns)

    if args.target == "pcie":
        soc.generate_software_header()

if __name__ == "__main__":
    main()
