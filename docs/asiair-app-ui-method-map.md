# ASIAIR App 界面骨架与方法映射

## 1. 文档范围

本文档用于把 ASIAIR App 的主要界面骨架、菜单分级、可点击交互点，与本项目已经整理出的 ASIAIR 方法目录进行对应。

本文档面向前端原型和后续交互设计，目标是确定：

- 网页端主骨架如何参照 ASIAIR App 的操作结构。
- 每个界面区域有哪些可点击交互点。
- 每个交互点在网页端应抽象成什么前端动作。
- 每个前端动作可对应哪些已知方法。
- 哪些交互只适合展示，哪些适合模拟，哪些应默认禁用。

本文档中的方法名来自本项目已有的逆向方法目录与本地验证记录。方法名不是官方公开 API 承诺。

## 2. 资料来源

界面骨架来源：

- ZWO ASIAIR Plus User Manual V1.3，ASIAIR App 章节。
- ZWO ASIAIR User Manual，Preview、Focus、Autorun 等章节。
- High Point Scientific 的 ASIAIR 使用指南，用于补充现代 App 工作流描述。
- 本项目 `docs/asiair-jsonrpc.md` 中的已知方法目录和本地测试记录。

前端映射依据：

- 官方说明中的界面区域、模式切换、设备设置、辅助工具和拍摄流程。
- 本项目已经验证或归类的方法名称。
- 当前项目目标：网页端先做静态模拟，再按风险逐步接入真实控制。

## 3. 总体界面骨架

ASIAIR App 主控界面可抽象为四个固定区域：

| 区域 | App 含义 | 网页端对应 |
|---|---|---|
| 顶部设备设置区 | ASIAIR、主相机、导星、赤道仪、滤轮、调焦器、存储等设置入口 | 设备配置栏 |
| 左侧辅助工具区 | 直方图、调焦、导星、解析、十字线、标注、星点检测等工具 | 图像与辅助工具栏 |
| 右侧模式操作区 | Preview、Focus、Polar Align、Autorun、Plan、Live、Video 等模式切换及拍摄按钮 | 工作模式栏 |
| 底部状态区 | 当前工作状态、相机信息、分辨率、Gain、温度、制冷功率等 | 运行状态栏 |

网页端主骨架：

```text
顶部：设备切换 + 设备设置入口
左侧：图像辅助工具
中间：当前模式主工作区
右侧：模式切换 + 当前模式操作
底部：当前设备运行状态
侧边抽屉：日志、方法库、命令结果、告警
```

## 4. 顶部设备设置区

