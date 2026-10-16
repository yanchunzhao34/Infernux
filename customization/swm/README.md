# Infernux-SWM 0.1 · 汉字语义世界

这是 Infernux 定制版的第一个可运行实验模块：汉字是创作和观察单元，底层保存连续数量、材料状态与过程。独立工作台和引擎插件共用同一份模拟核心。

[框架图与类型图](ARCHITECTURE.md) · [验收记录](VERIFICATION.md)

## 现在可以做什么

- 在 32×24 的俯视画布上绘制土、墙、门、石、草、木、床、叶、人。
- 检查每格水深、高程、温度、燃料、炭、灰和气体示踪量。
- 注水、开关门、移动角色、点燃材料，编辑含水率和供氧系数。
- 切换汉字、水深、温度观察方式；“，”只隐藏观察，不删除物质。
- 暂停、单步、回退最近 240 次操作；导出初始状态、操作和最终校验哈希，再导入验证。
- 无窗口运行核心，训练一个仅使用字符观察的局部转移基线。
- 打包为 InxPackage，在 Infernux 0.4.2 中加载原生面板与 SWMHost 组件。

## 直接使用

需要 Python 3.12+ 和 NumPy。已有 NumPy 时，双击本目录的 `启动语义世界.cmd`，或运行：

```powershell
python launch.py
```

也可安装独立包，然后运行 `infernux-swm`：

```powershell
python -m pip install .
infernux-swm
```

服务仅监听本机回环地址；每次启动使用新的会话标识，默认自动打开浏览器。关闭启动进程即停止服务。打开的本地 URL 不需要联网；页面没有外部脚本、字体或遥测。

### 四个实验

1. **院落与湖泊**：选择「检查」后点击格点查看隐藏状态；方向键移动人。绘制模式下先选择字，再点击地图。
2. **湖泊注水**：选择湖中格点，按「＋0.5 水」，观察总量上升。字图可能暂时不变。
3. **湿木与供氧**：从左至右是干木充分供氧、湿木充分供氧、干木低供氧，比较剩余燃料与炭。
4. **门与房间**：点击右侧门格，开关门，观察可达性与封闭区域数。几何区域由参考算法得到。

切换场景会创建新实验；需要保留时先保存。拖动轨迹滑块后继续编辑/演化会从所选检查点分支，丢弃后续分支。导出的回放包含全部当前分支操作，不限于滑块窗口。

## Infernux 插件

引擎需要其官方支持的 Python 3.13 和 Infernux 0.4.2。插件无需重新编译引擎。

从仓库根目录构建；每次使用新的暂存目录：

```powershell
python customization/swm/package.py --stage out/stage/swm-build-001
```

输出位于 `dist/releases/swm-0.1.0/`：

- `infernux-swm-0.1.0.inxpkg`：导入已有 Infernux 0.4.2 项目。
- `infernux-swm-0.1.0-source.zip`：独立工作台与源代码。

导入后在 `Extensions / SWM / 语义世界 SWM` 打开面板；面板的「打开语义世界工作台」连接同一会话。Editor 服务由插件 preload 管理，卸载/关闭时停止。

把 `SWMHost` 添加到场景对象，可以调用 `observe()` 和 `act(command)`。`auto_step` 默认关闭；启用后按场景固定步累计到核心的 0.1 秒步长。使用场景自动步进时，暂停浏览器播放，避免两个时钟同时推进。浏览器编辑与固定步共享同一锁和会话。

`runtime/` 只包含核心与宿主组件，`editor/` 包含浏览器工具、HTTP 服务和面板。训练工具和网页不会进入 Player 的 Runtime 角色。跨平台 Player 导出尚需各目标验收；本版本不包含可移植神经推理后端。

## 开发与验证

从本目录运行：

```powershell
python -m unittest discover -s tests -v
python launch.py --train ../../out/swm/baseline
```

第二条命令输出局部符号转移模型和真实评估指标。报告包含“保持上一帧不变”的基线以及发生变化格点的准确率，避免静止格占多数造成虚高成绩。它没有预训练中文知识，不声称发现了因果或高阶对象。

引擎环境中验证实际安装、preload、面板注册、组件步进与清理：

```powershell
python customization/swm/tools/native_smoke.py --project out/swm/native-check --package dist/releases/swm-0.1.0/infernux-swm-0.1.0.inxpkg
```

该命令生成独立演示项目和依赖清单。随后用同一个引擎 Python 打开它：

```powershell
python customization/swm/tools/open_editor.py out/swm/native-check
```

同时运行多个编辑器时，可为演示项目指定不同的本机 MCP 端口：`python customization/swm/tools/open_editor.py --mcp-port 19713 out/swm/native-check`。

GitHub 的 `SWM workbench` 工作流检查独立核心、HTTP 工作流与打包，并提供 ZIP 和插件构建产物。原生编辑器仍需在安装 Infernux 的本机验证。

### 状态与过程约定

- 固定 `dt=0.1`。CPU 浮点参考实现在同一环境中验证精确回放；不承诺跨架构逐位一致。
- 水量以单位格面积的水深表示，按水面高程差进行成对通量交换，总出流受供给量约束。封闭边界；没有蒸发。
- 材料模型是实验规则。`fuel + char + ash + gas` 守恒的是燃料来源示踪量，不是含外界氧气的完整化学质量。
- 含水率和供氧系数是受控参数；温度有环境冷却和上限，不声称完整能量守恒或真实燃烧动力学。
- 空间关系来自参考几何算法，过程来自显式规则。学习型因果结构发现、对象槽及神经世界模型是后续研究任务。
- 观察接口只返回汉字、可见性、尺寸和视图约定。内部事件、材料量和区域标签不会暗中进入字符基线。

## 源码布局

```text
swm_core/           状态、规则、场景、回放、学习基线
swm_workbench/      本机工作台及画布
integration/       引擎宿主组件、preload 和面板
tests/             状态不变量与使用工作流
tools/             打包与引擎验证
```

权威源码仅在此目录维护。打包生成的副本位于 `out/stage/`，不手工编辑。上游引擎代码保留原有版本与许可。

## 许可与来源

本定制模块沿用仓库 MIT 许可。`tools/inxpack.py` 来自 InfernuxEngine/infernux_plugin_template（MIT），许可附于 `tools/INXPACK-LICENSE.txt`。图形界面由本模块的 HTML/CSS/Canvas 直接绘制。
