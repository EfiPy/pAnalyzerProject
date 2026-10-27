# pAnalyzer — UEFI Protocol Analyzer

pAnalyzer 是在 EfiPy2／UEFI Python 環境執行的 Protocol 函式攔截與分析工具。它能記錄呼叫參數、回傳狀態及函式位址，並透過 Python callback 在原始函式執行前修改參數。

pAnalyzer intercepts and analyzes protocol function calls inside the EfiPy2 UEFI Python environment. It records arguments, return statuses, and function addresses, and supports Python callbacks that modify arguments before invoking the original function.

本文以所在目錄為基準，所有主機端路徑均使用相對路徑。這裡的外層 `pAnalyzer/` 是發佈目錄，內層同名 `pAnalyzer/` 才是 Python package。

All host paths in this document are relative to this directory unless stated otherwise. The outer `pAnalyzer/` is the distribution directory; the inner directory with the same name is the Python package.

## 1. 目的 / Purpose

本工具用來觀察 UEFI application 或 driver 對 Protocol 的呼叫，檢查輸入與輸出、測試參數修改，以及追蹤 Protocol 安裝與替換。它直接修改目前 firmware 記憶體中的函式指標，不需要重新編譯被攔截的 firmware 函式。

The tool observes protocol calls made by UEFI applications and drivers, inspects inputs and outputs, tests argument changes, and traces protocol installation and replacement. It changes function pointers in the running firmware's memory without recompiling the intercepted firmware functions.

分析範圍由啟用的 hooks 決定；XML 只包含實際經過這些 hooks 的呼叫，不是整個系統的完整 trace。要記錄自訂 Protocol 的 `TestFunc()`，仍須定義對應的 EfiPy2／ctypes 結構並另外設定攔截。

The enabled hooks determine what is recorded. XML contains calls that pass through those hooks, rather than a complete system trace. Recording a custom protocol's `TestFunc()` requires a matching EfiPy2/ctypes structure and a separately configured hook.

## 2. 執行環境 / Requirements

執行分析需要 UEFI Shell、可存取的檔案系統，以及包含 EfiPy2 與 UEFI ctypes 支援的 Python 環境。目前部署位置使用 Python 3.6.8 的 library 目錄。一般 Windows／Linux Python 可離線解析 XML，但不能直接取得這些 UEFI firmware table 與執行實際攔截。

Runtime analysis requires a UEFI Shell, an accessible filesystem, and a Python environment with EfiPy2 and UEFI ctypes support. The current deployment uses the Python 3.6.8 library directory. Desktop Python can parse saved XML offline, but cannot directly access these UEFI firmware tables or run the live hooks.

## 3. 安裝與部署 / Installation and Deployment

### 3.1 複製 Python library 與 sample / Copy the Library and Samples

將內層 `pAnalyzer` 複製到目標 UEFI Python 的 `site-packages`，將 `pAnalyzerSample` 複製到測試磁碟的 `Efi/Apps`。對目前專案，可在本 README 所在目錄使用下列 PowerShell 指令；目標磁碟須已具備 EfiPy2／Python 環境。

Copy the inner `pAnalyzer` directory into the target UEFI Python's `site-packages`, and copy `pAnalyzerSample` into the test disk's `Efi/Apps` directory. For this repository, run the following PowerShell commands from this README's directory. The destination disk must already contain the EfiPy2/Python runtime.

```powershell
Copy-Item -LiteralPath '.\pAnalyzer' -Destination '..\QemuDisk\Efi\StdLib\lib\python36.8\site-packages' -Recurse -Force
Copy-Item -LiteralPath '.\pAnalyzerSample' -Destination '..\QemuDisk\Efi\Apps' -Recurse -Force
```

此操作會更新同名檔案。請確認實際部署位置包含 `site-packages/pAnalyzer/Panalyzer.py`，避免把外層發佈目錄整個放進 `site-packages`，造成多一層同名目錄。修改本目錄的原始碼後，也需重新部署，才會影響 QemuDisk 上執行的版本。