顶部设置区用于进入各硬件和系统配置。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入设备 | `device.enter` | `test_connection`, `get_device_state`, `get_app_state`, `get_view_state` | 可模拟 |
| 切换设备 | `device.switch` | 前端设备列表状态 | 可模拟 |
| ASIAIR 设置 | `settings.openSystem` | `pi_get_info`, `pi_get_time`, `pi_set_time`, `pi_is_verified`, `pi_vl805_version`, `need_reboot`, `is_downgraded`, `clear_downgrade`, `get_setting`, `set_setting`, `get_app_setting`, `set_app_setting`, `get_test_setting`, `set_test_setting` | 设置写入需确认 |
| 主相机设置 | `settings.openMainCamera` | `get_connected_cameras`, `open_camera`, `close_camera`, `get_camera_state`, `get_camera_info`, `get_controls`, `get_control_value`, `set_control_value`, `get_camera_exp_and_bin`, `set_camera_exp_and_bin`, `get_camera_bin`, `set_camera_bin`, `get_camera_16bit`, `set_camera_16bit`, `get_subframe`, `set_subframe`, `get_gain_segment`, `set_pixel_size`, `can_liveview`, `can_abort_expose`, `get_img_name_field`, `set_img_name_field` | 大部分可展示；写入需分级 |
| 导星设置 | `settings.openGuide` | `loop`, `guide`, `find_star`, `flip_calibration`, `get_flip_calibration`, `get_dither`, `set_dither`, `dither`, `restart_guide` | 可模拟；真实动作需确认 |
| 赤道仪设置 | `settings.openMount` | `scope_get_cap`, `scope_get_ra_dec`, `scope_get_equ_coord`, `scope_get_location`, `scope_get_pierside`, `scope_get_track_state`, `scope_get_target_pierside`, `scope_is_moving`, `scope_set_track_state`, `scope_set_target_pierside`, `scope_goto`, `scope_abort_slew`, `scope_park`, `scope_move`, `scope_move_left_by_angle`, `scope_sync`, `start_auto_goto`, `start_auto_goto_pixel`, `stop_auto_goto`, `scan_am5` | 运动类默认禁用 |
| 滤轮设置 | `settings.openWheel` | `get_connected_wheels`, `open_wheel`, `close_wheel`, `get_wheel_state`, `get_wheel_position`, `set_wheel_position`, `get_wheel_slot_name`, `set_wheel_slot_name`, `get_wheel_setting`, `set_wheel_setting`, `set_wheel_unidirection`, `calibrate_wheel` | 状态可展示；转动需确认 |
| 调焦器设置 | `settings.openFocuser` | `get_connected_focuser`, `open_focuser`, `close_focuser`, `get_focuser_state`, `get_focuser_caps`, `get_focuser_value`, `set_focuser_value`, `get_focuser_position`, `move_focuser`, `stop_focuser`, `get_focuser_setting`, `set_focuser_setting`, `start_auto_focuse`, `stop_auto_focuse`, `get_auto_focus_img` | 移动类默认谨慎 |
| 存储设置 | `settings.openStorage` | `get_disk_volume`, `list_mass_storage`, `get_image_save_path`, `set_image_save_path`, `set_image_save_usb_disk`, `eject_disk`, `get_img_file_page_number`, `get_img_file_page_name`, `get_img_file_info`, `set_img_file_info`, `file_rename`, `delete_image`, `save_image`, `start_export_image`, `stop_export_image`, `can_format_emmc` | 删除、弹出、格式化禁用 |
| 网络设置 | `settings.openNetwork` | `pi_get_ap`, `pi_station_scan`, `pi_station_state`, `pi_station_list`, `pi_station_set`, `pi_station_select`, `pi_station_remove`, `pi_station_auto_connect`, `pi_station_open`, `pi_station_close`, `pi_eth0_state`, `pi_set_eth0` | 默认只展示；避免远程断网 |
| 关机/重启 | `system.powerMenu` | `pi_shutdown`, `pi_reboot` | 默认禁用 |

## 5. 右侧模式切换区

右侧模式切换是 ASIAIR App 的核心工作流入口。

| App 模式 | 前端模式 | 方法候选 | 前端处理 |
|---|---|---|---|
| Preview | `mode.preview` | `set_page`, `get_app_state`, `get_camera_exp_and_bin`, `set_camera_exp_and_bin`, `start_exposure`, `stop_exposure`, `save_image`, `get_current_img`, `start_solve`, `stop_solve`, `start_annotate`, `stop_annotate`, `start_find_star`, `stop_find_star` | 第一优先级 |
| Focus | `mode.focus` | `set_page`, `start_exposure`, `stop_exposure`, `get_focuser_position`, `move_focuser`, `stop_focuser`, `start_auto_focuse`, `stop_auto_focuse`, `get_auto_focus_img`, `get_focuser_value` | 可做静态仿真 |
| Polar Align | `mode.polarAlign` | `set_page`, `set_polar_align_image`, `rm_polar_align_image`, `get_polar_align_image`, `start_polar_align`, `pause_polar_align`, `stop_polar_align`, `get_polar_axis`, `get_3p_pa_setting`, `set_3p_pa_setting`, `get_3p_pa_state` | 真实动作需现场条件 |
| Autorun / Scheduled Imaging | `mode.autorun` | `set_page`, `set_sequence`, `get_sequence_number`, `get_sequence`, `delete_sequence`, `clear_sequence`, `reset_sequence_progress`, `set_sequence_setting`, `get_sequence_setting`, `stop_capture`, `clear_autosave_err` | 计划修改需确认 |
| Plan / Multiple Targets | `mode.plan` | `set_page`, `set_plan`, `import_plan`, `get_plan`, `get_enabled_plan`, `list_plan`, `delete_plan`, `reset_plan`, `clear_plan`, `get_target_sequences`, `set_sequence`, `get_sequence` | 删除清空禁用 |
| Live / Real-time Stacking | `mode.liveStacking` | `set_page`, `set_stack_type`, `start_stack`, `stop_stack`, `clear_stack`, `save_stack`, `get_stack_info`, `get_stack_setting`, `set_stack_setting`, `set_calib_frame`, `get_calib_frame`, `set_calib_param`, `get_calib_param`, `get_stacked_img` | 清空栈需确认 |
| Video | `mode.video` | `set_page`, `start_record_avi`, `stop_record_avi`, `start_avi_rtmp`, `stop_avi_rtmp`, `get_rtmp_config`, `set_rtmp_config`, `start_planet_stack`, `stop_planet_stack`, `clear_planet_stack` | 录制可模拟 |
| Batch Stack / Post-processing | `mode.batchStack` | `start_batch_stack`, `stop_batch_stack`, `clear_batch_stack`, `get_batch_stack_setting`, `set_batch_stack_setting`, `del_batch_stack_file` | 删除禁用 |

