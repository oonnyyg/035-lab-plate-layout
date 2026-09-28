# 实验孔板排布工具 (lab-plate-layout)

把带有重复测量需求的样本安排到多块 8 行 × 12 列（A1–H12，共 96 孔）的实验孔板上，
自动避开每块板上相同的对照孔与禁用孔，并输出可供实验人员**逐孔核对**的布局 CSV
与汇总 JSON。仅使用 Python 标准库，不依赖任何外部服务。

## 运行环境

- Python 3.12+（仅标准库）

## 输入文件

### 1. 样本 CSV（如 `examples/samples.csv`）

必需表头为 `sample_id,group,replicates`（允许额外列，将被忽略）：

```csv
sample_id,group,replicates
S01,alpha,3
S02,beta,90
S03,beta,2
S04,alpha,2
```

校验规则（任一不满足即整体失败，错误信息定位到具体记录号与 CSV 行号）：

- 样本表不能为空（无表头或无数据行均拒绝）；
- `sample_id` 非空且全表唯一，`group` 非空；
- `replicates` 必须是正整数（空值、`0`、负数、非数字均拒绝）。

### 2. 布局配置 JSON（如 `examples/config.json`）

```json
{
  "max_plates": 3,
  "control_wells": ["A1", "H12"],
  "disabled_wells": ["A2"]
}
```

- `max_plates`：正整数，允许使用的板数上限；
- `control_wells` / `disabled_wells`：每块板**相同**的对照孔与禁用孔列表；
- 孔位格式为单个行字母 `A`–`H` 加数值列号 `1`–12（如 `a1` 等价于 `A1`）；
- 非法孔位、同一列表内重复占位、对照孔与禁用孔重叠均拒绝。

## 分配规则

1. 样本按 **(分组 group, 样本编号 sample_id) 字典序** 依次安排；
2. **同一样本的全部重复孔必须在同一块板上**，不要求孔位相邻；
3. 依次查看已开的板，选择**编号最小且剩余可用容量足够**的板；
4. 所有已开板都放不下时才开新板；每块新板先保留全部对照孔和禁用孔；
5. 板内取孔顺序为**先行后列**（A1, A2, …, A12, B1, …），列号按数值排序，
   自动跳过对照孔、禁用孔和已占用孔；
6. 单样本重复数超过单板可用容量（96 − 对照孔数 − 禁用孔数）时，或所需板数
   超过 `max_plates` 时，**整次规划失败**：不生成部分结果，也不覆盖已有输出；
7. 不追求最少板数的最优解；布局完全确定——打乱输入记录或重复运行，结果逐字节一致。

## 调用方法

无需安装依赖，在项目根目录直接运行：

```powershell
python -m plate_layout --samples examples\samples.csv `
                       --config examples\config.json `
                       --output-dir out
```

也可安装后使用控制台命令（可选）：

```powershell
pip install -e .
plate-layout --samples examples\samples.csv --config examples\config.json --output-dir out
```

作为库调用：

```python
from plate_layout import load_config, load_samples, plan_layout, write_outputs

samples = load_samples("examples/samples.csv")
config = load_config("examples/config.json")
layout = plan_layout(samples, config)   # 先完整规划
csv_path, json_path = write_outputs(layout, "out")  # 成功后才写盘
```

## 输出文件

### `plate_layout.csv`

仅包含**实际使用的板**；每块板 96 行，按 A1→H12 排列，共 96 × 板数 行：

| 列 | 含义 |
| --- | --- |
| `plate` | 板编号（从 1 开始） |
| `well` / `row` / `column` | 孔位（如 A3）、行字母、数值列号 |
| `content_type` | `sample` / `control` / `disabled` / `empty` 四类之一 |
| `sample_id` / `group` / `replicate` | 样本孔对应的样本编号、分组与重复序号（1 起） |

### `plate_summary.json`

- `plates_used`：实际使用板数；
- `plates`：每块板四类孔（sample/control/disabled/empty）数量，合计恒为 96，
  可与布局 CSV 交叉核对；
- `samples`：每个样本的全部坐标（板号 + 孔位），坐标数等于其重复数；
- 同时回显 `max_plates`、`control_wells`、`disabled_wells` 便于审计。

## 测试

```powershell
python -m unittest discover -s tests -v
```

覆盖：单板/多板分配、先填小编号板的回填策略、重复孔不拆板、新板保留孔位、
孔位非法/冲突/重复、容量不足与板数上限失败、输入乱序与重复运行的确定性、
以及失败时不覆盖已有结果。
