# TWRP 9.0 Native 构建与离线验收

## Objective / 已批准范围

目标设备：X96 MAX+ **2101W**，Amlogic **S905X3/SM1**，4 GB RAM + 64 GB eMMC。使用已经在本仓库 Stock Release 中完成下载和静态校验的 2024 年完整原厂烧录包，生成 **真正通过 Android/Omni 构建系统编译的 TWRP 9.0 `recovery.img`**。

本阶段允许 GitHub Actions 执行源码同步、环境安装、编译、离线静态分析和短期构建 Artifact 保存。**禁止创建任何 TWRP Release，禁止设备连接、刷机、修改 AVB/vbmeta、覆写 eMMC、删除历史 Stock/第三方 Release。**

## 构建入口

- [`.github/workflows/twrp_native.yml`](../.github/workflows/twrp_native.yml)
- [`scripts/build_twrp_native.sh`](../scripts/build_twrp_native.sh)
- [`scripts/validate_native_recovery.py`](../scripts/validate_native_recovery.py)
- 上游 Manifest：[minimal-manifest-twrp/platform_manifest_twrp_omni · twrp-9.0](https://github.com/minimal-manifest-twrp/platform_manifest_twrp_omni/tree/twrp-9.0)
- 上游参考：[TeamWin/android_device_amlogic_u212](https://github.com/TeamWin/android_device_amlogic_u212)（**S905X2/G12A，仅供学习结构和图形输入处理，不直接移植其二进制或 SoC 参数**）

选择 Ubuntu 22.04 是为降低 Android 9/Python2/Java8 旧构建链兼容风险，而不是追求最新 Runner。Python2 局限于临时 PATH，JDK8 来自 `actions/setup-java@main`。GitHub 标准公有仓库 Runner 约为 4 核、16 GiB 内存、14 GiB SSD，故采用 `repo init --depth=1`、`repo sync -j3`、`make -j2 recoveryimage`。环境磁盘资源不足则真实失败，不得宣称构建成功或使用占位产物。

### 输入与原厂一致性

源 ROM：[2024 2101W 原厂 Release](https://github.com/Grinch27/TWRP_x96maxplus2101w/releases/tag/firmware-2101w-stock-20240508-42466511950-1)。每次执行从正式 Stock Release 读取完整包，重新离线提取原厂 `kernel`、`second`（Amlogic Multi-DTB）、`dtbo.img`，验证 boot/recovery 内核一致和 DTBO 字节一致，再放入临时 `device/amlogic/x96maxplus2101w/prebuilt/`，不向源码树提交二进制或改动原 Stock Release。

- 设备内部产品名：`x96maxplus2101w`
- SoC / DTB 候选：`s905x3` / `sm1_ac213_4g`
- 原厂 Boot Header：v1、page 2048 字节、独立 Recovery
- 原厂 Recovery 的主要 ELF 程序：**ELF32 ARM**
- Recovery DTBO：**438 字节**、内嵌于偏移 **16,726,016 字节**
- Recovery 分区真实容量：**未确认**；当前 `BoardConfig.mk` 使用 **16 MiB 临时上限**，仅作为防止超大的离线失败门槛，不能代替真实分区信息。

### USB 键盘与鼠标，不包含红外遥控

源代码静态检查：

- TWRP `minuitwrp/events.cpp` 应通过 Linux `EV_REL`、`REL_X` 与 `REL_Y` 检测鼠标。
- TWRP `gui/gui.cpp` 应支持 `BTN_LEFT` 点击和 `EV_REL` 鼠标坐标变化。
- 键盘由 Linux `/dev/input/event*` 输入事件链处理，无需红外 `remotecfg` 服务。
- 原厂 `sbin/remotecfg` 是 **ELF64 AArch64**，本阶段不导入，不额外加入与红外设备有关的服务、库或文件。

**仅检验上游源代码存在相关处理，无法证明 S905X3 原厂内核的 USB Host/HID、HDMI/Framebuffer、输入节点权限或鼠标指针显示正常；必须后续经用户单独批准实机测试。**

## 验收分级

1. `preflight`：本仓库 Python 测试与 Bash 语法检查全部通过。
2. `stock-prebuilt`：从真实 2024 ROM 提取三件原厂预编译输入，内容、大小、来源与原厂验证报告一致。
3. `upstream-sync`：真实拉取 `twrp-9.0` Manifest 与相关源码；不得假造或以空目录代表同步通过。
4. `native-build`：`lunch omni_x96maxplus2101w-eng` 和 `make -j2 recoveryimage` 实际返回零，且存在真正的 `out/target/product/x96maxplus2101w/recovery.img`。
5. `static-accept`：用独立脚本验收真实 Android Boot v1 头、stock `kernel`/`second`/`recovery_dtbo` 字节一致、ramdisk 非空、构建大小不超过当前 16 MiB 暂定门槛。
6. `artifact`：**只在前五步全部通过时**，上传 `recovery.img` 和 `static-validation.json` 为保留 3 天的 Actions Artifact。禁止 Release 或任何实机操作。

以上任何失败都是真实失败。旧版 Manifest 构建工具缺失、GitHub Runner 磁盘限制、未满足模块依赖、TWRP UI 未能静态确认等均不能通过禁用必要检查来隐藏。

## 运行与验证记录

- 首次真实 Native 入口：[Actions Run #42475156248](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42475156248)。状态及结论必须通过 GitHub 实际 Run 核实。
- 本轮扩展后的源码静态测试：[Actions Run #42475335593](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42475335593)，**28 项全部通过**。
- 构建失败时记录精确 Job/Step/错误分类，再按原生构建实际原因修正，不宣称“源码可编译”。

## Pending / 非本阶段范围

- 原厂实际 eMMC 分区容量、真实 U-Boot Multi-DTB 选择、USB 键鼠／HDMI、ADB/MTP、挂载点及加密功能均未验收。
- 即使 Native 编译和静态验收成功，也不证明 Recovery 能启动或支持备份恢复；**下一次实机测试需要额外 HIGH-risk Approval Gate**。

## 实际 Native 运行记录（均非 Release）

| Run | 已验证达到的阶段 | 真实结果 |
| --- | --- | --- |
| [#42475156248](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42475156248) | 完整 ROM 输入、Python2、Java8、repo sync 均通过 | 旧版 Android 9 `envsetup.sh` 与 `set -u` 冲突；已修复严格模式作用域 |
| [#42475580066](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42475580066) | `envsetup` 能执行，产品配置检查开始 | `TARGET_COPY_OUT_VENDOR` 缺失；已从上游 Amlogic 9.0 设备树验证需要 `vendor` |
| [#42475902594](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42475902594) | `lunch` 成功、Soong bootstrap 执行至 76/76 | `hwui_defaults` 引用缺失的 `skia_deps`，来自 minimal manifest 中未同步的 `external/skia` |
| [#42476327374](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42476327374) | ROM 提取、Python2、环境准备 | 局部 Manifest 试图移除已被 groups 过滤的 Skia 项，`repo sync` 拒绝；已删除无效 `remove-project` |
| [#42476519937](https://github.com/Grinch27/TWRP_x96maxplus2101w/actions/runs/42476519937) | 第五次非发布真实构建入口 | 以 GitHub 最新的最终运行状态为准；不可在执行中声称成功 |

根因修复原则：精确诊断后在脚本或设备树内进行最小修复，`external/skia` 通过 `refs/tags/android-9.0.0_r47` 真实源码补齐，不开启 `ALLOW_MISSING_DEPENDENCIES`，不伪造 C++ / Soong 模块。
