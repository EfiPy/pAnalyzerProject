# MultiProtocol：C 測試端與 Python 分析端 / C Test Driver and Python Observer

`pAnalyzeMultiDrv.efi` 是測試端，負責安裝、查詢、驗證及移除 1、2、4 組 Protocol。`MultiProtocol.py` 是分析端，只啟用 pAnalyzer hooks、載入 driver 並保存 XML；Python 不再建立測試 Protocol，也不直接呼叫 Multiple Protocol 安裝／移除 API。

`pAnalyzeMultiDrv.efi` installs, queries, validates, and removes 1, 2, and 4 protocol pairs. `MultiProtocol.py` only enables pAnalyzer hooks, loads the driver, and saves XML. Python no longer creates test protocols or directly invokes the Multiple Protocol install/uninstall APIs.

## 建置 / Build

C 原始碼位於 [pAnalyzeMultiDrv](../pAnalyzerSample/pAnalyzerPkg/pAnalyzeMultiDrv/pAnalyzeMultiDrv.c)。將整個 `../pAnalyzerSample/pAnalyzerPkg` 複製到 EDK II 根目錄，再於已設定工具鏈的環境執行：

The C source is in [pAnalyzeMultiDrv](../pAnalyzerSample/pAnalyzerPkg/pAnalyzeMultiDrv/pAnalyzeMultiDrv.c). Copy the entire `../pAnalyzerSample/pAnalyzerPkg` directory into the EDK II root, then run in a configured build environment:

```text
build -p pAnalyzerPkg/pAnalyzerPkg.dsc -m pAnalyzerPkg/pAnalyzeMultiDrv/pAnalyzeMultiDrv.inf -a X64 -b DEBUG -t VS2019
```

將產生的 `Build/pAnalyzerPkg/DEBUG_VS2019/X64/pAnalyzeMultiDrv.efi` 複製到本目錄。工具鏈不同時請替換 `-t`；搭配目前的 VarArgs hooks 時使用 X64。

Copy `Build/pAnalyzerPkg/DEBUG_VS2019/X64/pAnalyzeMultiDrv.efi` into this directory. Substitute the toolchain tag as needed; use X64 with the current VarArgs hooks.

## 執行 / Run

切換到本目錄後執行下列指令。Python 在 hooks 啟用後才載入 driver，driver 執行完畢後還原 hooks，並直接寫入 `MultiProtocol.xml`。

Run from this directory. Python loads the driver after enabling hooks, restores them after execution, and writes `MultiProtocol.xml` directly.

```text
python.efi MultiProtocol.py
```

也可以傳入 driver 的 UEFI 路徑。若只想執行 C 測試、不需分析，可直接在 Shell 執行 `load pAnalyzeMultiDrv.efi`；單獨載入不會產生 Python XML。

You may also pass the driver's UEFI path as an argument. To run the C tests without analysis, use `load pAnalyzeMultiDrv.efi` in the Shell; that alone does not generate Python XML.

## 預期結果 / Expected Results

正常情況下，XML 包含三次 `InstallMultipleProtocolInterfaces` 及三次 `UninstallMultipleProtocolInterfaces`，參數長度分別為 4、6、10（包含 Handle 與結尾 NULL），以及 driver 成功回傳的 `<return Func="0x0" Driver="0x0"/>`。

A normal trace contains three calls each to `InstallMultipleProtocolInterfaces` and `UninstallMultipleProtocolInterfaces`, with argument lengths 4, 6, and 10 including the handle and NULL terminator, followed by `<return Func="0x0" Driver="0x0"/>` for successful driver execution.

畫面輸出與 XML 分開：驗證訊息由 C driver 印出，Python 預設只記錄已啟用 hooks 的 API 呼叫。`LocateProtocol`、`HandleProtocol` 的每次查詢不一定出現在 XML 中。

Validation messages are printed by the C driver, while Python records enabled API hooks. Individual `LocateProtocol` and `HandleProtocol` queries need not appear in XML.