These commands update files with matching names. Verify that the installed layout contains `site-packages/pAnalyzer/Panalyzer.py`; copying the outer distribution directory would introduce an extra directory level. Changes to this source directory must be deployed again to affect the version running from QemuDisk.

### 3.2 驗證 import / Verify the Import

在 UEFI Python 中執行以下程式，確認實際載入的是哪一份 library。以下測試指令假設 interpreter 可由 Shell 以 `python.efi` 執行；若名稱或位置不同，請替換成目前環境的 interpreter。

Run the following code in UEFI Python to check which library copy is imported. Later command examples assume the interpreter is available in the Shell as `python.efi`; substitute the actual executable name or location when necessary.

```python
import EfiPy2
import pAnalyzer.Panalyzer as analyzer_module
print(analyzer_module.__file__)
```

### 3.3 建置 C 測試程式 / Build the C Test Programs

將 `pAnalyzerSample/pAnalyzerPkg` 整個複製到 EDK II 根目錄，與 `MdePkg`、`ShellPkg` 放在同一層。此配置不需要另外設定 `PACKAGES_PATH`，也不需要 `AppPkg/Python.dec`。

Copy the entire `pAnalyzerSample/pAnalyzerPkg` directory into the EDK II root beside `MdePkg` and `ShellPkg`. This layout does not require an additional `PACKAGES_PATH` setting or `AppPkg/Python.dec`.

```text
edk2/
  BaseTools/
  MdePkg/
  ShellPkg/
  pAnalyzerPkg/
```

在已完成工具鏈設定的 Windows cmd.exe 中，切換到 EDK II 根目錄執行；下例使用 VS2019／X64／DEBUG。

From Windows cmd.exe with the toolchain configured, run the following in the EDK II root. This example selects VS2019, X64, and DEBUG.

```bat
edksetup.bat
build -p pAnalyzerPkg/pAnalyzerPkg.dsc -a X64 -b DEBUG -t VS2019
```

產物位於 EDK II 根目錄下的 `Build/pAnalyzerPkg/DEBUG_VS2019/X64/`。將 `pAnalyzeApp.efi`、`pAnalyzeApp2.efi`、`pAnalyzeDrv.efi` 更新到本目錄的 `pAnalyzerSample`，再部署到測試磁碟。附帶的 binary 與已修改的原始碼不一定同步，原始碼變更後應重新編譯。

The output is under `Build/pAnalyzerPkg/DEBUG_VS2019/X64/` relative to the EDK II root. Update `pAnalyzeApp.efi`, `pAnalyzeApp2.efi`, and `pAnalyzeDrv.efi` in this distribution's `pAnalyzerSample`, then deploy them to the test disk. Bundled binaries may not match later source changes; rebuild after modifying the C code.

更完整的 C 套件說明請參閱 [pAnalyzerPkg README](pAnalyzerSample/pAnalyzerPkg/README.md)。

For additional C package details, see the [pAnalyzerPkg README](pAnalyzerSample/pAnalyzerPkg/README.md).

## 4. 測試流程 / Test Procedures

先使用 UEFI Shell 的 `map -r` 確認磁碟，再切換到該磁碟的 `Efi/Apps/pAnalyzerSample` 目錄。`PaTest2.py`、`PaTest3.py` 的 image 路徑目前以 `FS0:` 開頭；若磁碟映射不同，請修改 `AppList`／`DrvList`。

Use `map -r` in the UEFI Shell to identify the disk, then enter its `Efi/Apps/pAnalyzerSample` directory. Image paths in `PaTest2.py` and `PaTest3.py` currently begin with `FS0:`. Update `AppList` and `DrvList` if your filesystem mapping differs.

三支 sample 會直接將 UTF-8 XML 寫入 script 旁的同名檔案，每次執行覆寫原結果。測試前可先備份要保留的 XML；不要用 `>` 將主控台輸出重導到相同檔案。