## 6. 左侧辅助工具区

左侧工具通常围绕当前图像工作。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 直方图开关 | `tool.histogram.toggle` | 前端图像显示状态 | 纯前端 |
| 直方图拉伸 | `tool.histogram.stretch` | 前端图像显示状态 | 纯前端 |
| 直方图自动 | `tool.histogram.autoStretch` | 前端图像显示状态 | 纯前端 |
| 调焦工具 | `tool.focuser.open` | `get_focuser_state`, `get_focuser_position`, `get_focuser_value`, `move_focuser`, `stop_focuser`, `start_auto_focuse`, `stop_auto_focuse` | 移动需确认 |
| 导星浮窗 | `tool.guide.openFloating` | `loop`, `guide`, `find_star`, `restart_guide`, `get_dither`, `set_dither` | 可模拟 |
| 解析 | `tool.solve.start` | `start_solve`, `stop_solve`, `get_solve_result`, `get_last_solve_result`, `get_solve_obj` | 依赖图像 |
| 十字线 | `tool.crosshair.toggle` | 前端叠加层状态 | 纯前端 |
| 标注 | `tool.annotation.start` | `start_annotate`, `stop_annotate`, `get_annotate_result`, `is_img_file_annotated` | 依赖图像 |
| 星点检测 | `tool.starDetect.start` | `start_find_star`, `stop_find_star`, `get_find_star_result` | 依赖星点 |
| 图像缩放 | `tool.image.zoom` | 前端图像显示状态 | 纯前端 |
| 图像拖动 | `tool.image.pan` | 前端图像显示状态 | 纯前端 |

## 7. 底部运行状态区

底部状态区主要用于展示，不承担高风险操作。

| 展示项 | 前端状态字段 | 方法候选 |
|---|---|---|
| 当前页面 | `device.page` | `get_app_state`, `get_view_state` |
| 当前任务 | `device.workflowState` | `get_app_state`, `get_camera_state` |
| 相机名称 | `camera.model` | `get_camera_state`, `get_camera_info` |
| 分辨率 | `camera.resolution` | `get_camera_info`, `get_controls`, `get_control_value` |
| 曝光 | `camera.exposureSeconds` | `get_camera_exp_and_bin`, `get_control_value` |
| Gain | `camera.gain` | `get_control_value` |
| Offset | `camera.offset` | `get_control_value` |
| Bin | `camera.bin` | `get_camera_bin`, `get_camera_exp_and_bin` |
| 位深 | `camera.bitDepth` | `get_camera_16bit` |
| 温度 | `camera.temperatureC` | `get_control_value` |
| 目标温度 | `camera.targetTemperatureC` | `get_control_value` |
| 制冷功率 | `camera.coolerPowerPercent` | `get_control_value` |
| 存储剩余 | `storage.freeBytes` | `get_disk_volume` |
| 供电状态 | `power.outputs` | `get_power_supply`, `pi_output_get`, `pi_output_get2` |

## 8. Preview 模式交互

Preview 是网页端第一阶段最重要的仿真对象。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Preview | `preview.enter` | `set_page`, `get_app_state` | 可模拟 |
| 曝光时间 | `preview.setExposure` | `get_camera_exp_and_bin`, `set_camera_exp_and_bin`, `get_control_value`, `set_control_value` | 可模拟 |
| Bin 设置 | `preview.setBin` | `get_camera_bin`, `set_camera_bin`, `get_camera_exp_and_bin`, `set_camera_exp_and_bin` | 可模拟 |
| Capture / Start | `preview.capture.start` | `start_exposure` | 后续可接入 |
| Stop / Abort | `preview.capture.stop` | `stop_exposure`, `stop_capture` | 可作为安全停止 |
| Save | `preview.image.save` | `save_image` | 可模拟 |
| 当前图像 | `preview.image.current` | `get_current_img` | 可展示 |
| 图像元数据 | `preview.image.info` | `get_img_file_info` | 可展示 |
| 解析当前图 | `preview.solve.start` | `start_solve`, `stop_solve`, `get_solve_result`, `get_last_solve_result`, `get_solve_obj` | 依赖图像 |
| 标注当前图 | `preview.annotation.start` | `start_annotate`, `stop_annotate`, `get_annotate_result` | 依赖图像 |
| 星点检测 | `preview.starDetect.start` | `start_find_star`, `stop_find_star`, `get_find_star_result` | 依赖星点 |
| 选择目标 | `preview.target.search` | `get_list`, `get_obj`, `get_constellations`, `get_comet_position`, `get_planet_position` | 可展示 |
| GoTo 目标 | `preview.target.goto` | `scope_goto`, `start_auto_goto`, `start_auto_goto_pixel`, `stop_auto_goto` | 默认禁用 |
| 跟踪开关 | `preview.mount.trackingToggle` | `scope_get_track_state`, `scope_set_track_state` | 默认谨慎 |
| 方向键 | `preview.mount.nudge` | `scope_move`, `scope_move_left_by_angle`, `scope_abort_slew` | 默认禁用 |
| 同步坐标 | `preview.mount.sync` | `scope_sync` | 默认禁用 |

