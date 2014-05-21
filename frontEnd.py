from msaGlobal import GetMsa, SetMsa, SetModuleVersion
from util import message
import wx

SetModuleVersion("cavityFilter",("1.30","JGH","05/20/2014"))

#  !!!!!!!   STILL SKELETON CODED IN LB !!!!!!!!!!!!!!!!
#==============================================================================
# FRONT END MODULE
# Front end files are used in SA mode to adjust for attenuators, amplifiers
# or other front-end attachements

class FronEndAttach:
    def __init__():
        pass

    def frontEndLoadBtn(self): #   ver115-9d
        close #frontEnd
        goto [frontEndMenuLoad]

    def frontEndMenuLoad(self): #ver115-9d
        filter$="All files" + chr$(0) + "*.*" + chr$(0) + _
                    "Parameter files" + chr$(0) + "*.s1p" + chr$(0) + _
                    "Text files" + chr$(0) + "*.txt" + chr$(0) + _
                    "CSV files" + chr$(0) + "*.csv"
        defaultExt$="*"
        initialDir$=frontEndLastFolder$+"\"
        initialFile$=""
        dataFileName$=uOpenFileDialog$(filter$, defaultExt$, initialDir$, initialFile$, "Open Data File")
        if dataFileName$="" then wait   #user cancelled
        frontEndActiveFilePath$=dataFileName$
        call frontEndLoadFile
        call RequireRestart     #Must restart to activate front end adjustment
        wait

    def frontEndCancelBtn(self): #  ver115-9d
        close #frontEnd
        wait
    def frontEndUnloadBtn(self): #   'ver115-9d
        close #frontEnd
        frontEndActiveFilePath$=""  #Prevents front end adjustment from being applied; no need to clear it
        wait
    def menuLoadFrontEndFile(self): #  'ver115-9d
        if haltsweep=1 then gosub [FinishSweeping]
        if frontEndActiveFilePath$="" then
            gosub [frontEndMenuLoad]
        else    # Determine whether to load or delete
            WindowWidth = 250
            WindowHeight = 150
            call GetDialogPlacement
            BackgroundColor$="gray"
            ForegroundColor$="black"
            TextboxColor$ = "white"

            statictext #frontEnd.intro, "Do you want to load a front-end file, or just unload the existing file?",10, 10, 200, 35

                'Buttons
            button #frontEnd.Load, "Load", [frontEndLoadBtn], UL,20, 75, 60,30
            button #frontEnd.Delete, "Unload", [frontEndUnloadBtn], UL,100, 75, 60,30
            button #frontEnd.Cancel, "Cancel", [frontEndCancelBtn], UL,180, 75, 60,30
            open "Front End" for dialog_modal as #frontEnd
            #frontEnd, "trapclose [frontEndCancelBtn]"
            #frontEnd.intro, "!font ms_sans_serif 10"
        end if
        wait

    def frontEndLoadFile(self): #  'Load front-end file in frontEndActiveFilePath$ ver115-9d
        restoreFileHndl$=touchOpenInputFile$(frontEndActiveFilePath$)
        if restoreFileHndl$="" then restoreErr$="Front-end file failed to open: ";dataFileName$ : exit sub
        call uParsePath frontEndActiveFilePath$, frontEndLastFolder$, dum$ 'Save folder from which file was loaded
        restoreFileName$=frontEndActiveFilePath$
        call touchReadParams restoreFileHndl$,1  'Read data from file into uWorkArray
        close #restoreFileHndl$
        if touchBadLine>0 then notice "File Error in Line ";touchBadLine : cursor normal : exit sub   'touchReadParams sets touchBadLine if error
        if uWorkNumPoints<2 then notice "File must contain two or more points" : cursor normal : exit sub
        if uWorkNumPoints>=gMaxNumPoints() then redim frontEndCalData(uWorkNumPoints+10,1)  'make cal array as big as necessary
        'The data is now in uWorkArray(1,x) to uWorkArray(uWorkNumPoints, x)
        for i=1 to uWorkNumPoints  'move from work array to frontEndCalData
            frontEndCalData(i,0)=uWorkArray(i,0)/1000000    'freq (we store in MHz)
            frontEndCalData(i,1)=uWorkArray(i,1)
        next i
            'set work array to minimum size. touchReadParams may have made it large
        call uSetMaxWorkPoints 0,3 'ver116-1b
        frontEndCalNumPoints=uWorkNumPoints 'Number of valid points in frontEndCalData
    end sub

    def frontEndInterpolateToScan(self): #   'Interpolate from frontEndCalData to frontEndCorrection based on current scan points ver115-9d

        #We copy data to the interpolation arrays, interpolate, and copy the results where we want them
        call intSetMaxNumPoints max(frontEndCalNumSteps, globalSteps)+1  'Be sure we have room

        call intClearSrc : call intClearDest
        for i=1 to frontEndCalNumPoints 'copy cal table to intSrc
            call intAddSrcEntry frontEndCalData(i,0),frontEndCalData(i,1),0
        next i
        for i=1 to globalSteps+1
            call intAddDestFreq gGetPointXVal(i)   'Install frequencies in intDest
        next i

        favorFlat=1 : isAngle=0
        #1 means do mag; first 0 means don't do phase; final 0 means not phase correction ver116-1b
        call intCreateCubicCoeffTable 1,0,isAngle, favorFlat,0    'Get coefficients for cubic interp of front end cal 'ver116-1b

        #0 means data is not polar , 1 means do cubic interp, 1 means do mag only
        call intSrcToDest 0, 1, 1

        for i=0 to globalSteps  'put the data where we want it
            call intGetDest i+1,f, m, p
            frontEndCorrection(i)=m 'mag from interp results
        next i
    end sub

    
