# TWRP for X96 MAX+ 2101W

Device: X96 MAX+ **2101W**, Amlogic **S905X3 / SM1**, RAM **4 GB**, eMMC **64 GB**. The exact PCB, Wi-Fi module and eMMC revision must still be identified from the physical device.

## Factory firmware archive

This repository initially focuses on collecting factory **Amlogic USB Burning Tool** images. **A ZIP or 7z file is not considered a valid burning ROM until its contents are inspected and an Amlogic firmware-package image is identified.**

| Entry | Device | Classification | Source | Archive status |
| --- | --- | --- | --- | --- |
| X96Max_Plus_2101W_20240508-1103.7z | 2101W | Factory/Stock candidate | [slimBOXtv official-firmware section](https://slimboxtv.ru/x96max-plus/) / [Yandex](https://disk.yandex.ru/d/EiPGAs73ml2wLQ) | Source identified; download and unpack unverified |
| X96max_plus_2101w_20220525-1404 | 2101W | Factory/Stock candidate | [4PDA firmware index](https://4pda.to/forum/index.php?showtopic=1013103&st=13260) | Exact public download link unverified |
| X96MaxPlus_2101_20220525-1725 | **2101, not 2101W** | Other-revision factory image | [4PDA](https://4pda.to/forum/index.php?showtopic=1013103&st=10120) | Excluded from 2101W Stock publication |
| sbx_x96max_plus_2101w_{aosp,atv}_9_20.zip | 2101W | **Third-party slimBOXtv**, not factory stock | [Armbian issue #929](https://github.com/ophub/amlogic-s9xxx-armbian/issues/929) / [Yandex](https://disk.yandex.ru/d/hGbDgwMQjO8BDQ) | Separate optional category; not marked Stock |

Use [`.github/workflows/stock_rom.yml`](.github/workflows/stock_rom.yml) to inspect and archive available sources. The workflow checks the actual package format before creating a Release, stores the untouched source archive and its extracted flashable image, and splits assets that exceed GitHub's per-file limit. It does **not** flash any device, prove board compatibility, or replace a complete device-specific eMMC backup.

The default push job archives **only the known-source 2024 2101W factory candidate**. Other sources can be investigated from the workflow dispatch menu; entries with no verified direct download source fail closed.

**Upstream attribution and redistribution condition:** [slimBOXtv X96Max Plus source post](https://slimboxtv.ru/x96max-plus/) requires permission or a link to its source post for third-party redistribution. Preserve this link in any mirror and obey applicable upstream rights. Firmware copyright and permission from the original hardware vendor are not established by this repository.

This is a firmware-research/archive project. TWRP itself is not yet implemented or validated.
