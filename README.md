# NeTV2 LiteX Quickstart Guide

tl;dr:


These instructions can be used to quickly start development.

1. Check out this repo with `git clone --recurse-submodules https://github.com/xobs/netv2-fpga.git`.
1. Ensure you have Python 3.5 or newer installed.
1. Ensure you have `make` installed.
1. Download the Risc-V toolchain from https://www.sifive.com/products/tools/ and put it in your PATH.
1. Go to https://www.xilinx.com/support/download.html and download `All OS installer Single-File Download`
1. Do a minimal Xilinx install to /opt/Xilinx/, and untick everything except `Design Tools / Vivado Design Suite / Vivado` and `Devices / Production Devices / 7 Series`
1. Go to https://www.xilinx.com/member/forms/license-form.html, get a license, and place it in ~/.Xilinx/Xilinx.lic
1. Run `./build.py` (or `python3 ./build.py`)

## Rationale

NeTV2 uses Migen for its HDL, and uses many components from the LiteX project.
These are primarily written in Python, which has a large number of options
available for configuring installs, ranging from global installs, virutlalenv, conda,
as well as several others.  Everyone has an opinion on what's right.

These instructions ignore all of that, in favor of simplicity.  You likely already
have a copy of `make` and `python`, and you probably ought to have a compiler
installed for other projects.  It's also more challenging to work on submodules
when they're combined together in a `site-packages` repository.

This quickstart takes a different approach in that it doubles-down on using native
components and simply modifies several magical environment variables to make
it all work.  As a bonus, it works on platforms where Conda doesn't, such as
platforms where packages might not be available.

## Support programs

There is a wrapper script in this repo to run litex_server and litex_term as well.  These may be invoked either with python (`python bin/litex_server udp`) or on Unix-type systems they may be executed directly (`./bin/litex_server udp`).

## Xilinx PATH

If your Xilinx install is in the default path (`C:\\Xilinx` on Windows, `/opt/Xilinx` on Linux), then the build system should be able to automatically find Xilinx.

If not, you can add the `bin` directory to your PATH.

## PyCharm integration

Without setting environment variables, PyCharm won't know about litex/migen modules, and will give you lots of errors.

Get a list of environment variables to set by running `build.py --print-env > project.env`.  Then add those to the pycharm configuration.

1. Install the `Env File` plugin.  *Preferences* -> *Plugins* -> *Browse repositories...* -> search for `Env File` -> *Install Plugin*
1. Go to *Run* -> *Edit Configurations*
1. Click *EnvFile*, tick *Enable EnvFile*, and click the *+* to browse for `project.env`

More information at:

https://stackoverflow.com/questions/42708389/how-to-set-environment-variables-in-pycharm

## Visual Studio Code integration

Visual Studio Code needs to know where modules are.  These are specified in environment variables, which are automatically read from a .env file in your project root.  Create this file to enable pylint and debugging in Visual Studio Code:

````sh
python build.py --print-env > .env
````