Each sample writes UTF-8 XML directly beside the script, replacing the previous file with the same name. Save any results you wish to retain before rerunning a test. Do not redirect console output with `>` into that same XML file.

### 4.1 PaTest：文字輸出攔截與參數修改 / Text Output Hooks and Argument Changes

```text
python.efi PaTest.py
```

`Prepare` 搜尋文字輸出 Protocol instances，建立各函式的 filter，並只啟用 `QueryMode`。`ABCD` 與 `asd` 是刻意使用的不存在名稱，相關 warning 屬於測試內容。

`Prepare` discovers text output protocol instances, creates function filters, and enables only `QueryMode`. The nonexistent names `ABCD` and `asd` deliberately exercise warning paths.

`Testing_1` 執行文字輸出、清畫面與 mode 0／1 查詢；除了明確的查詢，也可能記錄到 firmware 內部發起的 `QueryMode`。不同 instance 支援的模式可能不同，必須連同 `sAddr` 與回傳狀態判讀。

`Testing_1` performs text output, screen clearing, and queries for modes 0 and 1. Firmware-internal `QueryMode` calls may appear alongside the explicit queries. Supported modes can differ by instance, so interpret results together with `sAddr` and the return status.

`Testing_2` 將自訂 `_filter_func` 註冊為 `QueryMode` 的前處理，把 mode 10 改為 0。XML 應出現 `<Change argument="1" before="0xA" after="0x00"/>`，下層呼叫收到 mode 0，並記錄實際查詢結果。

`Testing_2` registers `_filter_func` as the `QueryMode` pre-callback and changes mode 10 to mode 0. XML should contain `<Change argument="1" before="0xA" after="0x00"/>`, with mode 0 passed to the lower-level call and the resulting query output recorded.

`Testing_3` 只對目前 console instance 建立新 filter，啟用攔截並測試 `ClearScreen`，最後停止攔截。結尾 dump 的 `Active` 應等於 `Native`。`Mode` 是資料欄位，`start()` 遍歷到它時會發出 warning 並跳過。

`Testing_3` creates filters for the current console instance, enables interception, tests `ClearScreen`, and stops interception. In the final dump, `Active` should equal `Native`. `Mode` is a data field, so `start()` warns and skips it.

### 4.2 PaTest2：觀察 Application 的文字輸出 / Observe Application Output

```text
python.efi PaTest2.py
```

目前 `DrvList` 為空，`AppList` 只含 `pAnalyzeApp2.efi`。在尚未載入 driver 的乾淨環境執行，預期 application 印出找不到 `EFIPY_PANALYZE_TEST_PROTOCOL`，並回傳 `EFI_NOT_FOUND`。這是觀察 application 失敗路徑的有效情境。

Currently, `DrvList` is empty and `AppList` contains only `pAnalyzeApp2.efi`. In a fresh environment without the driver, the application is expected to report that `EFIPY_PANALYZE_TEST_PROTOCOL` was not found and return `EFI_NOT_FOUND`. This is a valid failure-path observation scenario.

若要測試成功執行，請先載入 driver，再執行 Python sample。driver 成功替換成 version 2 後，首次執行應顯示十六進位計數 `2、4、6、8、A、C` 並正常結束；後續執行沿用 driver 的累積計數。

To test successful execution, load the driver before running the Python sample. After a successful replacement with version 2, the first application run should show hexadecimal counts `2, 4, 6, 8, A, C` and exit successfully. Later runs reuse the driver's accumulated count.

```text
load pAnalyzeDrv.efi
python.efi PaTest2.py
```

此 sample 啟用 `SetAttribute`、`QueryMode`、`OutputString`、`TestString` 的攔截，但 `_filter_func` 目前只有定義、沒有註冊。XML 中的錯誤文字是透過 `OutputString` 間接觀察到的；預設沒有直接攔截 `LocateProtocol`。

This sample enables hooks for `SetAttribute`, `QueryMode`, `OutputString`, and `TestString`, but defines `_filter_func` without registering it. Error text is observed indirectly through `OutputString`; `LocateProtocol` is not directly hooked by default.

