!macro NSIS_HOOK_PREINSTALL
  ; Keep installer-owned binaries separate from %LOCALAPPDATA%\LocalComet user data.
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${PRODUCTNAME}"
!macroend
