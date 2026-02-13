#Include \\DESKTOP-KIAEFEG\share\lib\ft.ahk
; #Include C:\Users\cpst\Documents\AutoHotkey\Lib\ft.ahk
#NoEnv
#SingleInstance, force
#Persistent
; #HotKeyInterval 1
; #MaxHotkeysPerInterval 127
DetectHiddenWindows, On
SetKeyDelay,-1, 1
SetControlDelay, -1
SetWinDelay,-1
SetBatchLines,-1
SetWorkingDir,%a_scriptdir%
PID := DllCall("GetCurrentProcessId")
Process, Priority, %PID%, High

win:="MapleStory Worlds"

mult := 1 ; 배율 수정시 바클 창도 수정 됨

; findText 좌표
size_w := 16 + (854*mult)
size_h := 39 + (480*mult)
map_sx := 280  * mult, map_sy := 0 * mult, map_dx := map_sx + 100 * mult, map_dy :=  map_sy + 13 * mult
xy_sx := 640 * mult, xy_sy := 456 * mult, xy_dx := xy_sx + 88 * mult, xy_dy := xy_sy + 12 * mult
hp_sx := 650 * mult, hp_sy := 403 * mult, hp_dx := hp_sx + 82 * mult, hp_dy := hp_sy + 12 * mult
mp_sx := 650 * mult, mp_sy := 416 * mult, mp_dx := mp_sx + 82 * mult, mp_dy := mp_sy + 12 * mult
status_sx := 560 * mult, status_sy := 200 * mult, status_dx := status_sx + 150 * mult, status_dy := status_sy + 13 * mult ;62-12

; status_sx := 560 * mult, status_sy := 200 * mult, status_dx := status_sx + 150 * mult, status_dy := status_sy + 65 * mult ; 빈화면 확인

win := "MapleStory Worlds"

;숫자 데이터
Text.="<0>*0$8.62F2aNaNaNZ291W"
Text.="|<1>*0$8.62F4V6EY92N1Ubm"
Text.="|<2>*0$9.714EImOEG4VCEA2TY"
Text.="|<3>*0$9.7l1E9m4V44FmEI4T4"
Text.="|<4>*0$8.1UYF8IaNUM5t2EO"
Text.="|<5>*0$9.7l18GQEW2CFWEY8S4"
Text.="|<6>*0$8.3V4WH4+NaN62F3W"
Text.="|<7>*0$8.DY61SF8YG8WEY62"
Text.="|<8>*0$9.7V2H+F8G4aImYG4D4"
Text.="|<9>*0$8.7299aNa1EX94W72"
Text.="|<1>**100$38.000401E4S1y2I10UE3p0EF001Ty8Hzao08421ZDky48ZE48F20I12AE05DUQ7w0M"

; 부여관령, 상곡, 읍루, 범안, 송원, 장훈
MapText.="|<입구>**100$9.E/x0jx07j50c54"
MapText.="|<흉가1>**50$4.zlqNbky"   
MapText.="|<흉가2>**50$5.zhrfRrw7s"   
MapText.="|<흉가3>**100$4.wQvNvUy"   
MapText.="|<흉가4>**100$6.DNFldd0t9DU"  
MapText.="|<흉가5>**100$4.w7QS/Uy"   
MapText.="|<흉가6>**100$5.TWpkaBO7s"  
MapText.="|<흉가7>**100$4.wCLNieu"  
MapText.="|<흉가8>**100$4.yKMVNUy"  
MapText.="|<흉가9>**100$4.yKNUvVy"   
MapText.="|<흉가10>**100$10.wyqFqbONdabORUkzy" 

global LogMessages := [] ; 로그 배열
global iniPath := "\\DESKTOP-KIAEFEG\share\env\Slave.ini"
global target := "\\DESKTOP-KIAEFEG\share\env\Master.ini"
; iniPath := "C:\Users\cpst\Documents\AutoHotkey\Env\Slave.ini"
; target := "C:\Users\cpst\Documents\AutoHotkey\Env\Master.ini"
Slave := false ; Slave 상태
Macro := false ; 매크로 상태
Debuff := false ; 혼마술 On/Off
Shout := false ; 사자후
NextMap := false ; 다음맵 넘어가야함
TapFound := false
RetryTab := false ; 탭탭다시
Protect := false ; 보무
Invincible := false ; 금강
global hp, mp, x_coord, y_coord, status ; Slave 자신의 체력을 알기 위해 전역 선언
global EventX, EventY
global xyData := {}
global eventData := {}

