# 实验孔板排布工具

把样本及重复测量需求安排到多块 8 行 12 列（A1–H12，每板 96 孔）的孔板上，
自动避开对照孔与禁用孔，输出可供实验人员逐孔核对的布局 CSV 与汇总 JSON。
仅依赖 Python 3.12+ 标准库，无需任何外部服务。

## 输入文件

### 样本 CSV

必须包含表头 `sample_id,group,replicates`，编码 UTF-8（允许带 BOM）：

```csv
sample_id,group,replicates
S1,treated,3
S2,control,2
S3,treated,5
```

- `sample_id`：样本唯一编号，非空且不可重复。
- `group`：非空分组名。
- `replicates`：正整数重复测量孔数。
- 空行会被忽略；任何坏行（缺编号、缺分组、重复编号、非法重复数）都会导致整体失败，
  错误信息标明记录所在行号，不会忽略坏行继续输出。

### 布局配置 JSON

```json
{
  "max_plates": 3,
  "control_wells": ["A1"],
  "disabled_wells": ["H11", "H12"]
}
```

- `max_plates`：允许使用的板数上限，正整数。
- `control_wells`：每块板相同的对照孔（如 `A1`，行 A–H、列 1–12）。
- `disabled_wells`：每块板相同的禁用孔。
- 非法孔位、同类列表内重复占位、对照孔与禁用孔重叠都会被拒绝。

## 分配规则

1. 样本先按 `group` 字典序、再按 `sample_id` 字典序排序；因此打乱输入或重复运行，布局完全一致。
2. 同一样本的全部重复孔必须位于同一块板（不拆板），孔位不必相邻。
3. 依次为每个样本选择**编号最小且剩余容量足够**的已有板；只有所有已有板都放不下时才开新板。
   本工具不追求最少板数的最优解。
4. 板内按**先行后列**取空孔（A1, A2, …, A12, B1, …），列号按数值排序，
   对照孔与禁用孔一律跳过。
5. 每块新板先保留全部对照孔与禁用孔。
6. 单样本重复数超过单板可用容量（96 减去保留孔数），或所需板数超过 `max_plates` 时，
   整次规划失败：返回非零退出码，不生成任何部分结果，也不覆盖已有输出文件。
7. 仅输出实际使用的板。

## 调用方法

在项目根目录运行（需要 Python 3.12+，无需安装第三方依赖）：

```bash
python -m plate_layout --samples samples.csv --config config.json --output-dir out
```

也可用 pip 安装后使用控制台脚本 `plate-layout`（参数相同）：

```bash
pip install .
plate-layout --samples samples.csv --config config.json --output-dir out
```

参数：

- `--samples`：样本 CSV 路径。
- `--config`：布局配置 JSON 路径。
- `--output-dir`：输出目录（不存在会创建；若目标文件已存在则拒绝覆盖）。

## 输出文件

### `plate_01.csv`、`plate_02.csv` …

每块实际使用的板一个文件，96 个孔各占一行，按 A1–H12 顺序排列：

```csv
plate,well,state,sample_id,group,replicate
1,A1,control,,,
1,A2,sample,S1,treated,1
1,A3,sample,S1,treated,2
1,B7,empty,,,
1,H12,disabled,,,
```

`state` 为 `sample`（样本孔）、`control`（对照孔）、`disabled`（禁用孔）、`empty`（空孔）四类。

### `summary.json`

汇总信息，便于程序化核对：

- `plate_count`、`max_plates`、保留孔列表；
- `plates`：每块板的文件名与四类孔计数（四类之和恒为 96）；
- `samples`：每个样本的分组、重复数及全部坐标（板号 + 孔位 + 重复序号）。

## 作为库调用

```python
from plate_layout.config import load_config
from plate_layout.samples import load_samples
from plate_layout.planner import build_layout
from plate_layout.writer import write_outputs

config = load_config("config.json")
samples = load_samples("samples.csv")
result = build_layout(samples, config)
write_outputs(result, config, "out")
```

## 运行测试

```bash
python -m unittest discover -s tests
```

测试覆盖：多板分配、配置/孔位冲突、重复孔不拆板、单板容量不足、板数超限、
输入顺序稳定性、坏行错误定位、拒绝覆盖与 CLI 端到端流程。
