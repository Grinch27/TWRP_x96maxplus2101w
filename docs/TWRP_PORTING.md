# X96 MAX+ 2101W: offline TWRP device-tree port

## Objective and boundary

Target: **X96 MAX+ 2101W, Amlogic S905X3 (SM1), 4GB RAM, 64GB eMMC**. The Android product/build identifier is `x96maxplus2101w`, independent of original Amlogic bootloader naming. Firmware and proprietary inputs are not committed. No flash, bootloader edits or AVB bypass is authorized.

This is a **candidate TWRP 9.0 device tree**, not a tested Recovery image. The `TeamWin/android_device_amlogic_u212` reference targets **S905X2/G12A** and must **not** be used as a binary/configuration drop-in.

## Evidence verified by real GitHub Actions

- 2024 original firmware source: [Stock Release](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/firmware-2101w-stock-20240508-42466511950-1).
- [Real offline analysis run #42471323150](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42471323150), from the above package: 28 items, 10,037,248-byte boot, 16,728,064-byte recovery, 438-byte DTBO, 4096-byte vbmeta, 85,773-byte compressed Multi-DTB, sparse system/vendor/odm/product.
- Both boot/recovery are Android Boot Header **v1**, **2048-byte** page size; load addresses kernel `0x01080000`, ramdisk `0x01000000`, second `0x00f00000`, tags `0x100`. Kernel payload: **9,947,616 bytes**. Recovery ramdisk: **6,687,486 bytes**, gzip/newc, 168 entries and `etc/recovery.fstab`; boot ramdisk is empty.
- Amlogic v2 compressed Multi-DTB includes `g12a_u212_2g`, `g12a_u212_4g`, `sm1_ac213_2g` and **`sm1_ac213_4g`**. These are parsed with 32-bit word byte reversal per [U-Boot aml_dt.c](https://third-party-mirror.googlesource.com/u-boot/+/refs/heads/vim3/common/aml_dt.c); it is not yet proved that the user's actual device selects the last variant.
- 2024 stock `recovery.fstab` mounts `/system` as `/` (system-as-root) and includes `/data ext4 encryptable=footer`. The latter is **not proof of working TWRP decryption**.
- The v1 embedded Recovery DTBO section must be checked for exact size/offset and matched with `PARTITION/dtbo` before packaging; [Android boot image specification](https://source.android.com/docs/core/architecture/bootloader/boot-image-header).

## Source layout

- `BoardConfig.mk`: proposed SM1 board, original boot header and load addresses; 32-bit recovery ABI and 16 MiB partition-size ceiling are **provisional**.
- `AndroidProducts.mk`, `omni_x96maxplus2101w.mk`: TWRP 9.0 Omni product declaration.
- `recovery/root/etc/recovery.fstab`: original vendor recovery mount table for offline comparison (comments added).
- `recovery/root/etc/twrp.fstab`: restricted TWRP-compatible mount candidates. Dangerous bootloader, tee, metadata, param writes are intentionally excluded; removable storage aliases not yet mapped.
- `scripts/inspect_amlogic.py` and `scripts/analyze_android_boot.py`: inspect stock package, Android images, ramdisk, DTBO and Multi-DTB without executing vendor binaries.
- `scripts/prepare_twrp_prebuilt.py`: enforce exact stock image/version/DTB and stage `prebuilt/kernel`, `prebuilt/second`, and `prebuilt/dtbo.img` as temporary local build inputs.
- `.github/workflows/inspect_stock.yml`: reproduce extraction, run offline tests, retain build inputs as short-lived Actions Artifacts. Stock and third-party firmware Releases are never modified by this workflow.

The source repository intentionally excludes proprietary kernel/bootloader binaries. To use this device tree, place it at `device/amlogic/x96maxplus2101w` **inside the selected TWRP/Omni source checkout**. Follow the device tree's source-branch validation gates before running `lunch omni_x96maxplus2101w-eng` and building `recoveryimage`.

## Unverified requirements before a build can be accepted

| Priority | Check | Acceptance evidence |
| --- | --- | --- |
| P0 | `recovery_dtbo_size`, exact overlay bytes and original header v1 | V1 extraction equals original partition DTBO |
| P0 | Actual `recovery` partition size | Stock partition table or `/proc/partitions`; no guessed ceiling in a final release |
| P0 | Userspace ABI/Android branch selection | Stock Recovery ELF interpreter/architecture and executable dependencies |
| P0 | Proper ramdisk source, init/ueventd and Amlogic USB gadget | Full stock ramdisk inventory with no missing required binaries/modules |
| P0 | Kernel, second, DTBO provenance | Exact byte equivalence to archived original, correct board variant |
| P1 | 2024 ROM filesystem/partition properties | Read-only sparse image inspection; mount topology/fstab reconciled |
| P1 | TWRP 9.0 build | Android build logs and recovery image static validation; must fit actual partition |
| P1 | Decryption, backup/restore, ADB sideload, screen/remote control | Separately authorized on-device tests, with original ROM recovery plan |

**No real device has been touched. No successful TWRP build/boot/FDE/FBE operation has yet been claimed.**

## Approval gates

- **HIGH:** any device flash, bootloader edit, AVB or vbmeta modification, or restoration must be separately approved after hardware matching and recovery proof.
- **HIGH:** firmware mirror publication is limited to original stock and separately classified slimBOXtv sources explicitly requested by the user. Do not publish anything else as factory stock.
- **MEDIUM:** staging unverified kernel/DTB as a public bootable Recovery Release is prohibited. Evidence Artifacts are permitted for offline research only.

## Next engineering steps

1. Finish real recovery v1 DTBO extraction and prepare matching temporary prebuilts.
2. Validate original Recovery userspace ELF ABI and init files; decide the supported TWRP/Omni branch.
3. Review Amlogic SM1 board DTB, partition sizes, USB/HDMI input and UI framebuffer dependencies.
4. Compile a non-release TWRP candidate and compare its header, second/DTBO, partition size and component manifests against stock.
5. Only consider on-device read-only boot checks after a new explicit approval gate.
