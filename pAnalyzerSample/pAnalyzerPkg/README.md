# pAnalyzerPkg

供 Python `pAnalyzer` 測試使用的 EDK II 套件，包含兩個 UEFI application 與兩個 DXE driver。將整個 `pAnalyzerPkg` 複製到 EDK II 根目錄即可建置；Python 測試程式位於 `pAnalyzerSample` 及 `pAnalyzer` 目錄。

## 目錄與模組

```text
pAnalyzerPkg/
  pAnalyzerPkg.dec
  pAnalyzerPkg.dsc
  Include/Protocol/pAnalyze.h
  pAnalyzeApp/pAnalyzeApp.c, pAnalyzeApp.inf
  pAnalyzeApp2/pAnalyzeApp2.c, pAnalyzeApp2.inf
  pAnalyzeDrv/pAnalyzeDrv.c, pAnalyzeDrv.inf
  pAnalyzeMultiDrv/pAnalyzeMultiDrv.c, pAnalyzeMultiDrv.inf
```

| 模組 | 類型 | 功能 |
| --- | --- | --- |
| `pAnalyzeApp` | UEFI_APPLICATION | 印出測試訊息後結束，可單獨執行。 |
| `pAnalyzeApp2` | UEFI_APPLICATION | 尋找測試 Protocol，呼叫 `TestFunc()` 並印出計數；需要先載入 driver。 |
| `pAnalyzeDrv` | DXE_DRIVER | 安裝、替換及移除測試 Protocol，提供 `pAnalyzeApp2` 使用的計數介面。 |
| `pAnalyzeMultiDrv` | DXE_DRIVER | 獨立執行 1、2、4 組 Multiple Protocol 安裝、查詢與移除測試；可由 Python 分析端載入。 |

`pAnalyzerPkg.dec` 匯出 `Include` 與三個 Protocol GUID；EDK II 依 INF 的 `[Protocols]` 產生 GUID 定義。GUID 的值與 `Include/Protocol/pAnalyze.h` 相同。

`pAnalyzerPkg.dsc` 建置上述四個模組，支援 `IA32`、`X64` 與 `DEBUG`、`RELEASE`、`NOOPT`。建置依賴 EDK II 的 `MdePkg`、`ShellPkg`，不需要 `AppPkg/Python.dec` 或 Python C library。

## 建置

先準備 EDK II BaseTools、Python 及對應架構的編譯工具鏈，並依 EDK II 的安裝程序完成 BaseTools 與 `Conf` 設定。將整個 `pAnalyzerPkg` 複製到 EDK II 根目錄，與 `MdePkg`、`ShellPkg` 放在同一層：

```text
edk2/
  edksetup.bat
  BaseTools/
  MdePkg/
  ShellPkg/
  pAnalyzerPkg/
    pAnalyzerPkg.dec
    pAnalyzerPkg.dsc
    ...
```

以下使用 Windows **cmd.exe** 與 Visual Studio 2019 的 `VS2019` toolchain。請在 EDK II 根目錄執行：

```bat
edksetup.bat
build -p pAnalyzerPkg/pAnalyzerPkg.dsc -a X64 -b DEBUG -t VS2019
```

此目錄配置不需要額外設定 `PACKAGES_PATH`。其他工具鏈請替換 `-t`，IA32 建置請改用 `-a IA32`。

上述 X64／DEBUG／VS2019 範例的產物位於下列路徑，以 EDK II 根目錄為基準：

```text
Build/pAnalyzerPkg/DEBUG_VS2019/X64/
  pAnalyzeApp.efi
  pAnalyzeApp2.efi
  pAnalyzeDrv.efi
  pAnalyzeMultiDrv.efi
```

編譯完成後，將三個 `.efi` 複製到原專案根目錄下的 `Efi/Apps/pAnalyzerSample/`，供 QEMU 中的 UEFI Shell 執行。

另將 `pAnalyzeMultiDrv.efi` 複製到 `Efi/Apps/pAnalyzer/`，搭配該目錄的 `MultiProtocol.py` 使用，詳見 [C 測試端與 Python 分析端](../../pAnalyzer/README.md)。

Copy the additional `pAnalyzeMultiDrv.efi` to `Efi/Apps/pAnalyzer/` for use with `MultiProtocol.py`. See [C Test Driver and Python Observer](../../pAnalyzer/README.md).

## 在 UEFI Shell 執行

先以 `map -r` 確認 QemuDisk 的裝置代號，切換到該磁碟的 `Efi/Apps/pAnalyzerSample` 目錄後執行：

```text
pAnalyzeApp.efi
load pAnalyzeDrv.efi
pAnalyzeApp2.efi
```

driver 正常完成 `ReinstallProtocolInterface()` 後，對外提供 version 2，`TestFunc()` 每次增加內部計數並回傳兩倍的值。首次載入後，application 預期依序印出 `2、4、6、8、A、C`（十六進位），當計數大於十進位 10 時正常結束。再次執行會沿用 driver 目前的計數。

`pAnalyzeApp2` 每次輪詢前等待 100 ms，最多輪詢 100 次。即使計數沒有增加，也會在約 10 秒加上函式執行時間後回傳 `EFI_TIMEOUT`；遇到 Protocol 呼叫錯誤則立即退出。測試計數不依賴滑鼠；driver 尋找的 `EFI_SIMPLE_POINTER_PROTOCOL` 是選用介面。

重新編譯 driver 後，建議重啟 QEMU 再載入新版，避免仍取得上一版 driver 安裝的 Protocol instance。

## 搭配 Python 測試

- `PaTest.py`：測試文字輸出 Protocol 的攔截及參數修改。
- `PaTest2.py`：目前由 `AppList` 執行 `pAnalyzeApp2.efi`；若 `DrvList` 為空，需先在 Shell 載入 `pAnalyzeDrv.efi`。
- `PaTest3.py`：透過 `DrvList`、`AppList` 依序載入 driver 與執行 application；請確認列表中的路徑與實際檔案位置一致。

三支測試使用 EfiPy2 環境中的 Python interpreter 執行，並直接將紀錄寫入同名 XML 檔案，不需要使用 `>` 重導輸出。

## 常見結果

| 訊息／狀態 | 意義與檢查方向 |
| --- | --- |
| `Locate EFIPY_PANALYZE_TEST_PROTOCOL Error Not Found` | application 已啟動，但找不到測試 Protocol；先確認 driver 安裝成功。 |
| `EFI_TIMEOUT` | 計數未在輪詢上限內超過 10；檢查是否使用新版 driver 與正確的 Protocol instance。 |
| `Load Application Error...` | 檢查 `AppList` 路徑、EFI 架構，以及 Python loader 的實際失敗步驟。目前 `ApplicationExec()` 的部分錯誤分支會以 `UnloadImage()` 結果覆蓋原始錯誤碼。 |
| XML 中出現相同文字的多筆 `OutputString` | 可能是不同層文字輸出 Protocol 的巢狀呼叫，可由 `sAddr` 區分。 |