global Ghost := {}
Ghost[1] := [7, 2, 6, 28]
Ghost[2] := [11, 23, 21, 14] ; [3], [4]빽굴(3에서 2굴가는길)
Ghost[3] := [23, 0, 23, 29] 
Ghost[4] := [16, 9, 9, 29] 
Ghost[5] := [5, 0, 22, 29] 
Ghost[6] := [17, 1, 18, 24] ; (db는 16, 3) 
Ghost[7] := [24, 0, 1, 29] ;
Ghost[8] := [5, 15, 14, 23] ;
Ghost[9] := [13, 1, 16, 7] ; (db는 12, 3)
Ghost[10] := [21, 2]

; 🎨 GUI 생성
Gui, +AlwaysOnTop
Gui, Show, w310 h440, Slave 상태 ; GUI 크기
Gui, Font, s11, Arial 
Gui, Add, Text, x10 y10 w260 h30 vSlave, [상태]: Off 🔴
Gui, Add, Text, x10 y40 w260 h30 vMacro, [매크로]: Off 🔴
Gui, Add, Text, x10 y70 w260 h30 vDebuff, [혼마술]: Off 🔴
Gui, Font, s10, Arial 

Gui, Font, s8, Arial 
Gui, Add, Button, x195 y10 w50 h25 gLoadStats, Upload
Gui, Add, Button, x250 y10 w50 h25 gReloadScript, Reload

Gui, Font, s10, Arial 
Gui, Add, Text, x10 y100 w260 h25 vMasterHp, Master 체력: -
Gui, Add, Text, x10 y125 w260 h25 vMasterMp, Master 마력: -
Gui, Add, Text, x10 y150 w260 h25 vSlaveHp, Slave 체력: -
Gui, Add, Text, x10 y175 w260 h25 vSlaveMp, Slave 마력: -
Gui, Add, Text, x10 y200 w260 h25 vMap, Map: -
Gui, Add, Text, x10  y225 w260 h30 vShoutText, 사자후:

Gui, Font, s8, Arial  ; 로그 박스 글씨 크기 작게 설정
Gui, Add, Edit, x10 y250 w290 h180 vLogBox -VScroll -ReadOnly ; 로그 창 (크기 증가)

SetTimer, CheckCommands, 500 ; 원격 커맨드를 읽기 위한 타이머

return

LoadStats:
    IniRead, MasterHP, %target%, Stats, MasterHP
    IniRead, MasterMP, %target%, Stats, MasterMP
    IniRead, SlaveHP, %target%, Stats, SlaveHP
    IniRead, SlaveMP, %target%, Stats, SlaveMP
    IniRead, ShoutText, %target%, Stats, ShoutText

    GuiControl,, MasterHp, Master 체력: %MasterHP%
    GuiControl,, MasterMp, Master 마력: %MasterMP%
    GuiControl,, SlaveHp, Slave 체력: %SlaveHP%
    GuiControl,, SlaveMp, Slave 마력: %SlaveMP%
    GuiControl,, ShoutText, 사자후: %ShoutText%
return 


CheckCommands:
   ; Ini 파일이 존재하는지 확인
   if (FileExist(target)) {
       ; [Commands] 섹션의 모든 키를 읽어옴

       IniRead, value, %target%, Commands, KeyToPress

        ; 명령 처리
        if (value = "F1") {
            AppendLog("F1 명령 수신(Status)")
            Send {F1}  ; F2 키를 누름
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F2") {
            AppendLog("F2 명령 수신(Macro)")
            Send {F2}  ; F3 키를 누름
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F3") {
            AppendLog("F3 명령 수신(Debuff)")
            Send {F3}  ; F4 키를 누름
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F4") {
            AppendLog("F4 명령 수신(Shout)")
            Send {F4}  ; F4 키를 누름
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "Up") {
            AppendLog("[방향키] Up 명령 수신")
            Send {Up}  ; 
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "Down") {
            AppendLog("[방향키] Down 명령 수신")
            Send {Down}  
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "Left") {
            AppendLog("[방향키] Left 명령 수신")
            Send {Left}  
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "Right") {
            AppendLog("[방향키] Right 명령 수신")
            Send {Right}  
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "Tab") {
            AppendLog("[긴급] 탭탭 다시잡음")
            GoSub, TabTab
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F8") {
            AppendLog("보무 수동 수신")
            Protect := true
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F7") {
            AppendLog("금강 On/Off 수신")
            Invincible := !Invincible
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F11") {
            AppendLog("[수동] 이전굴로 넘어갑니다.")
            NextMap := true
            BackMap := false
            IniDelete, %target%, Commands, KeyToPress
        } else if (value = "F12") {
            AppendLog("[수동] 다음굴로 넘어갑니다.")
            NextMap := false
            BackMap := true
            IniDelete, %target%, Commands, KeyToPress
        }

    }
