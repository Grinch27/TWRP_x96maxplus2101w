# Requirements: offline TWRP 9.0 recovery image for X96 MAX+ 2101W.
# Facts (stock run 42471323150): S905X3/SM1, Multi-DTB sm1_ac213_4g,
# Android boot header v1, 2048-byte page, kernel load 0x01080000,
# ramdisk load 0x01000000, second load 0x00F00000, tags 0x100.
# Ambiguities: stock userland ABI (arm/arm64), exact recovery partition size,
# ramdisk dependencies, DTBO inclusion, encryption and kernel module ABI.
# Research: verify header v1 recovery_dtbo, real U-Boot DTB selection,
# partition sizes, recovery ELF architecture and fstab runtime block nodes.
# Risks: incorrect recovery image, corrupt bootloader, missing vendor HAL,
# inadequate partition space. Never flash or disable AVB automatically.
# Verification: stock extraction, binary/header tests, TWRP compile, offline
# repacking comparison, eventual independently approved device boot test.

DEVICE_PATH := device/amlogic/x96maxplus2101w

# Provisional 32-bit recovery userspace matching TeamWin's 9.0 Amlogic tree.
# This is NOT yet confirmed against 2101W stock recovery binaries.
TARGET_ARCH := arm
TARGET_ARCH_VARIANT := armv8-a
TARGET_CPU_ABI := armeabi-v7a
TARGET_CPU_ABI2 := armeabi
TARGET_CPU_VARIANT := cortex-a53
TARGET_CPU_SMP := true
TARGET_USES_64_BIT_BINDER := true

BOARD_VENDOR := amlogic
TARGET_SOC := s905x3
TARGET_BOARD_HARDWARE := amlogic
TARGET_BOARD_PLATFORM := sm1
# The DTB says ac213. It does not prove ro.bootloader or U-Boot board name.
TARGET_BOOTLOADER_BOARD_NAME := ac213
TARGET_NO_BOOTLOADER := true
TARGET_NO_RADIOIMAGE := true

# Stock-matched Android boot v1 geometry.
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_PAGESIZE := 2048
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel
BOARD_PREBUILT_DTBOIMAGE := $(DEVICE_PATH)/prebuilt/dtbo.img
BOARD_INCLUDE_RECOVERY_DTBO := true
BOARD_KERNEL_CMDLINE := androidboot.dtbo_idx=0 --cmdline root=/dev/mmcblk0p18 buildvariant=userdebug
BOARD_MKBOOTIMG_ARGS := \
    --kernel_offset 0x01080000 \
    --ramdisk_offset 0x01000000 \
    --second_offset 0x00F00000 \
    --tags_offset 0x00000100 \
    --second $(DEVICE_PATH)/prebuilt/second \
    --header_version 1

# Provisional conservative image-size ceiling, NOT confirmed partition size.
# Stock recovery.img is 16,728,064 B; 16 MiB = 16,777,216 B.
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 16777216
BOARD_BOOTIMAGE_PARTITION_SIZE := 16777216
BOARD_FLASH_BLOCK_SIZE := 131072

BOARD_BUILD_SYSTEM_ROOT_IMAGE := true
BOARD_SYSTEMIMAGE_PARTITION_TYPE := ext4
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := ext4
TARGET_USERIMAGES_USE_EXT4 := true
BOARD_HAS_LARGE_FILESYSTEM := true

RECOVERY_VARIANT := twrp
TW_THEME := landscape_hdpi
TW_NO_BATT_PERCENT := true
TW_NO_SCREEN_TIMEOUT := true
TW_EXTRA_LANGUAGES := true
TW_INCLUDE_CRYPTO := true
TW_INCLUDE_LOGCAT := true
TW_NO_REBOOT_BOOTLOADER := true

# AVB/vbmeta is present in stock. Never force-disable verification.
# Do not enable format/wipe permissions for unknown partitions.