### 4.3 PaTest3：由 Engine 載入 Driver 與 Application / Load Both Images Through the Engine

```text
python.efi PaTest3.py
```

建議在重新開機後、尚未手動載入測試 driver 的環境執行此項測試。`PaTest3.py` 先由 `DrvList` 載入 driver，再由 `AppList` 執行 application，主要觀察 Boot Services 的 Protocol 操作。

Run this scenario preferably after a reboot, before manually loading the test driver. `PaTest3.py` loads the driver from `DrvList`, starts the application from `AppList`, and primarily observes protocol operations through Boot Services.

預期看到 `InstallProtocolInterface` 成功、`ReinstallProtocolInterface` 成功、driver 的 `<return Func="0" Driver="0">`，以及 application 的 `<Return Value="0">`。它沒有設定文字輸出或自訂 `TestFunc()` 的攔截，因此成功也不代表 XML 會直接列出每個計數值。

Expected records include successful `InstallProtocolInterface` and `ReinstallProtocolInterface` calls, `<return Func="0" Driver="0">` for the driver, and `<Return Value="0">` for the application. The sample does not configure text output or custom `TestFunc()` hooks, so individual counts need not appear in its XML.

不要把三支 sample 的執行順序視為彼此獨立：UEFI driver 載入後會繼續存在，Protocol 也會保留到重新開機或明確移除。若要比較「未載入 driver」與「已載入 driver」，請使用可確認的初始環境。

The three samples are not isolated from one another. A loaded UEFI driver and its protocols remain present until reboot or explicit removal. Use a known initial state when comparing runs with and without the driver.

## 5. 運作原理 / How It Works

### 5.1 結構辨識與 Instance 搜尋 / Structure Inspection and Instance Discovery

`Build_Capability()` 讀取 ctypes 結構的 `_fields_`，保存每個欄位的 offset、size 與型別，並以 `issubclass(type, ctypes._CFuncPtr)` 辨識函式指標。`Detect_Protocol()` 使用 `LocateHandleBuffer()` 與 `HandleProtocol()` 搜尋現有 instances，將 interface 位址與 handle 加入 `Target`，最後釋放 handle buffer。

`Build_Capability()` reads the ctypes structure's `_fields_`, retaining offsets, sizes, and types, and identifies function pointers with `issubclass(type, ctypes._CFuncPtr)`. `Detect_Protocol()` uses `LocateHandleBuffer()` and `HandleProtocol()` to discover existing instances, stores interfaces and handles in `Target`, and frees the handle buffer afterward.

### 5.2 Filter 的建立與切換 / Filter Creation and Pointer Replacement

`Build_Filter()` 從 interface 欄位讀出原始函式位址，使用相同 ctypes 函式型別建立 Python callback，並保存 callback 的參考。`install()` 只設定前後處理函式；真正將 live interface 指向 callback 的操作是 `start()`。

`Build_Filter()` reads original function addresses from the interface, creates Python callbacks using the same ctypes function types, and retains references to those callbacks. `install()` configures pre/post callbacks; `start()` performs the actual replacement in the live interface.

```text
Caller / 呼叫端
    |
    v
Live protocol function pointer / Protocol 目前的函式指標
    |
    v
Python callback
    |-- Record Input / 記錄輸入
    |-- Pre_func(dOut, *args)
    |-- Call saved Native_addr / 呼叫保存的原始位址
    |-- Post_func(dOut, result, *args)
    |-- Record Output / 記錄輸出
    v
Return original result / 回傳原始結果
```

callback 呼叫保存的 `Native_addr`，而不是再次從已被替換的 interface 欄位呼叫自己。`stop()`／`uninstall()` 會在欄位仍指向本 analyzer 的 filter 時還原原始位址；callback 物件在攔截期間必須持續存在。

The callback invokes the saved `Native_addr` rather than calling itself through the replaced interface field. `stop()` and `uninstall()` restore original pointers when the field still points to that analyzer's filter. Callback objects must remain alive throughout interception.

