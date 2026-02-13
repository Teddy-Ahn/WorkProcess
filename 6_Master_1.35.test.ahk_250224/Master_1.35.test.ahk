#Include D:\share\lib\ft.ahk
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

size_w := 16 + (854*mult)
size_h := 39 + (480*mult)
xy_sx := 640 * mult, xy_sy := 456 * mult, xy_dx := xy_sx + 88 * mult, xy_dy := xy_sy + 12 * mult
hp_sx := 650 * mult, hp_sy := 403 * mult, hp_dx := hp_sx + 82 * mult, hp_dy := hp_sy + 12 * mult
mp_sx := 650 * mult, mp_sy := 416 * mult, mp_dx := mp_sx + 82 * mult, mp_dy := mp_sy + 12 * mult

; status1_sx := 540 * mult, status1_sy := 187 * mult, status1_dx := status1_sx + 150 * mult, status1_dy := status1_sy + 13 * mult ; 빈화면 확인
; status1_sx := 560 * mult, status1_sy := 200 * mult, status1_dx := status1_sx + 150 * mult, status1_dy := status1_sy + 13 * mult ;62-12
; status2_sx := 560 * mult, status2_sy := 213 * mult, status2_dx := status2_sx + 150 * mult, status2_dy := status2_sy + 13 * mult
; status3_sx := 560 * mult, status3_sy := 226 * mult, status3_dx := status3_sx + 150 * mult, status3_dy := status3_sy + 13 * mult
; status4_sx := 560 * mult, status4_sy := 239 * mult, status4_dx := status4_sx + 150 * mult, status4_dy := status4_sy + 13 * mult
; status5_sx := 560 * mult, status5_sy := 252 * mult, status5_dx := status5_sx + 150 * mult, status5_dy := status5_sy + 13 * mult

; MaxHP_sx := 640 * mult,     MaxHP_sy := 152 * mult,     MaxHP_dx := MaxHP_sx + 67 * mult,    MaxHP_dy := MaxHP_sy + 13 * mult
; MaxMP_sx := 640 * mult,     MaxMP_sy := 172 * mult,     MaxMP_dx := MaxMP_sx + 67 * mult,     MaxMP_dy := MaxMP_sy + 13 * mult

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

MapText.="|<입구>**50$18.zDzXC1RDxR8BXDxzM0jzjUMcjscUMcU"
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

global StatusMessages := [] ; 상태창 배열

global win := "MapleStory Worlds"
global iniPath := "D:\share\env\Master.ini" 
global slavePath := "D:\share\env\Slave.ini" 
; global iniPath := "C:\Users\cpst\Documents\AutoHotkey\Env\Master.ini" ; 테스트용
; global slavePath := "C:\Users\cpst\Documents\AutoHotkey\Env\Slave.ini"
global LogMessages := [] ; 로그 배열
global Master := false ; 실행 상태
global xy, hp, mp, x_coord, y_coord  ;  상태값 전역 변수 선언

; 🎨 GUI 생성
Gui, +AlwaysOnTop
Gui, Show, w310 h400, Master 상태
Gui, Font, s11, Arial
Gui, Add, Text, x10 y10 w260 h30 vMaster, [상태]: Off 🔴
Gui, Font, s10, Arial
; Gui, Add, Text, x10 y40 w350 h20 vHpStatus, 체력: -
; Gui, Add, Text, x10 y60 w350 h20 vMpStatus, 마력: -
; Gui, Add, Text, x10 y80 w350 h20 vXYStatus, 좌표: X - ?, Y - ?
; Gui, Add, Text, x10 y100 w350 h20 vTimeStatus, 실행 시간: -
Gui, Add, Text, x10 y60 w260 h30, Master 체력:
Gui, Add, Edit, x90 y60 w80 h20 vMasterHp
Gui, Add, Text, x10 y90 w260 h30, Master 마력:
Gui, Add, Edit, x90 y90 w80 h20 vMasterMp
Gui, Add, Text, x10 y120 w260 h30, Slave 체력:
Gui, Add, Edit, x90 y120 w80 h20 vSlaveHp
Gui, Add, Text, x10 y150 w260 h30, Slave 마력:
Gui, Add, Edit, x90 y150 w80 h20 vSlaveMp
Gui, Add, Text, x10  y180 w50 h30, 사자후:
Gui, Add, Edit, x90 y180 w200 h20 vShoutText
Gui, Font, s8, Arial
Gui, Add, Edit, x10 y210 w290 h180 vLogBox -VScroll -ReadOnly ; 로그 창 (크기 증가)

Gui, Font, s8, Arial 
Gui, Add, Button, x140 y10 w50 h25 gApplyStats, Save
Gui, Add, Button, x195 y10 w50 h25 gLoadStats, Upload
Gui, Add, Button, x250 y10 w50 h25 gReloadScript, Reload

return

ApplyStats:
    GuiControlGet, MasterHp, , MasterHp
    GuiControlGet, MasterMp, , MasterMp
    GuiControlGet, SlaveHp, , SlaveHp
    GuiControlGet, SlaveMp, , SlaveMp
    GuiControlGet, ShoutText, , ShoutText

    IniWrite, %MasterHp%, %iniPath%, Stats, MasterHP
    IniWrite, %MasterMp%, %iniPath%, Stats, MasterMP
    IniWrite, %SlaveHp%, %iniPath%, Stats, SlaveHP
    IniWrite, %SlaveMp%, %iniPath%, Stats, SlaveMP
    IniWrite, %ShoutText%, %iniPath%, Stats, ShoutText
return

