"""Alienware AW3225QF (Dell, 32" 4K QD-OLED, 2024): what is known about its VCP codes. A skeleton for review.

Only the codes marked `confirmed` were read on BevelTipDrip's monitor. Everything else is "from <source>, not
confirmed on this monitor": the capabilities listing of another person's AW3225QF (vdu_controls issue 84, March
2024, read with ddcutil), meanings seen on other Dell / Alienware models (mostly the AW3423DWF, the closest
Alienware QD-OLED), or the MCCS standard. Dell does not publish its manufacturer codes (Dell community forum,
"we cannot publish the Dell proprietary VCP codes"). Run T-DDC2 (plan-ddc-module.md) to fill in this monitor's
own capabilities string and replies; then update `in_caps`, `confirmed` and the notes here.

Out of scope, permanently: anything that modifies, reads out or bypasses the monitor's firmware.
"""
from . import ASK, NEVER, SAFE, Control, DisplayModule

SOURCES = {
    "nearblack-tint": "research/docs/plan-nearblack-tint.md (reads on BevelTipDrip's AW3225QF, 2026-11-18; OSD "
                      "facts from BevelTipDrip)",
    "measurement": "research/docs/measurement-reference.md",
    "vdu84": "https://github.com/digitaltrails/vdu_controls/issues/84 (another person's AW3225QF, ddcutil "
             "capabilities, 2024-03-31; checked by the drafting agent 2026-11-19)",
    "aw3423dwf-map": "https://github.com/ykoval/aw3423dwf-tray/blob/main/VCP_MAP.md (AW3423DWF, firmware M3B107; "
                     "checked by the drafting agent 2026-11-19)",
    "aw3423dwf-dump": "https://gist.github.com/nicck/d77235bc1276b1e068b6c3d758e75e94 (AW3423DWF, ControlMyMonitor "
                      "dump)",
    "u3421we": "https://raw.githubusercontent.com/ddccontrol/ddccontrol-db/master/db/monitor/DELA181.xml (Dell "
               "U3421WE, ddccontrol database)",
    "dell-preset": "https://www.dell.com/community/Monitors/DDM-Linux-standard-command-to-switch-Preset-Modes/"
                   "m-p/7846533 (Dell P-series users)",
    "dell-pbp": "https://gist.github.com/lainosantos/06d233f6c586305cde67489c2e4a764d (Dell U2723QE PbP / KVM)",
    "m1ddc-codes": "https://gist.github.com/nebriv/cb934a3b702346c5988f2aba5ee39f0d (Dell code list for m1ddc)",
    "dell-codes": "https://www.dell.com/community/Monitors/U3818DW-Please-publish-the-VCP-MCCS-codes/m-p/6188173 "
                  "(Dell: 'we cannot publish the Dell proprietary VCP codes')",
    "tt536": "https://github.com/xanderfrangos/twinkle-tray/issues/536 (AW3423DWF: constant polling hid the OSD)",
    "ddcutil-warn": "https://manpages.opensuse.org/Leap-16.0/ddcutil-service/ddcutil-service.1 (manufacturer "
                    "features 'may have irreversible consequences')",
    "mccs": "MCCS 2.2a, via ddc/mccs.py",
}

NC = "not confirmed on this monitor"
VDU = "from vdu84 (listed in that unit's capabilities), " + NC
DWF = "from aw3423dwf-map (AW3423DWF), " + NC

COLOUR_LOCK = ("every HDR preset except Custom Color HDR (BevelTipDrip, 2026-11-18: only Custom Color HDR offers "
               "colour controls, hue and saturation; whether the DDC gains act there is not known [I])")

