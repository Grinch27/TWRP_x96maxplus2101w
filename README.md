# TWRP for X96 MAX+ 2101W

Device: X96 MAX+ **2101W**, Amlogic **S905X3 / SM1**, RAM **4 GB**, eMMC **64 GB**. The exact PCB, Wi-Fi module and eMMC revision must still be identified from the physical device.

## Factory firmware archive

This repository initially focuses on collecting factory **Amlogic USB Burning Tool** images. **A ZIP or 7z file is not considered a valid burning ROM until its contents are inspected and an Amlogic firmware-package image is identified.**

| Entry | Device | Classification | Source | Archive status |
| --- | --- | --- | --- | --- |
| X96Max_Plus_2101W_20240508-1103.7z | 2101W | Factory/Stock candidate | [slimBOXtv official-firmware section](https://slimboxtv.ru/x96max-plus/) / [Yandex](https://disk.yandex.ru/d/EiPGAs73ml2wLQ) | [Released and statically validated (2024 original + UBT .img)](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/firmware-2101w-stock-20240508-42466511950-1) |
| X96max_plus_2101w_20220525-1404 | 2101W | Factory/Stock candidate | [4PDA firmware index](https://4pda.to/forum/index.php?showtopic=1013103&st=13260) | Exact public download link unverified |
| X96MaxPlus_2101_20220525-1725 | **2101, not 2101W** | Other-revision factory image | [4PDA](https://4pda.to/forum/index.php?showtopic=1013103&st=10120) | Excluded from 2101W Stock publication |
| sbx_x96max_plus_2101w_{aosp,atv}_9_20.zip | 2101W | **Third-party slimBOXtv**, not factory stock | [Armbian issue #929](https://github.com/ophub/amlogic-s9xxx-armbian/issues/929) / [Yandex](https://disk.yandex.ru/d/hGbDgwMQjO8BDQ) | [AOSP third-party prerelease](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/thirdparty-slimbox-2101w-slimbox-aosp-42470158359-1) / [ATV third-party prerelease](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/thirdparty-slimbox-2101w-slimbox-atv-42470158359-1) |

Use [`.github/workflows/stock_rom.yml`](.github/workflows/stock_rom.yml) to inspect and archive available sources. The workflow checks the actual package format before creating a Release, stores the untouched source archive and its extracted flashable image, and splits assets that exceed GitHub's per-file limit. It does **not** flash any device, prove board compatibility, or replace a complete device-specific eMMC backup.

For repeat Stock archives, use explicit `workflow_dispatch`; push runs only offline validation. [`thirdparty_rom.yml`](.github/workflows/thirdparty_rom.yml) publishes third-party AOSP/ATV as separately tagged prereleases, never Stock. Entries with no verified URL fail closed.

**Upstream attribution and redistribution condition:** [slimBOXtv X96Max Plus source post](https://slimboxtv.ru/x96max-plus/) requires permission or a link to its source post for third-party redistribution. Preserve this link in any mirror and obey applicable upstream rights. Firmware copyright and permission from the original hardware vendor are not established by this repository.

This repository now contains an **initial TWRP 9.0 Omni recovery device-tree port**, with original Stock 2024 kernel/second/DTBO preparation, independent `BoardConfig.mk`, Android product definitions, stock-derived Recovery fstab and automated source tests. The image has **not been compiled or boot-tested**. See [TWRP porting evidence and gates](docs/TWRP_PORTING.md).

## Verified Release

- **2024 2101W factory candidate:** [firmware-2101w-stock-20240508-42466511950-1](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/firmware-2101w-stock-20240508-42466511950-1), archived by [successful Actions run #42466511950](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42466511950).
- Contents: original `X96Max_Plus_2101W_20240508-1103.7z` (816,338,224 bytes), extracted `amlogic-factory-package.img` (1,689,100,628 bytes), `original-rom-manifest.json`.
- **Validation limit:** archive integrity and Amlogic package static header passed; actual USB Burning Tool import, device boot and 2101W board compatibility were not tested.
- **2022 2101W:** download URL remains unresolved, and no Release is available. Never confuse this with 2101 firmware or SlimBOXtv custom images.

## TWRP offline port status

- **Board / TWRP identity:** `x96maxplus2101w`, SoC `S905X3 / SM1`, original multi-DTB candidate `sm1_ac213_4g`. The S905X2 `u212` config is not reused.
- **Stock Recovery evidence:** Boot Header v1, 2048-byte pages, 32-bit ARM `init`/`adbd`/`recovery`, byte-matched 438-byte Recovery DTBO, and original compressed Multi-DTB; `remotecfg` is AArch64 (64-bit) and still requires dependency work.
- [Device-tree offline verification workflow](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/workflows/device_tree_verify.yml) and [original ROM extraction workflow](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/workflows/inspect_stock.yml).
- [Validated stock-derived TWRP prebuilts (7-day Artifact)](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42471929004/artifacts/13614290005); production builds should regenerate the inputs from the pinned original ROM.
- **Remaining gates:** real Recovery partition capacity, Amlogic init/USB/remote control dependencies, Android build selection, system-as-root mapping, userdata encryption, first successful TWRP build and eventual independently approved device tests.

## 2101W flashing and recovery research

See [**2101W flashing research and approval gates**](docs/FLASHING_RESEARCH_2101W.md). It distinguishes the complete Amlogic USB Burning Tool factory package from a single-partition TWRP `recovery.img` and cites a **firsthand 2101W USB 3.0/AV-reset** report.

**No TWRP device flashing is authorized.** The current Native Android 9 workflow is non-publishing and uploads a short-lived candidate only after a genuine build and bytewise stock component validation. Other variants' `u212`, `Plus2`, `2101` or `Q1` TWRP files are not considered compatible with the 2101W.
