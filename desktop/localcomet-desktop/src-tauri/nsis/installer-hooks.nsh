!macro NSIS_HOOK_PREINSTALL
  ; Keep installer-owned binaries separate from %LOCALAPPDATA%\LocalComet user data.
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${PRODUCTNAME}"
  ; The stock template selects its output path before this supported hook runs.
  SetOutPath $INSTDIR
!macroend