_C = [
    # --- standard codes this model lists or answers ---------------------------------------------------------------
    Control(0x02, "new control value", ASK, "MCCS: set when a control changed at the OSD", VDU, in_caps=True),
    Control(0x04, "restore factory defaults", NEVER, "factory reset (core never list)", VDU, in_caps=True),
    Control(0x05, "restore factory brightness/contrast", NEVER, "factory reset (core never list)", VDU,
            in_caps=True),
    Control(0x08, "restore factory colour", NEVER, "factory reset (core never list)", VDU, in_caps=True),
    Control(0x10, "brightness", SAFE, "0-100; stored per preset, so it jumps when the preset changes (AW3423DWF)",
            VDU + "; per-preset storage " + DWF, in_caps=True),
    Control(0x12, "contrast", SAFE, "0-100; stored per preset (AW3423DWF)", VDU, in_caps=True),
    Control(0x14, "colour preset", ASK, "colour temperature preset; changes with the OSD preset (AW3423DWF)", VDU,
            values={0x01: "sRGB", 0x05: "6500 K", 0x08: "9300 K", 0x0B: "user 1", 0x0C: "user 2"}, in_caps=True),
    Control(0x16, "red gain", SAFE, "per-channel gain, 0-100", "nearblack-tint",
            confirmed="read 100 of 100 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK, in_caps=True),
    Control(0x18, "green gain", SAFE, "per-channel gain, 0-100", "nearblack-tint",
            confirmed="read 100 of 100 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK, in_caps=True),
    Control(0x1A, "blue gain", SAFE, "per-channel gain, 0-100", "nearblack-tint",
            confirmed="read 100 of 100 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK, in_caps=True),
    Control(0x52, "active control", ASK, "MCCS: the code last changed at the OSD (read only in practice)", VDU,
            in_caps=True),
    Control(0x60, "input source", NEVER, "input select (core never list); reads 0x0F0F for DP: use the low byte",
            VDU, values={0x0F: "DisplayPort 1", 0x11: "HDMI 1", 0x12: "HDMI 2"}, in_caps=True),
    Control(0x6C, "red black level", SAFE, "per-channel black level, 0-255", "nearblack-tint",
            confirmed="read 50 of 255 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK + "; effect not measured",
            in_caps=False),
    Control(0x6E, "green black level", SAFE, "per-channel black level, 0-255", "nearblack-tint",
            confirmed="read 50 of 255 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK + "; effect not measured",
            in_caps=False),
    Control(0x70, "blue black level", SAFE, "per-channel black level, 0-255", "nearblack-tint",
            confirmed="read 50 of 255 on 2026-11-18 (probe)", locked_by=COLOUR_LOCK + "; effect not measured",
            in_caps=False),
    Control(0x87, "sharpness", ASK, "MCCS sharpness", VDU, in_caps=True),
    Control(0xAC, "horizontal frequency", ASK, "read only (MCCS)", VDU, in_caps=True),
    Control(0xAE, "vertical frequency", ASK, "read only (MCCS)", VDU, in_caps=True),
    Control(0xB2, "flat panel sub-pixel layout", ASK, "read only (MCCS)", VDU, in_caps=True),
    Control(0xB6, "display technology type", ASK, "read only (MCCS)", VDU, in_caps=True),
    Control(0xC6, "application enable key", ASK, "MCCS application key; meaning on Dell unknown", VDU,
            in_caps=True),
    Control(0xC8, "display controller type", NEVER, "identification, read only; the AW3423DWF reports it writable "
            "(aw3423dwf-dump), nothing here should write it", VDU, in_caps=True),
    Control(0xC9, "display firmware level", NEVER, "firmware version, read only; firmware is out of scope", VDU,
            in_caps=True),
    Control(0xCA, "OSD / button control", NEVER, "OSD lock (core never list)", VDU, in_caps=True),
    Control(0xCC, "OSD language", ASK, "OSD language; values 02 03 04 06 09 0A 0D 0E listed", VDU, in_caps=True),
    Control(0xD6, "power mode", NEVER, "power (core never list)", VDU,
            values={0x01: "on", 0x04: "off (soft)", 0x05: "off (MCCS: power off)"}, in_caps=True),
    Control(0xDC, "display mode", ASK, "on the AW3423DWF 5 = Game 1, every other preset 0", VDU + "; " + DWF,
            in_caps=True),
    Control(0xDF, "VCP version", ASK, "read only; 2.1 on that unit", VDU, in_caps=True),
    # --- manufacturer codes (E0-FF): listed by that unit; meanings from other models ---------------------------
    Control(0xE0, "manufacturer E0", ASK, "unknown; reads 0 or 1 on the AW3423DWF", VDU, in_caps=True),
    Control(0xE1, "Dell power (inverted)", NEVER, "on Dell U/P models: power, 0 = on, 1 = off/standby (inverted "
            "against MCCS D6)", "from u3421we (Dell U3421WE), " + NC + "; listed by vdu84", in_caps=True),
    Control(0xE2, "preset mode (report)", ASK, "reports the OSD preset; writes are accepted and ignored on the "
            "AW3423DWF. A read could tell a tool which preset is active (e.g. the probe's label check)",
            DWF + "; listed by vdu84",
            values={0: "Standard", 4: "Game 1", 11: "Creator sRGB", 14: "Warm", 18: "Cool", 20: "Custom Color",
                    27: "Creator DCI-P3", 35: "Movie HDR", 36: "Game HDR", 39: "Desktop (HDR)", 58: "DisplayHDR",
                    255: "Custom Color HDR"},
            in_caps=True),
    Control(0xE3, "manufacturer E3", ASK, "unknown", VDU, in_caps=True),
    Control(0xE4, "manufacturer E4", ASK, "unknown", VDU, in_caps=True),
    Control(0xE5, "manufacturer E5", ASK, "on some Dell models: swap PiP/PbP inputs", "from m1ddc-codes (low "
            "confidence, model not stated), " + NC + "; listed by vdu84", in_caps=True),
    Control(0xE8, "PiP/PbP secondary input", ASK, "on Dell U/S models: the second input of PiP/PbP",
            "from dell-pbp (low confidence), " + NC + "; listed by vdu84", in_caps=True),
    Control(0xE9, "PiP/PbP mode", ASK, "on Dell U models: PiP/PbP mode; on the U3421WE some modes change the EDID, "
            "which may make Windows re-detect the display and drop its colour profile (Q-11)",
            "from u3421we and dell-pbp, " + NC + "; listed by vdu84",
            values={0x00: "off", 0x21: "PiP small", 0x22: "PiP large", 0x24: "PbP"}, in_caps=True),
    Control(0xEA, "manufacturer EA", ASK, "unknown", VDU, in_caps=True),
    Control(0xEC, "manufacturer EC", ASK, "unknown; values 01 02 04 06 listed; AW3423DWF reads 3840 of 3846",
            VDU, in_caps=True),
    Control(0xF0, "preset select (part)", ASK, "with E2 and 14, selects OSD presets on the AW3423DWF (HDR: Desktop "
            "52, Movie HDR 49, Game HDR 50, Custom Color HDR 10, DisplayHDR 54). AW3225QF values listed: 00 05 06 "
            "0A 0D 0E 0F 10 11 13 31 32 34 36; their meaning here is not known", DWF + "; listed by vdu84",
            in_caps=True),
    Control(0xF1, "manufacturer F1", ASK, "unknown", VDU, in_caps=True),
    Control(0xF2, "HDR state (report)", ASK, "reads 65 while HDR is on, 0 while off (AW3423DWF)",
            DWF + "; listed by vdu84", in_caps=True),
    Control(0xF4, "indirect register (gaming settings)", ASK, "a command register, not a value: on the AW3423DWF "
            "Dark Stabilizer is set by writing 48+N and read by writing 63 and then reading 48+N; 65535 = no "
            "answer yet. Reading Dark Stabilizer therefore needs a write, so `scan` cannot report it. AW3225QF "
            "values listed: 10-17 30-33 40-46 A1-A3", DWF + "; listed by vdu84", in_caps=True),
    Control(0xF5, "manufacturer F5", ASK, "unknown; value 1D listed", VDU, in_caps=True),
    Control(0xFD, "manufacturer FD", ASK, "unknown; AW3423DWF reads 98", VDU, in_caps=True),
    Control(0xFE, "manufacturer FE", ASK, "unknown", VDU, in_caps=True),
]

PRESETS = {
    "True Black 400": "HDR preset used for calibration (BevelTipDrip, 2026-11-18); colour controls locked "
                      "(nearblack-tint)",
    "Peak 1000": "HDR; dropped for now (BevelTipDrip, 2026-11-18). On the AW3423DWF the Peak 1000 toggle changed "
                 "no polled code (aw3423dwf-map)",
    "Desktop": "HDR; the preset the monitor fell back to after losing power (plan-nearblack-tint.md, T-NT0)",
    "Custom Color HDR": "the only HDR preset with colour controls: hue and saturation in the OSD, peak about 450 "
                        "nits (BevelTipDrip, 2026-11-18). Not reachable over DDC/CI on the AW3423DWF "
                        "(aw3423dwf-map README), " + NC,
    "Creator (SDR)": "gamma 2.2 option, planned for the SDR run (Q-7)",
}

NOTES = [
    "6C / 6E / 70 (black level) answered on BevelTipDrip's monitor (50 of 255, 2026-11-18) but are not in the "
    "capabilities listing of the unit in vdu84: if T-DDC2 shows the same on this unit, they are the first hidden "
    "settings found [I].",
    "62 (audio volume) and E7 (Dell USB/KVM) are not listed by the unit in vdu84.",
    "No public source ties any VCP code to firmware update, a service menu or a factory mode on Dell or Alienware "
    "monitors. Dell says its factory service menu is for the manufacturer only (Dell community forum); it is not "
    "a DDC/CI matter and is out of scope here.",
    "No public VCP code starts the OLED panel refresh (pixel refresh); Dell documents it only in the OSD.",
    "Constant DDC/CI polling made the OSD disappear on an AW3423DWF (tt536): do not poll in a loop.",
    "Unknown manufacturer codes are 'ask first', not 'safe': ddcutil warns that manufacturer features may have "
    "irreversible consequences (ddcutil-warn).",
]

MODULE = DisplayModule(key="aw3225qf", model="AW3225QF", match=["aw3225qf"], controls={c.code: c for c in _C},
                       presets=PRESETS, notes=NOTES, sources=SOURCES)