## 9. Focus 模式交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Focus | `focus.enter` | `set_page` | 可模拟 |
| Start 刷新图像 | `focus.loop.start` | `start_exposure`, `can_liveview` | 可模拟 |
| Stop 刷新图像 | `focus.loop.stop` | `stop_exposure` | 可模拟 |
| 曝光时间 | `focus.setExposure` | `get_camera_exp_and_bin`, `set_camera_exp_and_bin` | 可模拟 |
| Bin 设置 | `focus.setBin` | `get_camera_bin`, `set_camera_bin` | 可模拟 |
| 选择星点框 | `focus.starBox.select` | 前端图像坐标状态 | 纯前端 |
| 放大调焦 | `focus.zoom.toggle` | 前端图像显示状态 | 纯前端 |
| HFD 显示 | `focus.hfd.read` | `start_find_star`, `get_find_star_result` | 依赖图像 |
| EAF 当前位置 | `focus.focuser.position` | `get_focuser_position` | 可展示 |
| EAF 粗调/细调 | `focus.focuser.move` | `move_focuser`, `stop_focuser` | 默认确认 |
| EAF 反向 | `focus.focuser.reverse` | `set_focuser_setting`, `get_focuser_setting` | 可模拟 |
| EAF 步长 | `focus.focuser.stepSetting` | `set_focuser_setting`, `get_focuser_setting` | 可模拟 |
| AF | `focus.autofocus.start` | `start_auto_focuse`, `stop_auto_focuse`, `get_auto_focus_img` | 后续接入 |

## 10. Polar Align 模式交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入极轴模式 | `polar.enter` | `set_page` | 可模拟 |
| 开始极轴流程 | `polar.start` | `start_polar_align` | 依赖现场条件 |
| 暂停极轴流程 | `polar.pause` | `pause_polar_align` | 可作为模拟 |
| 停止极轴流程 | `polar.stop` | `stop_polar_align` | 可作为安全停止 |
| 设置极轴图像 | `polar.image.set` | `set_polar_align_image` | 可模拟 |
| 移除极轴图像 | `polar.image.remove` | `rm_polar_align_image` | 可模拟 |
| 读取极轴图像 | `polar.image.read` | `get_polar_align_image` | 可展示 |
| 读取偏差结果 | `polar.axis.read` | `get_polar_axis` | 可展示 |
| 读取三点设置 | `polar.threePoint.settingRead` | `get_3p_pa_setting` | 可展示 |
| 写入三点设置 | `polar.threePoint.settingWrite` | `set_3p_pa_setting` | 需确认 |
| 读取三点状态 | `polar.threePoint.stateRead` | `get_3p_pa_state` | 可展示 |
| Auto Refresh | `polar.autoRefresh.toggle` | 前端轮询状态 | 纯前端 |

## 11. Autorun / Scheduled Imaging 交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Autorun | `autorun.enter` | `set_page` | 可模拟 |
| 读取序列数量 | `autorun.sequence.count` | `get_sequence_number` | 可展示 |
| 读取序列 | `autorun.sequence.read` | `get_sequence` | 可展示 |
| 新建/修改序列 | `autorun.sequence.write` | `set_sequence` | 模拟；真实需确认 |
| 删除序列 | `autorun.sequence.delete` | `delete_sequence` | 默认禁用 |
| 清空序列 | `autorun.sequence.clear` | `clear_sequence` | 默认禁用 |
| 重置进度 | `autorun.sequence.resetProgress` | `reset_sequence_progress` | 需确认 |
| 序列设置读取 | `autorun.sequence.settingRead` | `get_sequence_setting` | 可展示 |
| 序列设置写入 | `autorun.sequence.settingWrite` | `set_sequence_setting` | 需确认 |
| 开始拍摄 | `autorun.capture.start` | `start_exposure` | 后续接入 |
| 停止拍摄 | `autorun.capture.stop` | `stop_capture`, `stop_exposure` | 可作为安全停止 |
| 清除自动保存错误 | `autorun.autosave.clearError` | `clear_autosave_err` | 可作为低风险动作 |

