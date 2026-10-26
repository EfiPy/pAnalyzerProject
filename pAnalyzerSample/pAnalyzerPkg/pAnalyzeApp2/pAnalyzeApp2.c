
#include  <Uefi.h>
#include  <Library/UefiLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include  <Library/ShellCEntryLib.h>

#include <Protocol/pAnalyze.h>

#define TEST_POLL_INTERVAL_US  100000
#define TEST_MAX_POLLS         100

INTN
EFIAPI
ShellAppMain (
  IN UINTN Argc,
  IN CHAR16 **Argv
  )
{

  UINT64      Count;
  UINTN       Attempt;
  EFI_STATUS  Status;
  EFIPY_PANALYZE_TEST_PROTOCOL *pAnalyzeTestProtocol;

  Count = 0;
  pAnalyzeTestProtocol = NULL;
  Status = gBS->LocateProtocol (&gEfiPypAnalyzeTestProtocol, NULL, (VOID **)&pAnalyzeTestProtocol);
  if (EFI_ERROR (Status)) {
    Print(L"Locate EFIPY_PANALYZE_TEST_PROTOCOL Error %r\n", Status);
    return Status;
  }
  if ((pAnalyzeTestProtocol == NULL) || (pAnalyzeTestProtocol->TestFunc == NULL)) {
    Print(L"Invalid pAnalyzer protocol interface\n");
    return EFI_INVALID_PARAMETER;
  }

  Print(L"pAnalyzer Protocol version:%LX\n", pAnalyzeTestProtocol->Version);

  for (Attempt = 0; Attempt < TEST_MAX_POLLS; Attempt++) {

    Status = gBS->Stall (TEST_POLL_INTERVAL_US);
    if (EFI_ERROR (Status)) {
      Print(L"Stall Error %r\n", Status);
      return Status;
    }
    Status = pAnalyzeTestProtocol->TestFunc(&Count);
    if (EFI_ERROR (Status)) {
      Print(L"pAnalyzer TestFunc Error %r\n", Status);
      return Status;
    }
    Print(L"pAnalyzer Protocol count:%LX\n", Count);

    if (Count > 10) {
      Print(L"This is pAnalyzer application test\n");
      return EFI_SUCCESS;
    }
  }

  Print(L"pAnalyzer protocol test timed out after %u polls\n", TEST_MAX_POLLS);
  return EFI_TIMEOUT;
}
