/** @file
  Test real C variadic protocol calls independently of the Python observer.
  Copyright (C) 2026 MaxWu efipy.core@gmail.com
  SPDX-License-Identifier: GPL-2.0-only
**/

#include <Uefi.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>

typedef struct {
  UINT32  Version;
  UINTN   Value;
} SAMPLE_PROTOCOL;

typedef struct {
  EFI_HANDLE       Handle;
  EFI_GUID         Guids[4];
  SAMPLE_PROTOCOL  Interfaces[4];
} TEST_CONTEXT;

// Private test GUIDs: these need no declarations in the package DEC.
STATIC EFI_GUID mProtocolGuids[4] = {
  { 0x72FC9000, 0x5AF1, 0x43AC, { 0xA9, 0x81, 0x64, 0x7B, 0xD1, 0x2E, 0x30, 0 } },
  { 0x72FC9001, 0x5AF1, 0x43AC, { 0xA9, 0x81, 0x64, 0x7B, 0xD1, 0x2E, 0x30, 1 } },
  { 0x72FC9002, 0x5AF1, 0x43AC, { 0xA9, 0x81, 0x64, 0x7B, 0xD1, 0x2E, 0x30, 2 } },
  { 0x72FC9003, 0x5AF1, 0x43AC, { 0xA9, 0x81, 0x64, 0x7B, 0xD1, 0x2E, 0x30, 3 } }
};

STATIC EFI_STATUS
CheckAbsent (IN UINTN Count)
{
  EFI_STATUS  Status;
  VOID        *Interface;
  UINTN       Index;

  for (Index = 0; Index < Count; Index++) {
    Interface = NULL;
    Status = gBS->LocateProtocol (&mProtocolGuids[Index], NULL, &Interface);
    if (Status != EFI_NOT_FOUND) {
      return EFI_ERROR (Status) ? Status : EFI_ALREADY_STARTED;
    }
  }
  return EFI_SUCCESS;
}

STATIC EFI_STATUS
InstallProtocols (IN OUT TEST_CONTEXT *Context, IN UINTN Count)
{
  // NULL terminates the GUID positions, not the Interface positions.
  switch (Count) {
    case 1:
      return gBS->InstallMultipleProtocolInterfaces (
                    &Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0], NULL);
    case 2:
      return gBS->InstallMultipleProtocolInterfaces (
                    &Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0],
                    &Context->Guids[1], &Context->Interfaces[1], NULL);
    case 4:
      return gBS->InstallMultipleProtocolInterfaces (
                    &Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0],
                    &Context->Guids[1], &Context->Interfaces[1],
                    &Context->Guids[2], &Context->Interfaces[2],
                    &Context->Guids[3], &Context->Interfaces[3], NULL);
    default:
      return EFI_INVALID_PARAMETER;
  }
}

STATIC EFI_STATUS
UninstallProtocols (IN TEST_CONTEXT *Context, IN UINTN Count)
{
  switch (Count) {
    case 1:
      return gBS->UninstallMultipleProtocolInterfaces (
                    Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0], NULL);
    case 2:
      return gBS->UninstallMultipleProtocolInterfaces (
                    Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0],
                    &Context->Guids[1], &Context->Interfaces[1], NULL);
    case 4:
      return gBS->UninstallMultipleProtocolInterfaces (
                    Context->Handle,
                    &Context->Guids[0], &Context->Interfaces[0],
                    &Context->Guids[1], &Context->Interfaces[1],
                    &Context->Guids[2], &Context->Interfaces[2],
                    &Context->Guids[3], &Context->Interfaces[3], NULL);
    default:
      return EFI_INVALID_PARAMETER;
  }
}

