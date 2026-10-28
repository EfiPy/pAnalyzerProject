# Copyright (C) 2026 MaxWu efipy.core@gmail.com
# SPDX-License-Identifier: GPL-2.0-only
"""Python-managed X64 EFIAPI interception for the two Multiple Protocol APIs.

The generated entry stub preserves RCX/RDX/R8/R9 and the caller's RSP before
entering ctypes. Python then reads pointer pairs and calls the original entry
with an exact, dynamically constructed prototype. No fixed-size varargs guess,
ctypes modification, or separately compiled bridge is required.
"""

import ctypes

import EfiPy2 as EfiPy
from pAnalyzer.dOut import xml_attr


MULTIPLE_PROTOCOL_FUNCTIONS = (
    'InstallMultipleProtocolInterfaces',
    'UninstallMultipleProtocolInterfaces',
)


def _build_entry_program(callback_address):
    """Build a CorePy-owned EFIAPI entry without an automatic call frame."""
    import corepy.arch.x86_64.isa as x86
    import corepy.arch.x86_64.types.registers as reg
    from corepy.arch.x86_64.lib.memory import MemRef
    from corepy.arch.x86_64.platform.edk2.spre_edk2_x86_64 import Program

    class EntryProgram(Program):
        def _synthesize_prologue(self):
            self._prologue = []

        def _synthesize_epilogue(self):
            self._epilogue = []

    # Each instruction opts out of CorePy's active stream. A Program's default
    # prologue would change RSP before we capture the original stack arguments.
    instructions = (
        x86.sub(reg.rsp, 0x68, ignore_active=True),
        x86.mov(MemRef(reg.rsp, 0x20), reg.rcx, ignore_active=True),
        x86.mov(MemRef(reg.rsp, 0x28), reg.rdx, ignore_active=True),
        x86.mov(MemRef(reg.rsp, 0x30), reg.r8, ignore_active=True),
        x86.mov(MemRef(reg.rsp, 0x38), reg.r9, ignore_active=True),
        x86.lea(reg.rax, MemRef(reg.rsp, 0x68, data_size=None), ignore_active=True),
        x86.mov(MemRef(reg.rsp, 0x40), reg.rax, ignore_active=True),
        x86.lea(reg.rcx, MemRef(reg.rsp, 0x20, data_size=None), ignore_active=True),
        x86.mov(reg.rax, callback_address, ignore_active=True),
        x86.call(reg.rax, ignore_active=True),
        x86.add(reg.rsp, 0x68, ignore_active=True),
        x86.ret(ignore_active=True),
    )
    program = EntryProgram()
    stream = program.get_stream()
    for instruction in instructions:
        stream.add(instruction)
    program.add(stream)
    return program


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
        if (ctypes.sizeof(ctypes.c_void_p) != 8 or
                EfiPy.EFIPY_MDE_CPU_TYPE != EfiPy.EFIPY_MDE_CPU_X64):
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
        self._entry_program = _build_entry_program(callback_address)
        # get_code_bytes() returns a view of Program.render_code. Retain both
        # the owning Program and the machine-code array while the hook is live.
        self.address, self._code = self._entry_program.get_code_bytes()

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
        # CorePy owns this buffer; never pass it to gBS.FreePages().
        # An executing callback must never release its own return instructions.
        if getattr(self, 'address', 0) and not getattr(self, '_busy', True):
            self.address = 0
            self._code = None
            self._entry_program = None
