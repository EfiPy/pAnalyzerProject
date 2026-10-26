#
# PaTest2.py
#
# Copyright (C) 2015 - 2026 MaxWu efipy.core@gmail.com All rights reserved.
#
# Panalyzer.py is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# PaTest.py is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EfiPy.  If not, see <http://www.gnu.org/licenses/>.
#

from pAnalyzer.Panalyzer import *

from EfiPy2.MdePkg.Protocol.SimpleTextOut import gEfiSimpleTextOutProtocolGuid, EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL, EFI_TEXT_CLEAR_SCREEN
from EfiPy2.MdePkg.Protocol.SimpleTextIn  import gEfiSimpleTextInProtocolGuid,  EFI_SIMPLE_TEXT_INPUT_PROTOCOL

if __name__ == "__main__":

  def _filter_func (dOut, *args):

    if args[1] != 0x00:
      dOut.append ('<Change argument="1" before="0x%X" after="0x00"/>\n' % args[1])
      args = (args[0], 0x00) + args[2:]

    return None, args

  DrvList = []
  # AppList = ["FS0:\\EFI\\Apps\\pAnalyzerSample\\pAnalyzeApp2.efi", "aaa.py"]
  AppList = ["FS0:\\EFI\\Apps\\pAnalyzerSample\\pAnalyzeApp2.efi"]

  print ("================================")

  dOut = dOutClass(fName=__file__[:-3] + '.xml')

  dOut.section("Prepare")

  t = pAnalyzer(dOut)
  
  t.Build_Capability (EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL)
  t.Detect_Protocol (gEfiSimpleTextOutProtocolGuid, EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL)
  
  for target, handle in t.Target:
    t.Filter.append (t.Build_Filter (target, handle))
  
  t.install("Reset")
  t.install("ABCD")
  t.install("OutputString")
  t.install("TestString")
  t.install("QueryMode")
  t.install("SetMode")
  t.install("SetAttribute")
  t.install("ClearScreen")
  t.install("SetCursorPosition")

  t.start("SetAttribute")
  t.start("QueryMode")
  t.start("OutputString")
  t.start("TestString")
  t.debug_dump ()

  dOut.section("Testing_1")

  t.LoadEfiFiles (DrvList, AppList)

  del (t)

  dOut.terminate ()