## 12. Plan / Multiple Targets 交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Plan | `plan.enter` | `set_page` | 可模拟 |
| 计划列表 | `plan.list` | `list_plan` | 可展示 |
| 读取计划 | `plan.read` | `get_plan`, `get_enabled_plan` | 可展示 |
| 新建/修改计划 | `plan.write` | `set_plan` | 模拟；真实需确认 |
| 导入计划 | `plan.import` | `import_plan` | 模拟 |
| 删除计划 | `plan.delete` | `delete_plan` | 默认禁用 |
| 清空计划 | `plan.clear` | `clear_plan` | 默认禁用 |
| 重置计划进度 | `plan.reset` | `reset_plan` | 需确认 |
| 目标序列 | `plan.targetSequences.read` | `get_target_sequences` | 可展示 |
| 当前序列 | `plan.sequence.read` | `get_sequence` | 可展示 |
| 按目标执行 | `plan.capture.start` | `start_exposure` | 后续接入 |
| 停止执行 | `plan.capture.stop` | `stop_capture` | 可作为安全停止 |

## 13. Live / Real-time Stacking 交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Live | `live.enter` | `set_page` | 可模拟 |
| 设置栈类型 | `live.stack.typeSet` | `set_stack_type` | 可模拟 |
| 开始叠加 | `live.stack.start` | `start_stack` | 后续接入 |
| 停止叠加 | `live.stack.stop` | `stop_stack` | 可模拟 |
| 清空叠加 | `live.stack.clear` | `clear_stack` | 默认禁用 |
| 保存叠加结果 | `live.stack.save` | `save_stack` | 可模拟 |
| 叠加状态 | `live.stack.info` | `get_stack_info` | 可展示 |
| 叠加设置读取 | `live.stack.settingRead` | `get_stack_setting` | 可展示 |
| 叠加设置写入 | `live.stack.settingWrite` | `set_stack_setting` | 需确认 |
| 校准帧读取 | `live.calib.read` | `get_calib_frame`, `get_calib_param` | 可展示 |
| 校准帧设置 | `live.calib.write` | `set_calib_frame`, `set_calib_param` | 需确认 |
| 当前叠加图 | `live.image.current` | `get_stacked_img` | 可展示 |

## 14. Video 模式交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 进入 Video | `video.enter` | `set_page` | 可模拟 |
| 开始 AVI 录制 | `video.avi.start` | `start_record_avi` | 后续接入 |
| 停止 AVI 录制 | `video.avi.stop` | `stop_record_avi` | 可模拟 |
| 开始 RTMP | `video.rtmp.start` | `start_avi_rtmp` | 默认谨慎 |
| 停止 RTMP | `video.rtmp.stop` | `stop_avi_rtmp` | 可模拟 |
| RTMP 设置读取 | `video.rtmp.settingRead` | `get_rtmp_config` | 可展示 |
| RTMP 设置写入 | `video.rtmp.settingWrite` | `set_rtmp_config` | 需确认 |
| 开始行星叠加 | `video.planetStack.start` | `start_planet_stack` | 后续接入 |
| 停止行星叠加 | `video.planetStack.stop` | `stop_planet_stack` | 可模拟 |
| 清空行星叠加 | `video.planetStack.clear` | `clear_planet_stack` | 默认禁用 |

## 15. Batch Stack / 后处理交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 批量叠加设置 | `batchStack.settingRead` | `get_batch_stack_setting` | 可展示 |
| 修改批量叠加设置 | `batchStack.settingWrite` | `set_batch_stack_setting` | 需确认 |
| 开始批量叠加 | `batchStack.start` | `start_batch_stack` | 可模拟 |
| 停止批量叠加 | `batchStack.stop` | `stop_batch_stack` | 可模拟 |
| 清空批量叠加 | `batchStack.clear` | `clear_batch_stack` | 默认禁用 |
| 删除批量文件 | `batchStack.file.delete` | `del_batch_stack_file` | 默认禁用 |