return

f1::
    if !WinActive("ahk_exe msw.exe") {
        return
    }

    WinMove, %win%, , , , %size_w%,%size_h%

    if (!FileExist(iniPath)) { ; 🔹 .ini 파일 존재 여부 확인
        AppendLog("파일을 찾을 수 없음: " . iniPath)
        return
    }
    
    Slave := !Slave  ; 상태 토글 (true ↔ false)

    if (Slave) {
        SetTimer, Slave, 400
        ; SetTimer, Follow, 100
    } else {
        SetTimer, Slave, Off
        SetTimer, Follow, Off
        Macro := false
        Debuff := false
        Shout := false
        NextMap := false
        RetryTab := false
        xyData := {}
        eventData := {}
    }

    GuiControl,, Slave, % (Slave ? "[상태]: On 🟢" : "[상태]: Off 🔴")
    GuiControl,, Macro, % (Macro ? "[매크로]: On 🟢" : "[매크로]: Off 🔴")
    GuiControl,, Debuff, % (Debuff ? "[혼마술]: On 🟢" : "[혼마술]: Off 🔴")

return 

f2:: 
    if !WinActive("ahk_exe msw.exe") {
        return
    }

    if (!FileExist(target)) { ; 🔹 .ini 파일 존재 여부 확인
        AppendLog("파일을 찾을 수 없음: " . target)
        return
    }

    if (!Slave) { ; Slave Off 상태에서 매크로를 키려고 할 때 [살패]
        AppendLog("[ERROR] F1을 눌러 Slave 준비 필요")
        return
    }


    Macro := !Macro

    if (!Macro) {
        NextMap := false
        Debuff := false
        RetryTab := false
        SetTimer, Follow, Off
    }

    GuiControl,, Macro, % (Macro ? "[매크로]: On 🟢" : "[매크로]: Off 🔴")
    GuiControl,, Debuff, % (Debuff ? "[혼마술]: On 🟢" : "[혼마술]: Off 🔴")
        
return 

f3::
    if !WinActive("ahk_exe msw.exe") {
        return
    }

    if (!FileExist(target)) { ; 🔹 .ini 파일 존재 여부 확인
        AppendLog("파일을 찾을 수 없음: " . target)
        return
    }

    if (!Slave) { ; Slave Off 상태에서 혼마술을 키려고 할 때 [실패]
        AppendLog("[ERROR] F1을 눌러 Slave 준비 필요")
        return
    }    

    if (Debuff) {
        Debuff := false
    } else {
        Debuff := true
        Macro := true 
    }

    GuiControl,, Macro, % (Macro ? "[매크로]: On 🟢" : "[매크로]: Off 🔴")
    GuiControl,, Debuff, % (Debuff ? "[혼마술]: On 🟢" : "[혼마술]: Off 🔴")
return 

F4::
    if !WinActive("ahk_exe msw.exe") {
        return
    }

    if (!FileExist(target)) { ; 🔹 .ini 파일 존재 여부 확인
        AppendLog("파일을 찾을 수 없음: " . target)
        return
    }

    if (!Slave) { ; Slave Off 상태에서 사자후를 할 때 [실패]
        AppendLog("[ERROR] F1을 눌러 Slave 준비 필요")
        return
    }

    Shout := !Shout

return 

+F4::
    Reload
return