STATIC EFI_STATUS
CleanupProtocols (IN TEST_CONTEXT *Context, IN UINTN Count, OUT BOOLEAN *RetainContext)
{
  EFI_STATUS  Status;
  EFI_STATUS  Result;
  VOID        *Interface;
  UINTN       Index;

  *RetainContext = FALSE;
  if (Context->Handle == NULL) {
    return EFI_SUCCESS;
  }
  Result = UninstallProtocols (Context, Count);
  Print (L"UninstallMultiple (%u pairs): %r\n", (UINT32)Count, Result);

  // Attempt every remaining owned interface after failed rollback/removal.
  for (Index = 0; Index < Count; Index++) {
    Interface = NULL;
    Status = gBS->HandleProtocol (Context->Handle, &Context->Guids[Index], &Interface);
    if (!EFI_ERROR (Status) && (Interface == &Context->Interfaces[Index])) {
      Status = gBS->UninstallProtocolInterface (
                      Context->Handle, &Context->Guids[Index], Interface);
      if (EFI_ERROR (Status)) {
        *RetainContext = TRUE;
        Result = Status;
      }
    } else if (EFI_ERROR (Status) && (Status != EFI_UNSUPPORTED) &&
               (Status != EFI_NOT_FOUND) && (Status != EFI_INVALID_PARAMETER)) {
      *RetainContext = TRUE;
      Result = Status;
    }
  }
  return Result;
}

STATIC EFI_STATUS
RunCase (IN UINTN Count)
{
  TEST_CONTEXT     *Context;
  SAMPLE_PROTOCOL  *Interface;
  EFI_STATUS       Status;
  EFI_STATUS       CleanupStatus;
  BOOLEAN          RetainContext;
  UINTN            Index;

  Status = CheckAbsent (Count);
  if (EFI_ERROR (Status)) {
    Print (L"Sample GUID already present or lookup failed: %r\n", Status);
    return Status;
  }
  Context = AllocateZeroPool (sizeof (*Context));
  if (Context == NULL) {
    return EFI_OUT_OF_RESOURCES;
  }
  for (Index = 0; Index < Count; Index++) {
    Context->Guids[Index] = mProtocolGuids[Index];
    Context->Interfaces[Index].Version = 1;
    Context->Interfaces[Index].Value = 0x100 + Index;
  }

  Status = InstallProtocols (Context, Count);
  Print (L"InstallMultiple (%u pairs): %r\n", (UINT32)Count, Status);
  if (!EFI_ERROR (Status)) {
    for (Index = 0; Index < Count; Index++) {
      Interface = NULL;
      Status = gBS->HandleProtocol (Context->Handle, &Context->Guids[Index], (VOID **)&Interface);
      if (EFI_ERROR (Status)) {
        break;
      }
      if ((Interface != &Context->Interfaces[Index]) ||
          (Interface->Version != 1) || (Interface->Value != 0x100 + Index)) {
        Status = EFI_COMPROMISED_DATA;
        break;
      }
      Print (L"  Protocol %u: Version=%u Value=0x%LX\n",
             (UINT32)Index, Interface->Version, (UINT64)Interface->Value);
    }
  }

  CleanupStatus = CleanupProtocols (Context, Count, &RetainContext);
  if (!RetainContext) {
    FreePool (Context);
  } else {
    // Data-only protocols have no code pointers into this driver's image.
    // Keep their pool storage if firmware refuses removal, even on entry error.
    Print (L"Cleanup incomplete; retaining protocol data at %p\n", Context);
  }
  if (EFI_ERROR (Status)) {
    return Status;
  }
  if (EFI_ERROR (CleanupStatus)) {
    return CleanupStatus;
  }
  Status = CheckAbsent (Count);
  Print (L"%s: %u protocol pair(s)\n", EFI_ERROR (Status) ? L"FAIL" : L"PASS", (UINT32)Count);
  return Status;
}

EFI_STATUS EFIAPI
MultiProtocolDriverEntry (IN EFI_HANDLE ImageHandle, IN EFI_SYSTEM_TABLE *SystemTable)
{
  EFI_STATUS  Status;
  UINTN       Count;

  for (Count = 1; Count <= 4; Count *= 2) {
    Status = RunCase (Count);
    if (EFI_ERROR (Status)) {
      Print (L"Multi-protocol driver test failed: %r\n", Status);
      return Status;
    }
  }
  Print (L"All multi-protocol driver tests passed\n");
  return EFI_SUCCESS;
}