## 16. 赤道仪控制面板 MCP

赤道仪控制面板是 Preview、Plan、Live 等流程中的关键浮动面板。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 目标搜索框 | `mount.target.searchOpen` | `get_list`, `get_obj`, `get_constellations`, `get_comet_position`, `get_planet_position` | 可展示 |
| 新增目标列表 | `objectList.add` | `add_list` | 可模拟 |
| 重命名目标列表 | `objectList.rename` | `rename_list` | 可模拟 |
| 删除目标列表 | `objectList.delete` | `del_list` | 默认禁用 |
| 新增目标 | `object.add` | `add_obj` | 可模拟 |
| 删除目标 | `object.delete` | `del_obj` | 默认禁用 |
| 更新彗星数据 | `object.comet.update` | `update_comet_txt` | 需确认 |
| GoTo | `mount.goto` | `scope_goto`, `start_auto_goto`, `start_auto_goto_pixel` | 默认禁用 |
| 停止 GoTo | `mount.goto.stop` | `stop_auto_goto`, `scope_abort_slew` | 可作为安全停止 |
| 方向键 | `mount.move` | `scope_move`, `scope_move_left_by_angle` | 默认禁用 |
| 停止移动 | `mount.move.stop` | `scope_abort_slew` | 可作为安全停止 |
| 速度滑块 | `mount.move.speedSet` | `scope_move` 参数 | 纯前端模拟 |
| 跟踪开关 | `mount.tracking.toggle` | `scope_get_track_state`, `scope_set_track_state` | 需确认 |
| 当前位置 | `mount.position.read` | `scope_get_ra_dec`, `scope_get_equ_coord`, `scope_get_location`, `scope_get_pierside`, `scope_is_moving` | 可展示 |
| 目标 Pier Side | `mount.targetPierSide.read` | `scope_get_target_pierside` | 可展示 |
| 设置目标 Pier Side | `mount.targetPierSide.set` | `scope_set_target_pierside` | 默认禁用 |
| Park | `mount.park` | `scope_park` | 默认禁用 |
| Sync | `mount.sync` | `scope_sync` | 默认禁用 |
| 中天翻转设置 | `mount.meridian.setting` | `get_merid_delta`, `get_merid_setting`, `set_merid_setting` | 写入需确认 |

## 17. 导星界面交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 打开导星浮窗 | `guide.floating.open` | `loop`, `get_app_state` | 可模拟 |
| 打开完整导星页 | `guide.panel.open` | `loop`, `find_star` | 可模拟 |
| 导星曝光时间 | `guide.exposure.set` | `loop` 参数 | 可模拟 |
| 开始循环曝光 | `guide.loop.start` | `loop` | 后续接入 |
| 停止循环曝光 | `guide.loop.stop` | `stop_send` | 可模拟 |
| 自动找星 | `guide.star.find` | `find_star` | 依赖星点 |
| 手动选星 | `guide.star.select` | 前端坐标状态 + `guide` | 需确认 |
| 开始校准 | `guide.calibrate.start` | `guide` | 后续接入 |
| 重启导星 | `guide.restart` | `restart_guide` | 需确认 |
| Dither | `guide.dither` | `dither` | 需确认 |
| Dither 设置 | `guide.dither.setting` | `get_dither`, `set_dither` | 写入需确认 |
| 翻转校准 | `guide.flipCalibration` | `get_flip_calibration`, `flip_calibration` | 需确认 |
| 曲线长度切换 | `guide.graph.windowSize` | 前端图表状态 | 纯前端 |
| 清除曲线 | `guide.graph.clear` | 前端图表状态 | 纯前端 |

## 18. 滤轮面板交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 连接滤轮 | `wheel.open` | `open_wheel` | 可模拟 |
| 断开滤轮 | `wheel.close` | `close_wheel` | 需确认 |
| 滤轮状态 | `wheel.state.read` | `get_connected_wheels`, `get_wheel_state`, `get_wheel_position` | 可展示 |
| 切换滤镜槽 | `wheel.position.set` | `set_wheel_position` | 需确认 |
| 槽位名称读取 | `wheel.slotName.read` | `get_wheel_slot_name` | 可展示 |
| 槽位名称写入 | `wheel.slotName.write` | `set_wheel_slot_name` | 可模拟 |
| 滤轮设置读取 | `wheel.setting.read` | `get_wheel_setting` | 可展示 |
| 滤轮设置写入 | `wheel.setting.write` | `set_wheel_setting`, `set_wheel_unidirection` | 需确认 |
| 校准滤轮 | `wheel.calibrate` | `calibrate_wheel` | 需确认 |

