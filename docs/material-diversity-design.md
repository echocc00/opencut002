# 素材多样性抽帧设计（v0.6.4，opt-in）

> 借鉴第三方 fork 的 Level A「素材多样性」改进，opt-in 引入，默认零行为变化。

## 问题

视频素材经 ffmpeg 抽帧后，若简单「取前 N 帧」，候选往往全是视频开头的
`frame_001.jpg` 附近画面 —— 镜头还没展开，内容单一，导致 AI 选图/配图阶段
拿到的候选缺乏代表性，最终视频画面重复度高。

## 方案

`src/tools/material_prep.py` 增加两个可选能力（**默认关闭**）：

1. **`max_per_video`**：限制单个视频最多贡献 N 帧，避免某个长视频堆满候选池、
   挤掉其他视频/图片。
2. **`diversity`**：从抽出的帧里按「相邻帧像素差」选差异最大的 top-k 帧
   （`_select_diverse_frames`），并**保持原始时间顺序**返回（不乱序，保叙事）。

### 选帧算法

- 每帧缩放到 64×64 灰度图，计算与前一帧的 `sum(abs(diff))`
- 首帧差视为 0
- 按差异度降序取 top_k，再按原时序过滤返回
- PIL/numpy 不可用或读图失败 → 回退均匀采样（`frames[::step][:top_k]`），绝不崩

## 开关

```bash
OPENCUT_MATERIAL_DIVERSITY=1   # 开启：diversity=True + 每视频最多 3 帧
```

`run_full.py` 与 `src/api/project_routes.py`（Web 上传）都读这个 env：

- 关（默认）：`prepare_materials(mat_dir)` 行为与 v0.6.3 完全一致
  （`max_per_video=None` 不限、`diversity=False`）
- 开：`max_per_video=3`（`DIVERSITY_MAX_PER_VIDEO`）+ `diversity=True`

**注意**：上游没有采纳 fork 把 `max_count` 默认 5→30、`fps` 0.2→0.5 的行为变更
（那会改变所有现有项目的素材量与抽帧密度）。这两项仍由调用方显式传参控制，
默认签名保持 `max_count=5, fps=0.2` 向后兼容。

## 依赖

- PIL（Pillow）+ numpy：`[face]` extras 已含 Pillow；numpy 缺失自动回退均匀采样
- 无新硬依赖

## 测试

`tests/test_material_diversity.py`：默认关不变 / env 开 / max_per_video 裁剪 /
diversity 保持时序 / ≤top_k 原样 / PIL 缺失回退 / 无 ffmpeg 跳过 / 抽帧失败跳过。
