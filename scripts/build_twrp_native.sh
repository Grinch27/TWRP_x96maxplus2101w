#!/usr/bin/env bash
# Requirements: real Omni/TWRP 9.0 native build using verified 2024 stock prebuilts.
# Ambiguities: Android9 legacy tools, actual partition capacity, kernel USB host.
# Research: USB HID/HDMI and stock init/decryption runtime require later approval.
# Risks: 14GiB hosted disk, Python2 EOL, unavailable upstream, oversized image.
# Verification: full sync + make recoveryimage + independent static validation;
# no device flash, no Release, no force-sync or missing-dependency bypass.
set -euo pipefail
readonly DEVICE=x96maxplus2101w
readonly WORK_ROOT="${RUNNER_TEMP:?}/twrp9-native"
readonly SRC="${WORK_ROOT}/src"
readonly BOARD_SOURCE="${GITHUB_WORKSPACE:?}"
readonly STOCK_TAG=firmware-2101w-stock-20240508-42466511950-1

space_gate() {
  local kib
  kib="$(df -Pk "${WORK_ROOT}" | awk 'NR==2 {print $4}')"
  echo "Free KiB before ${2}: ${kib}"
  (( kib >= ${1} * 1024 * 1024 )) || {
    echo "Insufficient runner storage before ${2}" >&2
    exit 1
  }
}

prepare() {
  mkdir -p "${SRC}" "${WORK_ROOT}/rom" "${WORK_ROOT}/inspect" "${WORK_ROOT}/stock-prebuilt"
  space_gate 8 stock-download
  : "${GH_TOKEN:?GitHub read-only token required}"
  gh release download "${STOCK_TAG}" --repo "${GITHUB_REPOSITORY:?}" \
    --pattern amlogic-factory-package.img --dir "${WORK_ROOT}/rom"
  python3 "${BOARD_SOURCE}/scripts/inspect_amlogic.py" \
    "${WORK_ROOT}/rom/amlogic-factory-package.img" "${WORK_ROOT}/inspect"
  python3 "${BOARD_SOURCE}/scripts/analyze_android_boot.py" \
    "${WORK_ROOT}/inspect" "${WORK_ROOT}/inspect/boot-metadata"
  python3 "${BOARD_SOURCE}/scripts/prepare_twrp_prebuilt.py" \
    "${WORK_ROOT}/inspect" "${WORK_ROOT}/stock-prebuilt" \
    --inspection-run "${GITHUB_RUN_ID:?}"
  local project="${SRC}/device/amlogic/${DEVICE}"
  mkdir -p "${project}/prebuilt" "${project}/recovery/root/etc"
  for name in Android.mk AndroidProducts.mk BoardConfig.mk omni_x96maxplus2101w.mk; do
    cp "${BOARD_SOURCE}/${name}" "${project}/${name}"
  done
  cp "${BOARD_SOURCE}/recovery/root/etc/twrp.fstab" "${project}/recovery/root/etc/twrp.fstab"
  cp "${BOARD_SOURCE}/recovery/root/etc/recovery.fstab" "${project}/recovery/root/etc/recovery.fstab"
  for name in kernel second dtbo.img; do
    cp "${WORK_ROOT}/stock-prebuilt/${name}" "${project}/prebuilt/${name}"
  done
  # Only clean ephemeral re-downloads after original Release-derived validation.
  rm -f "${WORK_ROOT}/rom/amlogic-factory-package.img"
  rm -rf "${WORK_ROOT}/inspect"
  space_gate 8 upstream-checkout
}

legacy_python() {
  if command -v python2 >/dev/null 2>&1; then
    echo "Python2 already available"
  elif sudo apt-get install -y --no-install-recommends python2; then
    echo "Python2 distro package installed"
  else
    local py="${WORK_ROOT}/python2"
    mkdir -p "${py}"
    curl -fsSL https://www.python.org/ftp/python/2.7.18/Python-2.7.18.tgz -o "${py}/source.tgz"
    tar -xzf "${py}/source.tgz" -C "${py}"
    ( cd "${py}/Python-2.7.18" && ./configure --prefix="${py}/install" --disable-shared >/dev/null && make -j2 >/dev/null && make install >/dev/null )
    export PATH="${py}/install/bin:${PATH}"
  fi
  mkdir -p "${WORK_ROOT}/shim"
  local interpreter
  interpreter="$(command -v python2 || command -v python2.7)"
  ln -s "${interpreter}" "${WORK_ROOT}/shim/python"
  printf '%s\n' "${WORK_ROOT}/shim" >> "${GITHUB_PATH:?}"
  "${WORK_ROOT}/shim/python" --version
}

