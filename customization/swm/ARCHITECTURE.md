# 汉字语义世界：定制框架

设计原则是把「真实状态」「字符观察」「学习器」分开。水增加时可以仍显示同一个「水」字；观察被逗号遮蔽时，底层过程仍继续。学习器通过观察序列估计状态和规律，参考模拟器提供可重复的实验与评价标准。

## 当前可运行结构

```mermaid
flowchart TB
    Author[创作者：画字、注水、点火、开门] --> UI[浏览器工作台]
    Author --> Panel[Infernux 原生 SWM 面板]
    UI --> HTTP[本机 HTTP 服务与会话验证]
    HTTP --> Session[Session：动作、轨迹、检查点与回放]
    Panel --> Session
    Host[SWMHost：场景固定步 / observe / act] --> Session
    Session --> World[World：持久数值状态]
    World --> Process[水流 / 热交换 / 材料过程]
    Process --> World
    World --> Projection[字符投影与可见性遮罩]
    Projection --> UI
    Projection --> Dataset[字符观察序列]
    Dataset --> Baseline[局部字符转移学习基线]
    Baseline --> Evaluation[对比保持不变基线与变化格准确率]
    Session --> Replay[初始状态 + 动作序列 + 最终 SHA256]
    Replay --> Session
    World --> Inspector[仅创作者使用的隐藏状态检查器]
    Inspector --> UI
```

核心不依赖引擎，可独立运行与测试；插件把同一核心接入 Infernux 的生命周期、面板和组件系统。编辑器与浏览器共享一份 Session 和锁。网页、HTTP 服务和训练工具仅用于创作；Runtime 角色只承载世界核心与宿主。

## 核心类型关系

```mermaid
classDiagram
    class World {
        +int width
        +int height
        +int tick
        +ndarray water
        +ndarray temperature
        +ndarray ground
        +ndarray fuel
        +ndarray char
        +ndarray ash
        +ndarray gas
        +ndarray observed
        +apply(command)
        +step(count)
        +observation() dict
        +snapshot() dict
        +restore(data) World
        +digest() str
    }
    class Session {
        +World world
        +dict initial
        +list operations
        +list frames
        +int cursor
        +action(command)
        +step(count)
        +seek(index)
        +export() dict
        +load(document)
    }
    class Workbench {
        +Session session
        +RLock lock
        +start()
        +close()
    }
    class SWMHost {
        +bool auto_step
        +fixed_update(delta)
        +observe() dict
        +act(command)
    }
    class LocalTransitionModel {
        +fit_pair(before, after)
        +predict(observation)
        +document() dict
    }
    Session *-- World
    Workbench --> Session : 共享
    SWMHost --> Session : 共享
    World ..> LocalTransitionModel : 仅字符观察
```

## 对接 3N 的下一阶段

上游的 3N（Neural Network-Native）是发展方向。本版先落实可行动、可观察、可复现实验的数据闭环；没有把路线图功能当成已完成的能力。

```mermaid
flowchart LR
    O[字符与动作轨迹] --> E[待实现：字符与空间编码器]
    E --> Z[待实现：潜在状态与对象槽]
    Z --> R[待实现：关系路径与过程图]
    R --> T[待实现：动作条件状态预测]
    T --> P[下一帧 / 多步 / 反事实预测]
    P --> Loss[对照真实轨迹评价]
    Loss --> E
    T -. 后续部署 .-> Engine[Infernux 推理组件]
```

建议先做三个对照实验：同一字符外观、不同隐藏水量的未来预测；改变含水率和供氧后材料过程的预测；开关门后人物可达性的预测。先用分场景、分初始条件的数据划分，避免训练与测试轨迹泄漏，再研究神经状态表示和关系发现。

当前局部频数模型只验证训练管线。其变化格预测准确率为 0；高总体准确率主要来自静止格，不能证明模型学到了世界规律。

参考模拟器也有明确边界：燃料来源示踪量守恒不等于完整化学质量守恒；温度规则不构成能量守恒模型；房间识别来自显式几何算法。
