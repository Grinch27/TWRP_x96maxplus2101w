# Requirements: include only device-specific build files for 2101W.
# Ambiguities: recoveries for other Amlogic boards are not supported.
# Research: validate against pinned Omni/TWRP 9.0 checkout before release.
# Risks: build-root path mismatch and unsupported Android branches.
# Verification: lunch omni_x96maxplus2101w-eng and mka recoveryimage.
LOCAL_PATH := $(call my-dir)

ifeq ($(TARGET_DEVICE),x96maxplus2101w)
include $(call all-makefiles-under,$(LOCAL_PATH))
endif