## 19. 调焦器面板交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 连接调焦器 | `focuser.open` | `open_focuser` | 可模拟 |
| 断开调焦器 | `focuser.close` | `close_focuser` | 需确认 |
| 调焦器状态 | `focuser.state.read` | `get_connected_focuser`, `get_focuser_state`, `get_focuser_caps`, `get_focuser_position`, `get_focuser_value` | 可展示 |
| 移动到位置 | `focuser.move.absolute` | `move_focuser` | 需确认 |
| 粗调/细调 | `focuser.move.relative` | `move_focuser`, `stop_focuser` | 需确认 |
| 停止移动 | `focuser.stop` | `stop_focuser` | 可作为安全停止 |
| 设置温补/步长/反向 | `focuser.setting.write` | `get_focuser_setting`, `set_focuser_setting`, `set_focuser_value` | 需确认 |
| 自动对焦 | `focuser.autofocus.start` | `start_auto_focuse`, `stop_auto_focuse`, `get_auto_focus_img` | 后续接入 |

## 20. 存储与图像管理交互

当前项目网页端第一阶段只展示 EMMC Images。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 容量展示 | `storage.capacity.read` | `get_disk_volume`, `list_mass_storage` | 可展示 |
| 保存位置读取 | `storage.savePath.read` | `get_image_save_path` | 可展示 |
| 保存位置设置 | `storage.savePath.write` | `set_image_save_path`, `set_image_save_usb_disk` | 需确认 |
| 弹出外部盘 | `storage.disk.eject` | `eject_disk` | 默认禁用 |
| 图片页数量 | `imageBrowser.page.count` | `get_img_file_page_number` | 可展示 |
| 图片页名称 | `imageBrowser.page.names` | `get_img_file_page_name` | 可展示 |
| 图片元数据 | `imageBrowser.file.info` | `get_img_file_info` | 可展示 |
| 修改图片元数据 | `imageBrowser.file.infoWrite` | `set_img_file_info` | 需确认 |
| 重命名图片 | `imageBrowser.file.rename` | `file_rename` | 需确认 |
| 删除图片 | `imageBrowser.file.delete` | `delete_image` | 默认禁用 |
| 保存当前图像 | `imageBrowser.file.saveCurrent` | `save_image` | 可模拟 |
| 导出图像 | `imageBrowser.export.start` | `start_export_image` | 可模拟 |
| 停止导出 | `imageBrowser.export.stop` | `stop_export_image` | 可模拟 |
| eMMC 格式化能力 | `storage.emmc.formatCheck` | `can_format_emmc` | 只展示，不提供格式化动作 |
| EMMC 素材传输状态 | `backup.emmc.status` | 前端静态数据 | 第一阶段只模拟 |

## 21. 电源输出交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 总供电状态 | `power.status.read` | `get_power_supply` | 可展示 |
| 输出口状态 | `power.output.read` | `pi_output_get`, `pi_output_get2` | 可展示 |
| 输出口开关 | `power.output.toggle` | `pi_output_set`, `pi_output_set2` | 默认禁用 |

## 22. 网络交互

远程台场景中网络操作容易导致失联。

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| AP 状态 | `network.ap.read` | `pi_get_ap` | 可展示但需脱敏 |
| Wi-Fi 扫描 | `network.station.scan` | `pi_station_scan`, `pi_station_list` | 可模拟 |
| Wi-Fi 状态 | `network.station.state` | `pi_station_state` | 可展示 |
| 选择 Wi-Fi | `network.station.select` | `pi_station_select` | 默认禁用 |
| 设置 Wi-Fi | `network.station.set` | `pi_station_set` | 默认禁用 |
| 删除 Wi-Fi | `network.station.remove` | `pi_station_remove` | 默认禁用 |
| 自动连接 | `network.station.autoConnect` | `pi_station_auto_connect` | 默认禁用 |
| 打开/关闭 Station | `network.station.toggle` | `pi_station_open`, `pi_station_close` | 默认禁用 |
| 以太网状态 | `network.eth.read` | `pi_eth0_state` | 可展示 |
| 以太网设置 | `network.eth.write` | `pi_set_eth0` | 默认禁用 |

## 23. 对象库与天体数据交互

