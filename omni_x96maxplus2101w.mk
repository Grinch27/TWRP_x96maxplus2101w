# Requirements: product identity for the X96 MAX+ 2101W 4GB/64GB.
# Ambiguities: manufacturer/brand properties are presentation aliases, not
# verified bootloader product identifiers or proof of real device support.
# Research: verify stock ro.product.* from system and vendor properties.
# Risks: selection of wrong hardware DTB or userspace ABI during porting.
# Verification: build environment product dump, resulting recovery.prop.
PRODUCT_RELEASE_NAME := x96maxplus2101w

$(call inherit-product, $(SRC_TARGET_DIR)/product/aosp_base.mk)
$(call inherit-product, build/target/product/embedded.mk)
$(call inherit-product, vendor/omni/config/common.mk)

PRODUCT_DEVICE := x96maxplus2101w
PRODUCT_NAME := omni_x96maxplus2101w
PRODUCT_MODEL := X96 MAX+ 2101W
PRODUCT_BRAND := X96
PRODUCT_MANUFACTURER := Amlogic

# The separate recovery fstab is intentionally kept in recovery/root/etc.
# Do not replace vendor init or fstab paths until an actual Android build
# confirms whether this branch copies device recovery/root automatically.
