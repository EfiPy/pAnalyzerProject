# Copyright (C) 2026 MaxWu efipy.core@gmail.com
# SPDX-License-Identifier: GPL-2.0-only
"""Analyze the separate C driver pAnalyzeMultiDrv.efi.

Run here: python.efi MultiProtocol.py [driver-path]
Only analyzer hooks are installed here; protocol tests run in the C driver.
Results are written to MultiProtocol.xml beside this script.
"""

import sys

import EfiPy2 as EfiPy
from EfiPy2.MdePkg.Protocol import Shell
from pAnalyzer.Panalyzer import pAnalyzer, dOutClass
from pAnalyzer.dOut import xml_attr


def main(driver_path='pAnalyzeMultiDrv.efi'):
    if EfiPy.EFIPY_MDE_CPU_TYPE != EfiPy.EFIPY_MDE_CPU_X64:
        raise RuntimeError('This analyzer sample requires UEFI X64 and EfiPy2/CorePy')
    log = dOutClass(fName=__file__[:-3] + '.xml')
    analyzer = None
    device_path = None
    try:
        log.section('Prepare')
        analyzer = pAnalyzer(log)
        interface = EfiPy.PVOID()
        status = EfiPy.gBS.LocateProtocol(
            EfiPy.byref(Shell.gEfiShellProtocolGuid), None, EfiPy.byref(interface))
        if EfiPy.EFI_ERROR(status):
            raise RuntimeError('Locate Shell protocol failed: 0x%X' % status)
        shell = EfiPy.cast(interface, EfiPy.POINTER(Shell.EFI_SHELL_PROTOCOL)).contents
        device_path = shell.GetDevicePathFromFilePath(driver_path)
        if not device_path:
            raise RuntimeError('Cannot resolve driver path: ' + driver_path)

        log.section('Driver')
        log.append('<Driver Name="%s">\n' % xml_attr(driver_path))
        try:
            status, driver_status = analyzer.DriverLoad(device_path)
            log.append('<return Func="0x%X" Driver="0x%X"/>\n' % (status, driver_status))
        finally:
            log.append('</Driver>\n')
        if EfiPy.EFI_ERROR(status):
            raise RuntimeError('Driver loading failed: 0x%X' % status)
        if EfiPy.EFI_ERROR(driver_status):
            raise RuntimeError('Multi-protocol driver test failed: 0x%X' % driver_status)
    except Exception as error:
        log.append('<ERROR message="%s"/>\n' % xml_attr(error))
        raise
    finally:
        try:
            if analyzer is not None:
                analyzer.stop()
                analyzer._ProtocolFilter.stop()
            if device_path:
                EfiPy.gBS.FreePool(device_path)
        finally:
            log.terminate()
    print('PASS: C driver completed; results: ' + log.fName)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'pAnalyzeMultiDrv.efi')
