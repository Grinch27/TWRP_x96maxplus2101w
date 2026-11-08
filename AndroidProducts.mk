# Requirements: separate X96 MAX+ 2101W build identity; no u212 aliases.
# Ambiguities: stock Android ro.product.device is not independently confirmed.
# Research: confirm build product choices on the selected TWRP branch.
# Risks: unrelated Amlogic products must never be selected implicitly.
# Verification: lunch lists omni_x96maxplus2101w-eng.
PRODUCT_MAKEFILES := $(LOCAL_DIR)/omni_x96maxplus2101w.mk

COMMON_LUNCH_CHOICES := \
    omni_x96maxplus2101w-userdebug \
    omni_x96maxplus2101w-eng