Slave:
    if (Slave) {
        FindText().BindWindow(WinExist(win),4)  ;비활성 입력    
        start_time := A_TickCount 
        WinGetPos, pX, pY, pW, pH, %win%
        FindText().ScreenShot()
        map := searchsort(win,map_sx + pX, map_sy + pY, map_dx + pX, map_dy + pY,MapText,,,mult,mult) ;맵이름
        xy := searchsort(win,xy_sx + pX, xy_sy + pY, xy_dx + pX, xy_dy + pY,Text,,,mult,mult) ;좌표 x := SubStr(xy, 1, 4) , y := SubStr(xy, 5, 4)
        hp := searchsort(win,hp_sx + pX, hp_sy + pY, hp_dx + pX, hp_dy + pY, Text,,0.7,mult,mult) ;체력
        mp := searchsort(win,mp_sx + pX, mp_sy + pY, mp_dx + pX, mp_dy + pY, Text,,0.7,mult,mult) ;마력
        status := searchsort(win,status_sx + pX, status_sy + pY, status_dx + pX, status_dy + pY, Text,,0.7,mult,mult) ; 상태창
        x_coord := SubStr(xy, 1, 4) + 0
        y_coord := SubStr(xy, 5, 4) + 0

        ; 🔹 .ini 파일에 값 저장
        IniWrite, %hp%, %iniPath%, SlaveStatus, HP
        IniWrite, %mp%, %iniPath%, SlaveStatus, MP
        IniWrite, %x_coord%, %iniPath%, SlaveStatus, X_Coord
        IniWrite, %y_coord%, %iniPath%, SlaveStatus, Y_Coord

        ; GUI 업데이트
        GuiControl,, HpStatus, 체력: %hp%
        GuiControl,, MpStatus, 마력: %mp%
        GuiControl,, ExpStatus, 경험치: %exp%
        GuiControl,, Map, 맵: %map%
        GuiControl,, XYStatus, 좌표: X - %x_coord%, Y - %y_coord%

        if (Macro && !Debuff && !Shout) {
            Gosub, Macro
        }

        if (Debuff && !Shout) {
            Gosub, Debuff
        }

        if (Shout) {
            Gosub, Shout
        }

        last_Time := A_TickCount - start_time
        IniWrite, %last_Time%, %iniPath%, SlaveStatus, ResponseTime
        GuiControl,, TimeStatus, 실행 시간: %last_Time% ms

        FindText().BindWindow(0)
    } 

return



Macro:
    if (Macro && !NextMap) {
        IniRead, MasterNowHp, %target%, MasterStatus, HP
        IniRead, MasterNowMP, %target%, MasterStatus, MP
        IniRead, MasterHp, %target%, Stats, MasterHP
        IniRead, MasterMp, %target%, Stats, MasterMP
        IniRead, SlaveHp, %target%, Stats, SlaveHP
        IniRead, SlaveMp, %target%, Stats, SlaveMP

        
        if(status != 1 && Invincible = true) {
            Send, {s}
            AppendLog("[Slave] 금강불체 시도")
            Send, 0
        }

        ; Slave 마력 확인
        if ( mp = 0) {
            SetTimer, Follow, Off
            ; AppendLog("[Slave] 마력 부족(" . mp . "), 공증 시도" . "(기준 : " . SlaveMp . ")")
            Send, {Esc}
            Sleep, 70
            Send, {Ctrl Down}
            Sleep, 70
            Send, a
            Sleep, 70
            Send, {Ctrl Up}
            Send, 2
        } else if ( mp < SlaveMp  ) {
            Send, 2
        }

        ; Slave 체력 확인
        if(hp = 0) {
            SetTimer, Follow, Off
            Send, {Esc}
            Sleep, 70
            Send, 9
            Sleep, 70
            Send, {Home}
            Sleep, 70
            Send, {Enter}
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, {Enter}
        }   else if ( hp < (SlaveHp * 0.15) ) {
            SetTimer, Follow, Off
            Send, {Esc}
            Sleep, 70
            Send, 1
            Sleep, 70
            Send, {Home}
            Sleep, 70
            Send, {Enter}
        }   else if ( hp < SlaveHp ) {
            SetTimer, Follow, Off
            ; AppendLog("[Slave] 위험(" . hp . "), 체력 회복(기준 : " . SlaveHp . ")" )
            Send, {Esc}
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, {Home}
            Sleep, 70
            Send, {Enter}
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, {Enter}
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, {Enter}
            Sleep, 70 
            Send, 3
            Sleep, 70
            Send, {Enter} 
        }  else {
            SetTimer, Follow, 100
        }

        if(Protect) { ; 보무
            AppendLog("[Master] 보호, 무장 사용")
            GoSub, RedTabSearch
            Send, 7
            Sleep, 70
            Send, 8
            Sleep, 70
            Protect := false
        }

        if(MasterNowMp <= MasterMp) {
            AppendLog("[Master] 마력 부족, 공력주입")
            GoSub, RedTabSearch
            Send, {Shift Down}
            Sleep, 70
            Send, z
            Sleep, 70
            Send, {Shift Up}
            Sleep, 70
            Send, t
        }

        if(MasterNowHp = 0) { ; 부활
            hpFull := false
            AppendLog("[Master] 체력 0, 부활 사용")
            GoSub, RedTabSearch
            Send, 9
            Sleep, 70
            Send, 7
            Sleep, 70
            Send, 8
        } else if ( MasterNowHp < MasterHp ) {
            hpFull := false
            ; AppendLog("[Master] 현재 체력(" . MasterNowHp . "), 기원사용(기준 : " . MasterHp . ")")
            GoSub, RedTabSearch
            Send, 3
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, 3
            Sleep, 70
            Send, 3
        } else {
            hpFull := true
        }

    }