### 5.3 前後處理的介面 / Callback Contracts

前處理與後處理都回傳 `(fRest, args)`；目前 engine 使用回傳的 `args`，但不使用 `fRest` 覆寫原始回傳值，也不會因此略過原始函式。前處理可改變送入 native function 的參數；後處理可檢查結果及修改指向的資料。

Both callback types return `(fRest, args)`. The current engine uses the returned `args`, but does not use `fRest` to override the native return value or skip the native call. A pre-callback can change arguments sent to the native function; a post-callback can inspect the result and modify pointed-to data.

```python
def pre_func(dOut, *args):
    # QueryMode: args[0] = This, args[1] = ModeNumber
    if args[1] != 0:
        dOut.append('<Change argument="1" before="0x%X" after="0x00"/>\n' % args[1])
        args = (args[0], 0) + args[2:]
    return None, args

def post_func(dOut, result, *args):
    return None, args

# After Build_Filter() / 建立 filter 之後
analyzer.install('QueryMode', Pre_func=pre_func, Post_func=post_func)
analyzer.start('QueryMode')
```

### 5.4 Boot Services 的攔截範圍 / Boot Services Hook Coverage

`pAnalyzer` 建構時會建立內部 `_ProtocolFilter`。目前 `ProtocolFuncList` 預設啟用以下三項；`LoadEfiFiles()` 另外啟用 `HandleProtocol`。`DriverLoad()` 與 `ApplicationExec()` 在執行目標 image 前後切換預設 hooks。

The `pAnalyzer` constructor creates an internal `_ProtocolFilter`. `ProtocolFuncList` enables the following three hooks by default, while `LoadEfiFiles()` additionally enables `HandleProtocol`. `DriverLoad()` and `ApplicationExec()` switch the default hooks around execution of the target image.

```python
('InstallProtocolInterface', None)
('ReinstallProtocolInterface', None)
('UninstallProtocolInterface', None)
```

`LocateProtocol`、`InstallMultipleProtocolInterfaces`、`UninstallMultipleProtocolInterfaces` 等項目目前被註解。取消某個項目的註解，只表示開始攔截該項 API；不能據此把其他未記錄的操作視為沒執行。可變參數 API 的攔截還需要確認 ctypes 宣告能正確處理該呼叫，不能只靠取消註解就視為驗證完成。

Entries such as `LocateProtocol`, `InstallMultipleProtocolInterfaces`, and `UninstallMultipleProtocolInterfaces` are currently commented out. Enabling one adds coverage for that API; missing records for other APIs do not prove they were not called. Variadic APIs also require a suitable ctypes declaration and validation, beyond simply enabling their list entries.

目前沒有重入保護。自訂 callback 若再次呼叫正在攔截的同一個 Boot Service，可能形成遞迴。現有紀錄先累積在記憶體，避免每個 hook 都立即執行檔案 I/O；但累積紀錄也會增加記憶體使用量。

There is currently no reentrancy guard. A custom callback that calls the same hooked Boot Service can recurse. Logs are buffered in memory instead of performing file I/O on every hook, at the cost of increasing memory use as the trace grows.

## 6. XML 判讀與離線分析 / XML Interpretation and Offline Analysis

XML 根元素為 `Panalyzer`；`Section` 區分測試階段，`Function` 可能代表函式呼叫，也可能只是 `Dump` 裡的位址描述。分析實際呼叫時，應選擇具有 `Input` 的 `Function`。巢狀 `Function` 可呈現不同 Protocol instances 之間的呼叫關係。

The root element is `Panalyzer`. `Section` separates test phases, while `Function` can represent either an actual call or an address description inside `Dump`. Select functions with an `Input` child when analyzing calls. Nested `Function` elements can represent calls between protocol instances.

