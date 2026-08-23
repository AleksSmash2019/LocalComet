from enum import IntFlag

import comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 as __wrapper_module__
from comtypes.gen._00020430_0000_0000_C000_000000000046_0_2_0 import (
    FONTBOLD, GUID, OLE_HANDLE, Font, Library, OLE_YSIZE_CONTAINER,
    OLE_XSIZE_HIMETRIC, Default, dispid, BSTR, FONTUNDERSCORE,
    OLE_YSIZE_PIXELS, FONTSTRIKETHROUGH, typelib_path, _check_version,
    StdFont, OLE_XSIZE_CONTAINER, OLE_OPTEXCLUSIVE, _lcid,
    OLE_YPOS_HIMETRIC, OLE_XPOS_CONTAINER, CoClass,
    OLE_YPOS_CONTAINER, DISPMETHOD, OLE_YPOS_PIXELS,
    OLE_XPOS_HIMETRIC, DISPPROPERTY, OLE_XSIZE_PIXELS, DISPPARAMS,
    OLE_CANCELBOOL, Monochrome, Color, OLE_COLOR,
    OLE_ENABLEDEFAULTBOOL, HRESULT, FontEvents, FONTITALIC,
    IFontEventsDisp, Gray, IFont, IFontDisp, FONTNAME, IPictureDisp,
    FONTSIZE, EXCEPINFO, IPicture, IUnknown, VARIANT_BOOL,
    OLE_YSIZE_HIMETRIC, IDispatch, Picture, VgaColor, StdPicture,
    OLE_XPOS_PIXELS, Checked, COMMETHOD, Unchecked, IEnumVARIANT
)


class LoadPictureConstants(IntFlag):
    Default = 0
    Monochrome = 1
    VgaColor = 2
    Color = 4


class OLE_TRISTATE(IntFlag):
    Unchecked = 0
    Checked = 1
    Gray = 2


__all__ = [
    'Color', 'FONTBOLD', 'OLE_COLOR', 'OLE_HANDLE',
    'OLE_ENABLEDEFAULTBOOL', 'Font', 'Library', 'FontEvents',
    'OLE_YSIZE_CONTAINER', 'FONTITALIC', 'OLE_XSIZE_HIMETRIC',
    'IFontEventsDisp', 'Gray', 'Default', 'IFont', 'OLE_TRISTATE',
    'IFontDisp', 'FONTNAME', 'IPictureDisp', 'FONTUNDERSCORE',
    'OLE_YSIZE_PIXELS', 'FONTSTRIKETHROUGH', 'typelib_path',
    'FONTSIZE', 'IPicture', 'StdFont', 'OLE_XSIZE_CONTAINER',
    'OLE_OPTEXCLUSIVE', 'OLE_YSIZE_HIMETRIC', 'Picture', 'VgaColor',
    'OLE_YPOS_HIMETRIC', 'OLE_XPOS_CONTAINER', 'StdPicture',
    'OLE_YPOS_CONTAINER', 'OLE_YPOS_PIXELS', 'OLE_XPOS_HIMETRIC',
    'OLE_XPOS_PIXELS', 'LoadPictureConstants', 'OLE_XSIZE_PIXELS',
    'Checked', 'OLE_CANCELBOOL', 'Monochrome', 'Unchecked'
]