return

Shout:
    IniRead, ShoutText, %target%, Stats, ShoutText
    if(Shout) {
        AppendLog("[Slave] 사자후 사용")
        Send, {Esc}
        Sleep, 100
        Send, {Shift Down}
        Sleep, 100
        Send, z
        Sleep, 100
        Send, {Shift Up}
        Sleep, 100
        Send, x
        Sleep, 100
        Send, %ShoutText%
        Sleep, 100
        Send, {Enter}
        Sleep, 100
        Shout := false
    }
return

Debuff:
    if (Debuff) {
        Send, {Esc}
        Sleep, 50
        Send, 4
        Sleep, 50
        Send, {Up}
        Sleep, 50
        Send, {Enter}
        Sleep, 50
        Send, 4
        Sleep, 50
        Send, {Up}
        Sleep, 50
        Send, {Enter}
        Sleep, 50
        Send, 4
        Sleep, 50
        Send, {Up}
        Sleep, 50
        Send, {Enter}
        Sleep, 50
    } 
return

Follow:
    if (Macro) { ;
        IniRead, master_x, %target%, MasterStatus, X_Coord
        IniRead, master_y, %target%, MasterStatus, Y_Coord
        IniRead, master_map, %target%, MasterStatus, Map

        if ( x_coord = "" || y_coord = "" ) {
            AppendLog("[Slave] 좌표 오류")
            return
        }

        lastIndex := xyData.MaxIndex()

        if (!lastIndex) { ; slave 좌표를 기록
            lastIndex := 1
            xyData[lastIndex] := [x_coord, y_coord]
            ; AppendLog("[Slave] 최초 좌표 기록(x:" . x_coord . ", y:" . y_coord . ")")
        } else {
            if (x_coord != xyData[lastIndex][1] || y_coord != xyData[lastIndex][2]) { ; 현재 좌표와 마지막으로 저장된 좌표의 값이 동일하지 않을때만 저장
                ; AppendLog("[Slave] 좌표 기록(x:" . x_coord . ", y:" . y_coord . ")")
                xyData[lastIndex + 1] := [x_coord, y_coord]
                if (xyData.MaxIndex() > 10) {
                    xyData.Delete(xyData.MinIndex())  ; 가장 오래된 값 삭제
                }
            }
        }

        slaveEventX := xyData[lastIndex][1] - x_coord
        slaveEventY := xyData[lastIndex][2] - y_coord
        if (Abs(slaveEventX) > 2 || Abs(slaveEventY) > 2) {
            AppendLog("[Slave] 멈춤")
            return
        }

        if ( map = master_map ) {
            NextMap := false
            xDifference := master_x - x_coord 
            yDifference := master_y - y_coord 
        } else {
            master_mapNum := StrReplace(master_map, "흉가", "") + 0
            mapNum := StrReplace(map, "흉가", "") + 0
            NextMap := true
            
            if ((master_mapNum - mapNum) > 0) {
                xDifference := Ghost[master_mapNum][1] - x_coord
                yDifference := Ghost[master_mapNum][2] - y_coord
            } else { ; 빽굴
                xDifference := Ghost[master_mapNum][3] - x_coord
                yDifference := Ghost[master_mapNum][4] - y_coord
            }
        }

        if (Abs(yDifference) > Abs(xDifference)) { ; y가 더 길면 x를 먼저 이동
            horizontal(xDifference, yDifference) 
            vertical(xDifference, yDifference)
        } else { ; x가 더 길면 y를 먼저 이동
            vertical(xDifference, yDifference)
            horizontal(xDifference, yDifference) 
        }

        ; 보정?
        if (Abs(master_x - x_coord) < 8 && Abs(master_y - y_coord) < 8 && !NextMap) {
                Goto, RedTabSearch
        }   
    }
Return