| 欄位 / Field | 意義 / Meaning |
| --- | --- |
| `Native` | 保存的原始函式位址。 / Saved original function address. |
| `filter` | Python C callback 的位址。 / Address of the Python C callback. |
| `Active` | 顯示目前指向 `Native` 或 `filter`；若位址與兩者皆不同，則保留該位址供檢查。 / Shows whether the current pointer targets `Native` or `filter`; an address matching neither is displayed as an address for inspection. |
| `fAddre` | 本次呼叫對應的原始函式位址，保留目前輸出的欄位拼字。 / Original function address for a call; this spelling matches the current output. |
| `sAddr` | 此次呼叫所屬的 interface instance 位址。 / Interface instance address associated with the call. |
| `Type` | 以函式宣告與 ctypes 型別轉換為 C／EDK 型別名稱，例如 `GUID *`、`VOID **`、`UINTN`。 / C/EDK type names derived from the function declaration and ctypes types, such as `GUID *`, `VOID **`, and `UINTN`. |
| `Input`、`Output` | 呼叫前後的參數快照；`Output` 的 `Value` 是函式回傳值。 / Argument snapshots before and after a call; `Output.Value` is the return value. |
| `Change` | sample 自訂前處理所記錄的參數修改。 / An argument change recorded by a sample pre-callback. |
| `Data` | 結構中的非函式欄位，例如文字輸出 Protocol 的 `Mode`。 / A non-function structure field, such as the text output protocol's `Mode`. |
| `Return` | application 的結束狀態。 / Application exit status. |
| `return Func / Driver` | driver 載入流程狀態及 entry point 執行結果。 / Driver loading-flow status and entry-point result. |

`Type` 會保留指標層數；`c_void_p` 顯示為 `VOID *`，`LP_c_void_p` 顯示為 `VOID **`。同一 ctypes 型別的 typedef 別名無法完全還原，因此 native-width 整數統一以 `INTN`／`UINTN` 呈現，例如 `EFI_STATUS` 可能顯示為 `UINTN`。

`Type` preserves pointer depth: `c_void_p` becomes `VOID *`, while `LP_c_void_p` becomes `VOID **`. Typedef aliases sharing a ctypes type cannot be recovered exactly. Native-width integers are displayed as `INTN` or `UINTN`; for example, `EFI_STATUS` may appear as `UINTN`.

`Output` 中的 `0x0` 通常表示成功，不是「全部位址為零」的舊問題。mode 0 回傳的 `0x50`／`0x19` 表示 80 欄、25 列；OUT 參數在 `Input` 中的舊內容不保證已初始化，應以成功呼叫後的值判讀。

An `Output` status of `0x0` normally indicates success and is distinct from the former all-zero address issue. Values `0x50` and `0x19` for a mode query mean 80 columns and 25 rows. OUT parameters may contain uninitialized data in `Input`; interpret their values after a successful call.

下面的 Python 程式可在一般主機執行。請先切換到保存 XML 的目錄，再統計實際呼叫及 application 回傳狀態。

The following script runs on desktop Python. Change to the directory containing the XML before counting actual calls and inspecting application return statuses.

```python
import xml.etree.ElementTree as ET
from collections import Counter

root = ET.parse('PaTest3.xml').getroot()
calls = [node for node in root.iter('Function') if node.find('Input') is not None]
print(Counter(node.attrib['name'] for node in calls))

for node in calls:
    output = node.find('Output')
    if output is not None:
        print(node.attrib['name'], output.attrib.get('Value'))

for app in root.findall('.//Application'):
    result = app.find('Return')
    print(app.attrib['Name'], None if result is None else result.attrib)
```

隨附的 XML 是既有執行紀錄，不是所有環境都應逐位元相同的標準答案。例如目前 `PaTest2.xml` 保存 Protocol 不存在時的結果，`PaTest3.xml` 則保存成功結果；位址、instance 數量與顯示模式都可能隨執行環境改變。

The bundled XML files are captured runs, not byte-for-byte golden results for every environment. For example, the current `PaTest2.xml` records a missing protocol, while `PaTest3.xml` records success. Addresses, instance counts, and display modes can vary between runs.