sync_sources() {
  mkdir -p "${WORK_ROOT}/bin"
  curl -fsSL https://storage.googleapis.com/git-repo-downloads/repo -o "${WORK_ROOT}/bin/repo"
  chmod +x "${WORK_ROOT}/bin/repo"
  ( cd "${SRC}"
    "${WORK_ROOT}/bin/repo" init --depth=1 -u https://github.com/minimal-manifest-twrp/platform_manifest_twrp_omni.git -b twrp-9.0
    # The twrp-9.0 minimal manifest removes Android 9 source providers used
    # by the Soong dependency graph. Restore actual AOSP projects declared in
    # the separately reviewed manifest, not synthetic module definitions.
    mkdir -p .repo/local_manifests
    cp "${BOARD_SOURCE}/build/manifests/twrp9-required.xml" \
      .repo/local_manifests/twrp9-required.xml
    "${WORK_ROOT}/bin/repo" sync -j3 -c --no-tags --fail-fast
    # Recovery-only: remove three foreign handset HAL edges from the Omni
    # system_server module. Leave their Java sources and all real recovery
    # dependencies unchanged. Any attempted system_server build still fails
    # normally on unresolved imports; never create dummy HAL modules.
    python3 "${BOARD_SOURCE}/scripts/prune_nonrecovery_hal.py" \
      frameworks/base/services/core/Android.bp
    test -f external/skia/Android.bp
    grep -Eq 'name: *"skia_deps"' external/skia/Android.bp
    test -f prebuilts/tools/common/m2/Android.bp
    test -f external/okhttp/Android.bp
    test -f external/aac/Android.bp
    test -f build/envsetup.sh
    test -f bootable/recovery/minuitwrp/events.cpp
    grep -q REL_X bootable/recovery/minuitwrp/events.cpp
    grep -q BTN_LEFT bootable/recovery/gui/gui.cpp
    test -f "device/amlogic/${DEVICE}/BoardConfig.mk"
  )
  space_gate 3 android-compilation
}

compile() {
  cd "${SRC}"
  # Do not use ALLOW_MISSING_DEPENDENCIES: missing modules must fail visibly.
  # Legacy Android 9 envsetup/lunch relies on unset shell variables and
  # benign probe failures. Suspend errexit/nounset ONLY for those two commands,
  # check both return codes, then restore strict build execution.
  set +e +u
  source build/envsetup.sh
  local setup_rc=$?
  if (( setup_rc != 0 )); then
    printf 'Android 9 envsetup failed: rc=%s\n' "${setup_rc}" >&2
    exit "${setup_rc}"
  fi
  lunch "omni_${DEVICE}-eng"
  local lunch_rc=$?
  set -euo pipefail
  if (( lunch_rc != 0 )); then
    printf 'Android 9 lunch failed: rc=%s\n' "${lunch_rc}" >&2
    exit "${lunch_rc}"
  fi
  make -j2 recoveryimage
  local image="${SRC}/out/target/product/${DEVICE}/recovery.img"
  test -s "${image}"
  python3 "${BOARD_SOURCE}/scripts/validate_native_recovery.py" \
    "${image}" "${WORK_ROOT}/stock-prebuilt" "${WORK_ROOT}/validation"
  echo "${image}" > "${WORK_ROOT}/candidate.path"
}

case "${1:-}" in
  prepare) prepare ;;
  toolchain) legacy_python ;;
  sync) sync_sources ;;
  build) compile ;;
  *) echo 'Usage: build_twrp_native.sh {prepare|toolchain|sync|build}' >&2; exit 2 ;;
esac