horizontal(xDifference, yDifference) {
    global NextMap
    if (Abs(xDifference) > 2 || NextMap ) { ; 조건을 무시하는 것이 필요요
        if (xDifference > 0) {
            Send, {Right}
        } else {
            Send, {Left}
        }
    } else if (Abs(yDifference) > 3 && Abs(xDifference) != 0) { ; 조건을 무시하는 것이 필요요
        if (xDifference > 0) {
            Send, {Right}
        } else {
            Send, {Left}
        }
    }
}

vertical(xDifference, yDifference) {
    global NextMap
    if (Abs(yDifference) > 2 || NextMap ) {
        if (yDifference > 0) {
            Send, {Down}
        } else {
            Send, {Up}
        }
    } else if (Abs(xDifference) > 3 && Abs(yDifference) != 0) {
        if (yDifference > 0) {
            Send, {Down}
        } else {
            Send, {Up}
        }
    }
}

TabTab:
    if (!RetryTab) {
        RetryTab := true
        Color1 := 0x539B7b ; 0x539B7b
        Color2 := 0x912F2B
        PixelSearch, FoundX, FoundY, SearchX1, SearchY1, SearchX2, SearchY2, Color1, Variation, Fast RGB
        ; PixelSearch, FoundX, FoundY, SearchX1, SearchY1, SearchX2, SearchY2, Color2, Variation, Fast RGB
        if !ErrorLevel
        {   
            SetTimer, Follow, Off ; 
            Send, {Esc}
            Sleep, 70
            Send, {Esc}
            Sleep, 70
            Send, {Tab}
            Sleep, 70
            Click, % (FoundX - 5) ", " (FoundY + 15)
            Sleep, 70
            Send, {Tab}
        } else {
            AppendLog("마스터를 못찾음")
        }
        SetTimer, Follow, 100 ; 
        RetryTab := false
    }
Return

RedTabSearch:
    if (NextMap) {
        return 
    }

    if (Debuff) {
        return
    }    
    ; 탐색할 빨간색의 색상값 (예: RGB FF5757)
    masterColor:=0x539B7b
    RedColor := 0xFF5757

    ; 탐색 영역 정의 (화면 전체를 탐지하려면 A_ScreenWidth와 A_ScreenHeight를 사용)
    SearchX1 := 0
    SearchY1 := 0
    SearchX2 := A_ScreenWidth
    SearchY2 := A_ScreenHeight

    ; 탐지 정밀도 설정 (0이 가장 정확, 255는 대략적인 탐색)
    Variation := 5
    
    ; FF5757 색상 픽셀을 검색
    PixelSearch, FoundX, FoundY, SearchX1, SearchY1, SearchX2, SearchY2, RedColor, Variation, Fast RGB

    ; 색상을 찾았으면
    if !ErrorLevel
    {
        SetTimer, Follow, 100 ;
    }
    else {
        PixelSearch, FoundX, FoundY, SearchX1, SearchY1, SearchX2, SearchY2, masterColor, Variation, Fast RGB
        if !ErrorLevel
        {
            SetTimer, Follow, Off ;
            Send, {Esc}
            Sleep, 70
            Send, {Tab}
            Sleep, 70
            Send, {Tab}
            Sleep, 70
        }
    }
return
           
searchsort(win,a,b,c,d,e,f=0.000001,g=0.000001, h=1, i=1)
{
    if(obj:=FindText(X,Y,a,b,c,d,f,g,e,0,,,,,,h,i))
    {
        obj:=FindText().sort(obj)
        for k,v in obj
            n.=obj[a_index].id "|"
    }
    return regexreplace(SubStr(n,1,strlen(n)-1),"\|")
}

; 로그 추가 함수 (최대 10줄 유지)
AppendLog(msg) {
    global LogMessages

    ; 현재 시간 HH:MM:SS 형식으로 구하기
    FormatTime, CurrentTime, %A_Now%, HH:mm:ss

    ; 로그에 시간 추가
    msg := "[" . CurrentTime . "] " . msg

    if (LogMessages.Length() >= 12) {
        LogMessages.RemoveAt(1)  ; 가장 오래된 로그 삭제
    }
    LogMessages.Push(msg)

    logText := ""
    for index, line in LogMessages {
        logText .= line . "`n"
    }

    GuiControl,, LogBox, % logText
}

; 창을 닫으면 프로그램 종료
GuiClose:
    ExitApp
return

ReloadScript:
    Reload  ; 스크립트 다시 실행
return

