# 2022 original firmware retrieval: X96 MAX+ 2101W

## Target

**Exact** original/factory Amlogic USB Burning Tool firmware: `X96max_plus_2101w_20220525-1404`; specific to **2101W**, not plain 2101, Q1, Q2 or 100W. Target is original **.img** or a losslessly compressed archive containing a complete Amlogic burning image. An OTA ZIP or slimBOXtv custom ROM does not satisfy the request.

## Provenance (verified titles and accounts, not downloaded files)

| Source | What it establishes | What it does not establish |
| --- | --- | --- |
| [4PDA official firmware directory](https://4pda.to/forum/index.php?showtopic=1013103&st=13700) | Index lists `X96max_plus_2101w_20220525-1404` under factory files | The actual file URL or current downloadability |
| [4PDA 2101W real reflash report](https://4pda.to/forum/index.php?showtopic=1013103&st=10320) | User reported flashing this exact stock build in USB Burning Tool | Successful reboot (that particular device remained stuck at logo) |
| [4PDA 2022 slimBOXtv discussion](https://4pda.to/forum/index.php?showtopic=1013103&st=9760) | A third-party slimBOXtv test build explicitly described as based on this 2022 stock | The original manufacturer ROM or an identical binary |
| [X96mini/OEM 4GB RAM firmware directory](https://drive.google.com/drive/folders/1VpgOB3npO98I_5s_ryKrMLpxE_4IbbOD?usp=drive_link) | Manufacturer-style X96 MAX+ 4GB public folder exists | The folder's individual files have not been enumerated or matched to **2101W** |
| [2024 2101W stock Recovery Release](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/firmware-2101w-stock-20240508-42466511950-1) | A newer full original-style package is safely archived | It is **not** the 2022 image and must not be renamed to that version |

The 4PDA forum page can be search-indexed, but the attachment's exact public URL could not be reliably recovered. **No matching 2022 ROM bytes were acquired or published.**

## Excluded identifications

- `X96MaxPlus_2101_20220525-1725`: the **2101** hardware revision (not 2101W).
- `sbx_x96max_plus_2101w_aosp_9_20.zip` and `sbx_x96max_plus_2101w_atv_9_20.zip`: **slimBOXtv third-party**. They have dedicated Third-party Releases, distinct from Stock.
- The 2022 slimBOXtv test published as a **derivative** of the 2022 stock. Derivation is not byte-for-byte equality.

## Evidence required to add the original 2022 stock to Release

1. Recover a direct, currently accessible URL or an owner-provided manufacturer package (with accurate source attribution).
2. Check filename and Amlogic UBT packaging; inspect decoded image header, content type and size. Do not accept just `20220525` in the name as identity proof.
3. Ensure it is not the `2101` firmware nor slimBOXtv rebrand. Compare original DTB variants and boot/recovery partition names, not just device family or RAM size.
4. Preserve original bytes, documentation and provider link in a distinct `firmware-2101w-stock-20220525-...` Release after all checks.
5. Any reflash still requires separate HIGH-risk device authorization and a verified backup/restore path.

The existing `stock_rom.yml` source catalog keeps 2022 entries as **unresolved**, and blocks automatic publication in the absence of a verified download.