| App 点击点 | 前端动作 | 方法候选 | 前端处理 |
|---|---|---|---|
| 对象列表 | `sky.list.read` | `get_list` | 可展示 |
| 新建对象列表 | `sky.list.add` | `add_list` | 可模拟 |
| 重命名对象列表 | `sky.list.rename` | `rename_list` | 可模拟 |
| 删除对象列表 | `sky.list.delete` | `del_list` | 默认禁用 |
| 对象内容 | `sky.object.read` | `get_obj` | 可展示 |
| 新增对象 | `sky.object.add` | `add_obj` | 可模拟 |
| 删除对象 | `sky.object.delete` | `del_obj` | 默认禁用 |
| 星座数据 | `sky.constellations.read` | `get_constellations` | 可展示 |
| 彗星位置 | `sky.comet.position` | `get_comet_position` | 可展示 |
| 行星位置 | `sky.planet.position` | `get_planet_position` | 可展示 |
| 更新彗星文件 | `sky.comet.updateFile` | `update_comet_txt` | 需确认 |

## 24. 内部或不明确方法

以下方法不应直接设计成前端按钮：

| 方法 | 前端处理 |
|---|---|
| `StreamingThread` | 不展示 |
| `my_write_canstop` | 不展示 |
| `pi_encrypt` | 不展示 |

## 25. 前端动作风险分级

| 前端处理 | 含义 | 示例 |
|---|---|---|
| 纯前端 | 只改变浏览器内状态 | 直方图、十字线、缩放、筛选、曲线长度 |
| 可展示 | 只展示状态或结果 | 设备状态、容量、相机状态、计划列表 |
| 可模拟 | 静态阶段可模拟执行 | 扫描 EMMC、模拟传输、模拟预览拍摄 |
| 需确认 | 后续真实接入前需要确认、日志、状态检查 | 改曝光、改 Bin、保存图像、改滤轮槽位 |
| 默认谨慎 | 会影响当前会话或正在运行的任务 | 停止曝光、停止导星、停止叠加、停止计划 |
| 默认禁用 | 会导致失联、硬件运动、删除、断电或不可逆变化 | 关机、重启、断网、删除、清空、Goto、Park、改 16bit |
| 不展示 | 内部符号或用途不清楚 | `StreamingThread`, `my_write_canstop`, `pi_encrypt` |

## 26. 网页端第一阶段交互优先级

第一阶段只做静态模拟，建议先实现以下交互：

| 优先级 | 前端动作 |
|---|---|
| P0 | `device.switch` |
| P0 | `device.enter` |
| P0 | `storage.capacity.read` |
| P0 | `backup.emmc.status` |
| P0 | `backup.emmc.scanMock` |
| P0 | `backup.emmc.transferMock` |
| P0 | `preview.enter` |
| P0 | `preview.setExposure` |
| P0 | `preview.setBin` |
| P0 | `preview.capture.startMock` |
| P0 | `preview.image.saveMock` |
| P0 | `methodCatalog.search` |
| P0 | `methodCatalog.filter` |
| P0 | `eventLog.filter` |
| P1 | `camera.status.read` |
| P1 | `mount.position.read` |
| P1 | `guide.floating.open` |
| P1 | `imageBrowser.page.names` |
| P1 | `imageBrowser.file.info` |
| P1 | `plan.list` |
| P1 | `plan.read` |
| P1 | `focus.enter` |
| P1 | `live.stack.info` |
| P2 | `wheel.state.read` |
| P2 | `focuser.state.read` |
| P2 | `network.ap.read` |
| P2 | `power.status.read` |

## 27. 与 `frontend-only-spec.md` 的关系

`frontend-only-spec.md` 描述前端公开规格，保留业务动作、状态模型和静态数据结构。

本文档描述内部映射，允许出现底层方法名，用于开发时对照：

```text
ASIAIR App 点击点
  -> 前端动作
    -> 方法候选
      -> 前端处理策略
```

前端 UI 中不应把所有方法名直接做成可点击按钮。前端应展示业务动作，方法名只在方法库、调试视图或内部资料中出现。

## 28. 需要继续补齐的内容

后续如果要做到更接近 ASIAIR App，需要继续补齐：

- App 各版本之间的模式名称差异。
- 手机和平板界面在按钮位置上的差异。
- 每个弹窗中的二级设置项。
- 每个模式下的实时状态枚举。
- 每个方法的真实参数形状。
- 每个方法是否会影响当前拍摄任务。
- 哪些动作可以安全停止，哪些停止动作也可能改变状态。
- 哪些只读结果需要脱敏。