LoadStats:
    IniRead, MasterHP, %iniPath%, Stats, MasterHP
    IniRead, MasterMP, %iniPath%, Stats, MasterMP
    IniRead, SlaveHP, %iniPath%, Stats, SlaveHP
    IniRead, SlaveMP, %iniPath%, Stats, SlaveMP
    IniRead, ShoutText, %iniPath%, Stats, ShoutText

    GuiControl,, MasterHp, %MasterHP%
    GuiControl,, MasterMp, %MasterMP%
    GuiControl,, SlaveHp, %SlaveHP%
    GuiControl,, SlaveMp, %SlaveMP%
    GuiControl,, ShoutText, %ShoutText%
return 

ReloadScript:
    Reload  ; 스크립트 다시 실행
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
    
    Master := !Master  ; 상태 토글 (true ↔ false)

    if (Master) {
        SetTimer, Master, 500
        KeyToPress("F1")
    } else {
        SetTimer, Master, Off
        KeyToPress("F1")
    }

    GuiControl,, Master, % (Master ? "[상태]: On 🟢" : "[상태]: Off 🔴")
return

; Slave 명령 모드
+Up::KeyToPress("Up")
+Down::KeyToPress("Down")
+Left::KeyToPress("Left")
+Right::KeyToPress("Right")
F2::KeyToPress("F2")
F3::KeyToPress("F3")
F4::KeyToPress("F4")
F7::KeyToPress("F7")
F8::KeyToPress("F8")
+F4::
    Reload
return
+Tab::
    KeyToPress("Tab")
return

KeyToPress(Press) {
    global iniPath

    if !WinActive("ahk_exe msw.exe") {
        return
    }

    if (Press = "Up") {
        AppendLog("[Up 명령]")
    } else if (Press = "Down") {
        AppendLog("[Down 명령]")
    } else if (Press = "Left") {
        AppendLog("[Left 명령]")
    } else if (Press = "Right") {
        AppendLog("[Right 명령]")
    } else if (Press = "F1") {
        AppendLog("[F1 명령] Master, Slave Ready")
    } else if (Press = "F2") {
        AppendLog("[F2 명령] 매크로 명령")
    } else if (Press = "F3") {
        AppendLog("[F3 명령] 혼마술 명령")
    } else if (Press = "F4") {
        AppendLog("[F4 명령] 사자후 명령")
    } else if (Press = "Tab") {
        AppendLog("[Tab 명령] TabTab을 다시 합니다.")
    } else if (Press = "F8") {
        AppendLog("[F8 명령] 보무")
    } else if (Press = "F7") {
        AppendLog("[F7 명령] 금강 On/Off")
    }

    IniWrite, %Press%, %iniPath%, Commands, KeyToPress
}

Master:
    if (Master) {
        FindText().BindWindow(WinExist(win),4)  ;비활성 입력    
        start_time := A_TickCount   ;시간 쳌
        WinGetPos, pX, pY, pW, pH, %win%
        FindText().ScreenShot()
        map := searchsort(win,map_sx + pX, map_sy + pY, map_dx + pX, map_dy + pY,MapText,,,mult,mult) ;맵이름
        xy := searchsort(win,xy_sx + pX, xy_sy + pY, xy_dx + pX, xy_dy + pY,Text,,,mult,mult) ;좌표 x := SubStr(xy, 1, 4) , y := SubStr(xy, 5, 4)
        hp := searchsort(win,hp_sx + pX, hp_sy + pY, hp_dx + pX, hp_dy + pY, Text,,0.7,mult,mult) ;체력
        mp := searchsort(win,mp_sx + pX, mp_sy + pY, mp_dx + pX, mp_dy + pY, Text,,0.7,mult,mult) ;마력
        ; status1 := searchsort(win,status1_sx + pX, status1_sy + pY, status1_dx + pX, status1_dy + pY, statusData,,0.7,mult,mult) ;
        ; status2 := searchsort(win,status2_sx + pX, status2_sy + pY, status2_dx + pX, status2_dy + pY, statusData,,0.7,mult,mult) ;
        ; status3 := searchsort(win,status3_sx + pX, status3_sy + pY, status3_dx + pX, status3_dy + pY, statusData,,0.7,mult,mult) ;
        ; status4 := searchsort(win,status4_sx + pX, status4_sy + pY, status4_dx + pX, status4_dy + pY, statusData,,0.7,mult,mult) ;
        ; status5 := searchsort(win,status5_sx + pX, status5_sy + pY, status5_dx + pX, status5_dy + pY, statusData,,0.7,mult,mult) ;
        x_coord := SubStr(xy, 1, 4) + 0
        y_coord := SubStr(xy, 5, 4) + 0

        
        ; 🔹 .ini 파일에 값 저장
        IniWrite, %hp%, %iniPath%, MasterStatus, HP
        IniWrite, %mp%, %iniPath%, MasterStatus, MP
        IniWrite, %x_coord%, %iniPath%, MasterStatus, X_Coord
        IniWrite, %y_coord%, %iniPath%, MasterStatus, Y_Coord
        IniWrite, %map%, %iniPath%, MasterStatus, Map

        ; GUI 업데이트
        GuiControl,, HpStatus, 체력: %hp%
        GuiControl,, MpStatus, 마력: %mp%
        GuiControl,, XYStatus, 좌표: X - %x_coord%, Y - %y_coord%
        
        last_Time := A_TickCount - start_time
        IniWrite, %last_Time%, %iniPath%, MasterStatus, ResponseTime
        GuiControl,, TimeStatus, 실행 시간: %last_Time% ms

        FindText().BindWindow(0)
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
