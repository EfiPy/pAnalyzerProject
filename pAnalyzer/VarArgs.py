# Copyright (C) 2026 MaxWu efipy.core@gmail.com
# SPDX-License-Identifier: GPL-2.0-only
"""Python-managed X64 EFIAPI interception for the two Multiple Protocol APIs.

The generated entry stub preserves RCX/RDX/R8/R9 and the caller's RSP before
entering ctypes. Python then reads pointer pairs and calls the original entry
with an exact, dynamically constructed prototype. No fixed-size varargs guess,
ctypes modification, or separately compiled bridge is required.
"""

import ctypes
import struct

import EfiPy2 as EfiPy
from pAnalyzer.dOut import xml_attr


MULTIPLE_PROTOCOL_FUNCTIONS = (
    'InstallMultipleProtocolInterfaces',
    'UninstallMultipleProtocolInterfaces',
)


class _X64Arguments(ctypes.Structure):
    _fields_ = [('Registers', ctypes.c_uint64 * 4),
                ('EntryRsp', ctypes.c_uint64)]

    def read(self, index):
        if index < 4:
            return self.Registers[index]
        # Return address + four 8-byte shadow slots precede stack arguments.
        return ctypes.c_uint64.from_address(
            self.EntryRsp + 0x28 + (index - 4) * 8).value


class MultipleProtocolHook:
    """Own the generated entry point and the fixed-argument Python callback.

    max_pairs is a parsing limit, not a fixed native signature. A call above
    the limit is rejected with EFI_INVALID_PARAMETER without calling firmware.
    """

    def __init__(self, name, native_address, function_filter, max_pairs=64):
        from EfiPy2 import _EfiPy2Pre
        if (ctypes.sizeof(ctypes.c_void_p) != 8 or
                _EfiPy2Pre.EFIPY_MDE_CPU_TYPE != _EfiPy2Pre.EFIPY_MDE_CPU_X64):
            raise NotImplementedError('Multiple Protocol hooks require X64 EFIAPI')
        if name not in MULTIPLE_PROTOCOL_FUNCTIONS:
            raise ValueError('Unsupported variadic function: ' + name)
        if max_pairs < 0:
            raise ValueError('max_pairs must not be negative')
        self.name = name
        self.native_address = native_address
        self.function_filter = function_filter
        self.max_pairs = max_pairs
        self.address = 0
        self._busy = False
        self._prototypes = {}
        callback_type = EfiPy.CFUNCTYPE(
            EfiPy.EFI_STATUS, ctypes.POINTER(_X64Arguments))
        self._callback = callback_type(self._dispatch)
        callback_address = ctypes.cast(self._callback, ctypes.c_void_p).value

        # X64 Microsoft/UEFI ABI. Reserve shadow space, an argument snapshot,
        # and padding so RSP is 16-byte aligned before calling the callback.
        code = (
            b'\x48\x83\xec\x68'      # sub rsp, 0x68
            b'\x48\x89\x4c\x24\x20'  # mov [rsp+0x20], rcx
            b'\x48\x89\x54\x24\x28'  # mov [rsp+0x28], rdx
            b'\x4c\x89\x44\x24\x30'  # mov [rsp+0x30], r8
            b'\x4c\x89\x4c\x24\x38'  # mov [rsp+0x38], r9
            b'\x48\x8d\x44\x24\x68'  # lea rax, [rsp+0x68] (entry RSP)
            b'\x48\x89\x44\x24\x40'  # mov [rsp+0x40], rax
            b'\x48\x8d\x4c\x24\x20'  # lea rcx, [rsp+0x20] (snapshot)
            b'\x48\xb8' + struct.pack('<Q', callback_address) +
            b'\xff\xd0'                # call rax
            b'\x48\x83\xc4\x68'      # add rsp, 0x68
            b'\xc3'                     # ret (EFI_STATUS in RAX)
        )
        address = EfiPy.EFI_PHYSICAL_ADDRESS(0)
        status = EfiPy.gBS.AllocatePages(
            EfiPy.AllocateAnyPages, EfiPy.EfiBootServicesCode, 1,
            EfiPy.byref(address))
        if EfiPy.EFI_ERROR(status):
            raise RuntimeError('AllocatePages for varargs hook failed: 0x%X' % status)
        self.address = address.value
        ctypes.memmove(self.address, code, len(code))

    def _capture(self, snapshot):
        handle = snapshot.read(0)
        handle_type = (EfiPy.POINTER(EfiPy.EFI_HANDLE)
                       if self.name == MULTIPLE_PROTOCOL_FUNCTIONS[0]
                       else EfiPy.EFI_HANDLE)
        raw, declarations = [handle], [handle_type]
        # The original Install API rejects a NULL Handle before reading '...'.
        if self.name == MULTIPLE_PROTOCOL_FUNCTIONS[0] and not handle:
            return raw, declarations
        for pair in range(self.max_pairs + 1):
            guid = snapshot.read(1 + pair * 2)
            if not guid:
                raw.append(0)
                declarations.append(EfiPy.POINTER(EfiPy.EFI_GUID))
                return raw, declarations
            if pair == self.max_pairs:
                raise ValueError('Protocol pair count exceeds %d' % self.max_pairs)
            raw.extend((guid, snapshot.read(2 + pair * 2)))
            declarations.extend((EfiPy.POINTER(EfiPy.EFI_GUID), EfiPy.PVOID))
        raise AssertionError('Unreachable')

    def _dispatch(self, context):
        previous_busy = self._busy
        log_before = None
        try:
            raw, declarations = self._capture(context.contents)
            key = tuple(declarations)
            prototype = self._prototypes.get(key)
            if prototype is None:
                prototype = EfiPy.CFUNCTYPE(EfiPy.EFI_STATUS, *declarations)
                self._prototypes[key] = prototype
            args = tuple(ctypes.cast(ctypes.c_void_p(value), declaration)
                         for value, declaration in zip(raw, declarations))
            # Reentry must not change the outer call's declaration or invoke
            # its pre/post callbacks recursively.
            if previous_busy:
                return prototype(self.native_address)(*args)
            self._busy = True
            self.function_filter.Native_func = prototype
            log_before = self.function_filter.dOut.msg
            return self.function_filter(*args)
        except Exception as error:
            # A failed Python pre/post callback must not leave open XML tags.
            if log_before is not None:
                self.function_filter.dOut.msg = log_before
            self.function_filter.dOut.append(
                '<ERROR function="%s" message="%s"/>\n' %
                (xml_attr(self.name), xml_attr(error)))
            return (EfiPy.EFI_INVALID_PARAMETER if isinstance(error, ValueError)
                    else EfiPy.EFI_DEVICE_ERROR)
        finally:
            self._busy = previous_busy

    def __del__(self):
        # The owning analyzer restores the protocol table before releasing us.
        # An executing callback must never free its own return instructions.
        if getattr(self, 'address', 0) and not getattr(self, '_busy', True):
            try:
                EfiPy.gBS.FreePages(self.address, 1)
                self.address = 0
            except Exception:
                pass
